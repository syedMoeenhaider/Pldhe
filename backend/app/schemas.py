"""Pydantic request/response contracts for the PLDHE API."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .models import CaseStatus, DispatchPath, RiskLevel


class TriageResult(BaseModel):
    disease_en: Optional[str] = None
    disease_ur: Optional[str] = None
    risk: RiskLevel = RiskLevel.LOW
    confidence: float = 0.0
    matched_symptoms: List[str] = []
    explanation: str = ""


class DispatchPlan(BaseModel):
    path: DispatchPath
    requires_consent: bool = False
    consent_message_ur: str = ""
    suggested_vet: Optional[dict] = None
    home_care_ur: Optional[str] = None


class IntakeResponse(BaseModel):
    case_id: UUID
    status: CaseStatus
    triage: TriageResult
    tehsil_resolved: Optional[str] = None
    address_professional: Optional[str] = None
    dispatch: DispatchPlan


class DispatchConsentRequest(BaseModel):
    consent: bool = Field(description="Farmer said yes/no to the proposed dispatch")
    path: Optional[DispatchPath] = None  # override the recommended path


class CaseSummary(BaseModel):
    id: UUID
    farmer_phone: str
    suspected_disease: Optional[str]
    risk_level: Optional[RiskLevel]
    status: CaseStatus
    tehsil_resolved: Optional[str]
    complaint_tracking_no: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NearbyVet(BaseModel):
    id: UUID
    name: str
    phone: str
    tehsil: Optional[str]
    distance_km: float


class HeatmapPoint(BaseModel):
    lat: float
    lon: float
    disease: Optional[str]
    risk: Optional[RiskLevel]


class HelplineProxyRequest(BaseModel):
    helpline_number: Optional[str] = None  # defaults to settings.HELPLINE_NUMBER
    use_n8n: bool = True  # False → call Vapi directly from backend


class LiveTriageRequest(BaseModel):
    """Mid-call triage — the Vapi intake assistant's function-tool payload."""

    text: str = Field(description="Farmer's spoken symptoms so far in the live call")
    language_hint: str = "saraiki"


class VapiCallbackPayload(BaseModel):
    """Subset of the Vapi end-of-call / status-update webhook body we care about."""

    call_id: Optional[str] = Field(default=None, alias="id")
    status: Optional[str] = None
    ended_reason: Optional[str] = Field(default=None, alias="endedReason")
    transcript: Optional[str] = None
    summary: Optional[str] = None
    case_id: Optional[UUID] = None  # we pass it via assistantOverrides variable

    model_config = {"populate_by_name": True}
