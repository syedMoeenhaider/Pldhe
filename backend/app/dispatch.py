"""Module B — Intelligent branching & dispatcher logic.

Four paths:
    Path 1 LOCAL_VET         — EMERGENCY: nearest vet dispatch (needs farmer consent)
    Path 2 VACCINATION_CHECK — routine: vaccination history check / govt complaint offer
    Path 3 HOME_REMEDY       — mild: safe palliative guidance in Urdu
    Path 4 HELPLINE_PROXY    — autonomous Voice-AI call to the Punjab Livestock Helpline

Also builds the Vapi outbound-call payload (fields verified against Vapi's
official create-call docs: POST https://api.vapi.ai/call) and extracts the
official complaint tracking number from call transcripts.
"""

import re
from typing import Dict, List, Optional
from uuid import UUID

import httpx
from geoalchemy2.functions import ST_Distance, ST_GeogFromText
from sqlalchemy import func, select

from .config import settings
from .models import CaseStatus, DispatchPath, RiskLevel, Veterinarian, VeterinaryCase
from .triage import HOME_CARE_UR

TRACKING_RE = re.compile(r"\bLIV[-\s]?(\d{4})[-\s]?(\d{3,5})\b", re.IGNORECASE)


def recommend_path(triage: Dict) -> DispatchPath:
    """Map triage risk → dispatch path (farmer confirms before execution)."""
    risk = triage["risk"]
    if risk == RiskLevel.EMERGENCY:
        return DispatchPath.LOCAL_VET
    if risk == RiskLevel.HIGH:
        # High risk: vet dispatch, but helpline proxy is offered as an option.
        return DispatchPath.LOCAL_VET
    if risk == RiskLevel.MEDIUM:
        return DispatchPath.VACCINATION_CHECK
    return DispatchPath.HOME_REMEDY


def find_nearest_vets(db, lat: float, lon: float, limit: int = 3) -> List[Dict]:
    """PostGIS nearest-vet query (geography meters → km)."""
    point = ST_GeogFromText(f"SRID=4326;POINT({lon} {lat})")
    dist_m = ST_Distance(Veterinarian.location, point)
    rows = (
        db.execute(
            select(Veterinarian, (dist_m / 1000.0).label("km"))
            .where(Veterinarian.is_active.is_(True), Veterinarian.location.isnot(None))
            .order_by(dist_m)
            .limit(limit)
        )
        .all()
    )
    return [
        {
            "id": vet.id,
            "name": vet.name,
            "phone": vet.phone,
            "tehsil": vet.tehsil,
            "distance_km": round(km, 2),
        }
        for vet, km in rows
    ]


def build_consent_message_ur(vet_name: str, disease_ur: str) -> str:
    return (
        f"Tashkhees ke mutabiq aapke janwar ko {disease_ur} ka khatra hai. "
        f"Kya qareeb tareen {vet_name} ko call mila kar aapke paas bhej doon?"
    )


def case_latlon(db, case_id) -> tuple:
    """Extract (lat, lon) from a case's PostGIS point. Returns (None, None) if absent."""
    row = db.execute(
        select(func.ST_Y(VeterinaryCase.location), func.ST_X(VeterinaryCase.location))
        .where(VeterinaryCase.id == case_id)
    ).first()
    return (row[0], row[1]) if row and row[0] is not None else (None, None)


def build_vet_alert_sms(vet_name: str, disease_ur: str, village: str, tehsil: str,
                        farmer_name: str, farmer_phone: str,
                        lat: Optional[float], lon: Optional[float]) -> str:
    """Phase 4 Path A — SMS/WhatsApp text for the dispatched vet, with map pin."""
    pin = f"https://maps.google.com/?q={lat},{lon}" if lat and lon else "GPS dastiyab nahi"
    return (
        f"PLDHE EMERGENCY: {disease_ur} ka shuba — {village or 'na-maloom chak'}, "
        f"Tehsil {tehsil or 'na-maloom'}. "
        f"Kisan: {farmer_name} ({farmer_phone}). "
        f"Location pin: {pin} — foran raabta karein."
    )


def build_farmer_closure_ur(tracking_no: str, vet_name: Optional[str] = None) -> str:
    """Phase 6 — closing-the-loop message for the farmer (live call or SMS)."""
    msg = ("Chacha, aapki complain government helpline par successfully darj ho gayi hai! "
           f"Aapka official tracking number {tracking_no} hai.")
    if vet_name:
        msg += f" Aur maine qareebi {vet_name} ko bhi alert bhej diya hai."
    msg += " Aapka janwar jald theek ho jaye ga, pareshan na hon."
    return msg


def plan_dispatch(triage: Dict, nearest_vets: List[Dict]) -> Dict:
    """Build the dispatch plan returned to the farmer for confirmation."""
    path = recommend_path(triage)
    plan = {"path": path, "requires_consent": False, "consent_message_ur": "",
            "suggested_vet": None, "home_care_ur": None}

    if path == DispatchPath.LOCAL_VET:
        plan["requires_consent"] = True
        if nearest_vets:
            vet = nearest_vets[0]
            plan["suggested_vet"] = vet
            plan["consent_message_ur"] = build_consent_message_ur(
                vet["name"], triage.get("disease_ur") or "bemari")
    elif path == DispatchPath.HOME_REMEDY:
        plan["home_care_ur"] = HOME_CARE_UR
    elif path == DispatchPath.VACCINATION_CHECK:
        plan["consent_message_ur"] = (
            "Aapke janwar ki vaccination history check kar lete hain. "
            "Agar vaccine miss hui to kya sarkaari shikayat darj kar doon?")
        plan["requires_consent"] = True
    return plan


def build_vapi_payload(case: VeterinaryCase, farmer_name: str, farmer_phone: str,
                       disease_en: Optional[str], professional_address: str,
                       helpline_number: str) -> Dict:
    """Outbound-call body for POST https://api.vapi.ai/call.

    `assistantOverrides.variableValues` injects per-case facts so one
    assistant serves every proxy call.
    """
    return {
        "assistantId": settings.VAPI_ASSISTANT_ID,
        "phoneNumberId": settings.VAPI_PHONE_NUMBER_ID,
        "customer": {"number": helpline_number, "name": "Punjab Livestock Helpline"},
        "assistantOverrides": {
            "variableValues": {
                "case_id": str(case.id),
                "farmer_name": farmer_name,
                "farmer_phone": farmer_phone,
                "disease": disease_en or "unspecified livestock illness",
                "address": professional_address,
            }
        },
    }


def trigger_helpline_proxy_n8n(payload: Dict) -> Dict:
    """Hand the proxy-call job to n8n (recommended — keeps telephony async)."""
    resp = httpx.post(settings.N8N_WEBHOOK_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return {"via": "n8n", "n8n_response": resp.json() if resp.content else {}}


def trigger_helpline_proxy_direct(vapi_payload: Dict) -> Dict:
    """Call Vapi directly from the backend (no n8n hop)."""
    resp = httpx.post(
        "https://api.vapi.ai/call",
        headers={"Authorization": f"Bearer {settings.VAPI_API_KEY}"},
        json=vapi_payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"via": "vapi-direct", "call_id": data.get("id")}


def extract_tracking_number(transcript: Optional[str]) -> Optional[str]:
    """Pull e.g. LIV-2026-9912 out of a helpline call transcript."""
    if not transcript:
        return None
    m = TRACKING_RE.search(transcript.replace(" ", ""))
    if not m:
        m = TRACKING_RE.search(transcript)
    if m:
        return f"LIV-{m.group(1)}-{m.group(2)}".upper()
    return None
