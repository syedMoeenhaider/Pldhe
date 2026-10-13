"""PLDHE FastAPI backend — walking skeleton.

Flow:  POST /api/v1/intake  → transcribe → triage → resolve location →
       dispatch plan → (farmer consent) → POST /api/v1/cases/{id}/dispatch
"""

import os
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db, init_db
from .dispatch import (
    build_farmer_closure_ur,
    build_vapi_payload,
    build_vet_alert_sms,
    case_latlon,
    extract_tracking_number,
    find_nearest_vets,
    plan_dispatch,
    recommend_path,
    trigger_helpline_proxy_direct,
    trigger_helpline_proxy_n8n,
)
from .vision import analyze_image
from .location import extract_village, resolve_location
from .models import (
    CaseStatus,
    DispatchPath,
    Farmer,
    HelplineCall,
    RiskLevel,
    Veterinarian,
    VeterinaryCase,
)
from .schemas import (
    CaseSummary,
    DispatchConsentRequest,
    DispatchPlan,
    HeatmapPoint,
    HelplineProxyRequest,
    IntakeResponse,
    LiveTriageRequest,
    NearbyVet,
    TriageResult,
    VapiCallbackPayload,
)
from .triage import analyze_symptoms
from .language import normalize_dialect

app = FastAPI(title="PLDHE API", version="0.1.0",
              description="Punjab Livestock Digital Health Ecosystem — walking skeleton")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    os.makedirs(settings.AUDIO_STORAGE_DIR, exist_ok=True)
    init_db()


# ---------------------------------------------------------------- helpers

def transcribe_audio(audio_path: Optional[str], language_hint: str = "ur") -> Optional[str]:
    """Speech-to-text. Uses faster-whisper when installed; else returns None
    so the caller falls back to the typed `text_description`."""
    if not audio_path:
        return None
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, language=language_hint)
    return " ".join(s.text for s in segments).strip() or None


def get_or_create_farmer(db: Session, phone: str, name: Optional[str],
                         village_text: Optional[str], tehsil: Optional[str],
                         lat: Optional[float], lon: Optional[float],
                         language: str) -> Farmer:
    farmer = db.execute(select(Farmer).where(Farmer.phone == phone)).scalar_one_or_none()
    if farmer:
        return farmer
    farmer = Farmer(
        name=name or "Na-maloom Kashtkar",
        phone=phone,
        preferred_language=language,
        village_text=village_text,
        tehsil=tehsil,
        location=from_shape(Point(lon, lat), srid=4326) if lat and lon else None,
    )
    db.add(farmer)
    db.flush()
    return farmer


# ---------------------------------------------------------------- intake

@app.post("/api/v1/intake", response_model=IntakeResponse)
async def intake(
    farmer_phone: str = Form(...),
    farmer_name: Optional[str] = Form(None),
    text_description: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    language_hint: str = Form("ur"),
    village_text: Optional[str] = Form(None),
    intake_channel: str = Form("live_call"),
    db: Session = Depends(get_db),
):
    """Intake: live-call transcript (primary), audio upload, or typed text + GPS → triage → plan."""
    audio_path = None
    if audio is not None:
        ext = os.path.splitext(audio.filename or "")[1] or ".ogg"
        audio_path = os.path.join(settings.AUDIO_STORAGE_DIR, f"{uuid.uuid4().hex}{ext}")
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio.file, f)

    transcript = transcribe_audio(audio_path, language_hint) or (text_description or "")
    transcript = normalize_dialect(transcript, language_hint)
    if not transcript.strip():
        raise HTTPException(400, "Audio ya text_description mein se ek lazmi hai.")

    triage = analyze_symptoms(transcript)
    loc = resolve_location(latitude, longitude, village_text)

    farmer = get_or_create_farmer(db, farmer_phone, farmer_name, village_text,
                                  loc["tehsil"], latitude, longitude, language_hint)

    case = VeterinaryCase(
        farmer_id=farmer.id,
        intake_channel=intake_channel,
        audio_path=audio_path,
        transcript_original=transcript,
        transcript_language=language_hint,
        symptoms_detected=triage["matched_symptoms"],
        suspected_disease=triage["disease_en"],
        suspected_disease_ur=triage["disease_ur"],
        risk_level=triage["risk"],
        triage_confidence=triage["confidence"],
        triage_explanation=triage["explanation"],
        location=from_shape(Point(longitude, latitude), srid=4326)
        if latitude and longitude else None,
        tehsil_resolved=loc["tehsil"],
        address_professional=loc["professional_address"],
        status=CaseStatus.TRIAGED,
        dispatch_path=recommend_path(triage),
    )
    db.add(case)
    db.flush()

    nearest = find_nearest_vets(db, latitude, longitude) if latitude and longitude else []
    plan = plan_dispatch(triage, nearest)
    if plan["requires_consent"]:
        case.status = CaseStatus.AWAITING_CONSENT
    db.commit()
    db.refresh(case)

    return IntakeResponse(
        case_id=case.id,
        status=case.status,
        triage=TriageResult(**triage),
        tehsil_resolved=case.tehsil_resolved,
        address_professional=case.address_professional,
        dispatch=DispatchPlan(**plan),
    )


# ---------------------------------------------------------------- dispatch

@app.post("/api/v1/cases/{case_id}/dispatch")
def execute_dispatch(case_id: UUID, req: DispatchConsentRequest, db: Session = Depends(get_db)):
    """Execute the farmer-confirmed dispatch path."""
    case = db.get(VeterinaryCase, case_id)
    if not case:
        raise HTTPException(404, "Case nahi mila.")
    if not req.consent:
        case.status = CaseStatus.CLOSED
        db.commit()
        return {"case_id": case_id, "status": case.status, "note": "Farmer ne consent nahi diya."}

    path = req.path or case.dispatch_path or recommend_path({"risk": case.risk_level})
    case.farmer_consent = True
    case.dispatch_path = path
    vet_alert_sms = None

    if path == DispatchPath.LOCAL_VET:
        case.status = CaseStatus.DISPATCHED
        # Phase 4 Path A — build the vet's SMS/WhatsApp alert with map pin.
        # (Gateway send is a TODO; the message contract is final.)
        lat, lon = case_latlon(db, case.id)
        farmer = db.get(Farmer, case.farmer_id)
        vet = db.get(Veterinarian, case.assigned_vet_id) if case.assigned_vet_id else None
        vet_alert_sms = build_vet_alert_sms(
            vet.name if vet else "Duty Vet",
            case.suspected_disease_ur or case.suspected_disease or "bemari",
            farmer.village_text or "", case.tehsil_resolved or "",
            farmer.name, farmer.phone, lat, lon,
        )
    elif path == DispatchPath.HELPLINE_PROXY:
        case.status = CaseStatus.HELPLINE_PROXY_IN_PROGRESS
    elif path == DispatchPath.VACCINATION_CHECK:
        case.status = CaseStatus.DISPATCHED
    else:
        case.status = CaseStatus.RESOLVED

    db.commit()
    return {"case_id": case_id, "status": case.status, "path": path,
            "vet_alert_sms": vet_alert_sms}


@app.post("/api/v1/cases/{case_id}/helpline-proxy")
def start_helpline_proxy(case_id: UUID, req: HelplineProxyRequest, db: Session = Depends(get_db)):
    """Path 4 — trigger the autonomous helpline proxy call (via n8n or direct)."""
    case = db.get(VeterinaryCase, case_id)
    if not case:
        raise HTTPException(404, "Case nahi mila.")
    farmer = db.get(Farmer, case.farmer_id)

    vapi_payload = build_vapi_payload(
        case=case,
        farmer_name=farmer.name,
        farmer_phone=farmer.phone,
        disease_en=case.suspected_disease,
        professional_address=case.address_professional or "",
        helpline_number=req.helpline_number or settings.HELPLINE_NUMBER,
    )
    job = {
        "case_id": str(case.id),
        "helpline_number": req.helpline_number or settings.HELPLINE_NUMBER,
        "vapi_payload": vapi_payload,
        "callback_url": "/api/v1/webhooks/vapi",
    }

    if req.use_n8n:
        result = trigger_helpline_proxy_n8n(job)
        call_id = None
    else:
        out = trigger_helpline_proxy_direct(vapi_payload)
        result, call_id = out, out.get("call_id")

    call = HelplineCall(case_id=case.id, provider="vapi",
                        provider_call_id=call_id, status="initiated")
    db.add(call)
    case.status = CaseStatus.HELPLINE_PROXY_IN_PROGRESS
    db.commit()
    return {"case_id": case_id, "trigger": result}


@app.post("/api/v1/webhooks/vapi")
def vapi_callback(payload: VapiCallbackPayload, db: Session = Depends(get_db)):
    """Vapi end-of-call / status-update webhook: capture the tracking number."""
    if not payload.case_id:
        return {"ok": True, "note": "no case_id in callback"}
    case = db.get(VeterinaryCase, payload.case_id)
    if not case:
        return {"ok": True, "note": "unknown case"}

    tracking = extract_tracking_number(payload.transcript or payload.summary)
    call = db.execute(
        select(HelplineCall)
        .where(HelplineCall.case_id == case.id)
        .order_by(HelplineCall.started_at.desc())
    ).scalar_one_or_none()
    if call:
        call.status = payload.status or call.status
        call.transcript = payload.transcript
        call.tracking_number_extracted = tracking
        if payload.status in ("ended", "completed"):
            call.ended_at = datetime.utcnow()
    if tracking:
        case.complaint_tracking_no = tracking
        case.status = CaseStatus.HELPLINE_LOGGED
    # Phase 6 — closing-the-loop message for the farmer (spoken on the still-live
    # intake call via the assistant's check_complaint_status tool, or SMS fallback).
    closure = None
    if tracking:
        vet_name = case.assigned_vet.name if case.assigned_vet else None
        closure = build_farmer_closure_ur(tracking, vet_name)
    db.commit()
    return {"ok": True, "tracking_number": tracking, "farmer_closure_ur": closure}


# ---------------------------------------------------------------- live-call intake

@app.post("/api/v1/triage/live")
def live_triage(req: LiveTriageRequest):
    """Mid-call triage — called by the Vapi intake assistant's function tool
    WHILE the farmer is still on the line. Returns risk + consent message
    so the assistant can react immediately (e.g. ask for dispatch consent)."""
    text = normalize_dialect(req.text, req.language_hint)
    triage = analyze_symptoms(text)
    plan = plan_dispatch(triage, [])
    return {"triage": TriageResult(**triage), "dispatch": DispatchPlan(**plan)}


@app.post("/api/v1/webhooks/vapi-intake")
def vapi_intake(body: Dict[str, Any], db: Session = Depends(get_db)):
    """Vapi live-call intake webhook — end-of-call transcript → full case.

    Configure the intake assistant's `serverUrl` to this endpoint.
    Handles both the wrapped `{"message": {...}}` server-event format
    and a flat payload (for manual testing).
    """
    msg = body.get("message", body) or {}
    mtype = msg.get("type")
    if mtype and mtype not in ("end-of-call-report", "transcript", "summary"):
        return {"ok": True, "ignored": mtype}

    call = msg.get("call", {}) or {}
    customer = call.get("customer", {}) or msg.get("customer", {}) or {}
    phone = customer.get("number") or msg.get("customer_number") or "unknown"
    name = customer.get("name") or msg.get("customer_name")

    transcript = (msg.get("transcript") or "").strip()
    if not transcript:
        return {"ok": True, "note": "empty transcript — no case created"}

    # Pilot default: Layyah farmers speak Saraiki; normalization is harmless for Urdu.
    text = normalize_dialect(transcript, "saraiki")
    triage = analyze_symptoms(text)
    village = extract_village(transcript)
    loc = resolve_location(None, None, village)  # phone calls carry no GPS

    farmer = get_or_create_farmer(db, phone, name, village, loc["tehsil"],
                                  None, None, "saraiki")
    case = VeterinaryCase(
        farmer_id=farmer.id,
        intake_channel="live_call",
        transcript_original=transcript,
        transcript_language="saraiki",
        symptoms_detected=triage["matched_symptoms"],
        suspected_disease=triage["disease_en"],
        suspected_disease_ur=triage["disease_ur"],
        risk_level=triage["risk"],
        triage_confidence=triage["confidence"],
        triage_explanation=triage["explanation"],
        tehsil_resolved=loc["tehsil"],
        address_professional=loc["professional_address"],
        status=CaseStatus.TRIAGED,
        dispatch_path=recommend_path(triage),
    )
    db.add(case)
    db.flush()

    plan = plan_dispatch(triage, [])
    if plan["requires_consent"]:
        case.status = CaseStatus.AWAITING_CONSENT
    db.commit()

    return {
        "ok": True,
        "case_id": str(case.id),
        "risk": triage["risk"].value,
        "disease": triage["disease_en"],
        "village": village,
        "dispatch": plan,
    }


# ---------------------------------------------------------------- read APIs

@app.get("/api/v1/cases/{case_id}")
def get_case(case_id: UUID, db: Session = Depends(get_db)):
    """Single case detail — also polled by the intake assistant's
    check_complaint_status tool (Phase 6 closing-the-loop)."""
    case = db.get(VeterinaryCase, case_id)
    if not case:
        raise HTTPException(404, "Case nahi mila.")
    farmer = db.get(Farmer, case.farmer_id)
    return {
        "id": case.id,
        "status": case.status,
        "risk": case.risk_level,
        "disease": case.suspected_disease,
        "disease_ur": case.suspected_disease_ur,
        "tehsil": case.tehsil_resolved,
        "address": case.address_professional,
        "tracking_no": case.complaint_tracking_no,
        "farmer_phone": farmer.phone if farmer else None,
        "created_at": case.created_at,
    }


@app.post("/api/v1/vision/analyze")
async def vision_analyze(image: UploadFile = File(...)):
    """Phase 2 CV hook: side-profile/headshot → breed guess + weight estimate."""
    ext = os.path.splitext(image.filename or "")[1] or ".jpg"
    path = os.path.join(settings.AUDIO_STORAGE_DIR, f"vision_{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        shutil.copyfileobj(image.file, f)
    return analyze_image(path)

@app.get("/api/v1/cases", response_model=List[CaseSummary])
def list_cases(
    risk: Optional[RiskLevel] = None,
    status: Optional[CaseStatus] = None,
    tehsil: Optional[str] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = select(VeterinaryCase, Farmer.phone).join(Farmer).order_by(VeterinaryCase.created_at.desc())
    if risk:
        q = q.where(VeterinaryCase.risk_level == risk)
    if status:
        q = q.where(VeterinaryCase.status == status)
    if tehsil:
        q = q.where(VeterinaryCase.tehsil_resolved == tehsil)
    rows = db.execute(q.limit(limit)).all()
    return [
        CaseSummary(
            id=c.id, farmer_phone=phone, suspected_disease=c.suspected_disease,
            risk_level=c.risk_level, status=c.status,
            tehsil_resolved=c.tehsil_resolved,
            complaint_tracking_no=c.complaint_tracking_no, created_at=c.created_at,
        )
        for c, phone in rows
    ]


@app.get("/api/v1/vets/nearby", response_model=List[NearbyVet])
def nearby_vets(lat: float, lon: float, radius_km: float = 25,
                db: Session = Depends(get_db)):
    vets = find_nearest_vets(db, lat, lon, limit=10)
    return [v for v in vets if v["distance_km"] <= radius_km]


@app.get("/api/v1/dashboard/heatmap", response_model=List[HeatmapPoint])
def heatmap(disease: Optional[str] = None, db: Session = Depends(get_db)):
    """Case points for the Leaflet heatmap (Module D)."""
    q = select(VeterinaryCase).where(VeterinaryCase.location.isnot(None))
    if disease:
        q = q.where(VeterinaryCase.suspected_disease == disease)
    points = []
    for c in db.execute(q.limit(2000)).scalars():
        pt = db.execute(
            select(func.ST_X(c.location), func.ST_Y(c.location))).first()
        if pt:
            points.append(HeatmapPoint(lat=pt[1], lon=pt[0],
                                       disease=c.suspected_disease, risk=c.risk_level))
    return points


@app.get("/health")
def health():
    return {"status": "ok", "service": "pldhe-backend"}
