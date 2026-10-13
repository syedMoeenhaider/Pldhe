"""PLDHE database schema — PostgreSQL + PostGIS.

Tables:
    farmers          — farmer profile + home GPS point
    animals          — livestock owned by a farmer
    veterinarians    — local vets with service-area GPS points
    veterinary_cases — every intake: transcript, symptoms, triage, dispatch state
    vaccinations     — vaccination history (drives Path 2 checks)
    helpline_calls   — audit trail of autonomous proxy calls to the helpline
    outbreak_alerts  — cluster-threshold alerts per tehsil (Module D)
"""

import uuid
from datetime import date, datetime
from enum import Enum

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class RiskLevel(str, Enum):
    EMERGENCY = "EMERGENCY"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CaseStatus(str, Enum):
    RECEIVED = "RECEIVED"
    TRIAGED = "TRIAGED"
    AWAITING_CONSENT = "AWAITING_CONSENT"
    DISPATCHED = "DISPATCHED"
    HELPLINE_PROXY_IN_PROGRESS = "HELPLINE_PROXY_IN_PROGRESS"
    HELPLINE_LOGGED = "HELPLINE_LOGGED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class DispatchPath(str, Enum):
    LOCAL_VET = "LOCAL_VET"                # Path 1 — emergency vet dispatch
    VACCINATION_CHECK = "VACCINATION_CHECK"  # Path 2 — routine / vaccination
    HOME_REMEDY = "HOME_REMEDY"            # Path 3 — mild, palliative guidance
    HELPLINE_PROXY = "HELPLINE_PROXY"      # Path 4 — autonomous helpline call


class Farmer(Base):
    __tablename__ = "farmers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    cnic = Column(String(20), nullable=True)
    preferred_language = Column(String(10), nullable=False, default="ur")  # ur|saraiki|punjabi
    village_text = Column(String(200), nullable=True)  # free-text, e.g. "Chak 111"
    tehsil = Column(String(100), nullable=True)
    district = Column(String(100), nullable=False, default="Layyah")
    location = Column(Geometry("POINT", srid=4326), nullable=True)  # home GPS
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    animals = relationship("Animal", back_populates="farmer", cascade="all, delete-orphan")
    cases = relationship("VeterinaryCase", back_populates="farmer", cascade="all, delete-orphan")


class Animal(Base):
    __tablename__ = "animals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("farmers.id"), nullable=False, index=True)
    species = Column(String(30), nullable=False)  # cow | buffalo | goat | sheep
    breed = Column(String(60), nullable=True)
    age_years = Column(Float, nullable=True)
    sex = Column(String(10), nullable=True)
    tag_id = Column(String(40), nullable=True)

    farmer = relationship("Farmer", back_populates="animals")
    vaccinations = relationship("Vaccination", back_populates="animal", cascade="all, delete-orphan")


class Veterinarian(Base):
    __tablename__ = "veterinarians"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=False)
    tehsil = Column(String(100), nullable=True)  # primary service area
    location = Column(Geometry("POINT", srid=4326), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    specialty = Column(String(120), nullable=True)


class VeterinaryCase(Base):
    __tablename__ = "veterinary_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farmer_id = Column(UUID(as_uuid=True), ForeignKey("farmers.id"), nullable=False, index=True)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("animals.id"), nullable=True)

    intake_channel = Column(String(20), nullable=False, default="live_call")  # live_call|app|sms — live phone/web call is the PRIMARY channel
    audio_path = Column(String(300), nullable=True)
    transcript_original = Column(Text, nullable=True)
    transcript_language = Column(String(10), nullable=True)  # detected: ur|saraiki|punjabi

    symptoms_detected = Column(JSONB, nullable=True)  # ["munh se jhaag", ...]
    suspected_disease = Column(String(120), nullable=True)  # e.g. "Foot and Mouth Disease"
    suspected_disease_ur = Column(String(120), nullable=True)
    risk_level = Column(SAEnum(RiskLevel), nullable=True, index=True)
    triage_confidence = Column(Float, nullable=True)
    triage_explanation = Column(Text, nullable=True)

    location = Column(Geometry("POINT", srid=4326), nullable=True)  # GPS at intake time
    tehsil_resolved = Column(String(100), nullable=True)
    address_professional = Column(String(300), nullable=True)  # for helpline operators

    status = Column(SAEnum(CaseStatus), nullable=False, default=CaseStatus.RECEIVED, index=True)
    dispatch_path = Column(SAEnum(DispatchPath), nullable=True)
    assigned_vet_id = Column(UUID(as_uuid=True), ForeignKey("veterinarians.id"), nullable=True)
    farmer_consent = Column(Boolean, nullable=True)

    complaint_tracking_no = Column(String(40), nullable=True, index=True)  # e.g. LIV-2026-9912

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    farmer = relationship("Farmer", back_populates="cases")
    assigned_vet = relationship("Veterinarian")
    helpline_calls = relationship("HelplineCall", back_populates="case", cascade="all, delete-orphan")


class Vaccination(Base):
    __tablename__ = "vaccinations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    animal_id = Column(UUID(as_uuid=True), ForeignKey("animals.id"), nullable=False, index=True)
    vaccine_name = Column(String(120), nullable=False)  # e.g. "FMD", "HS", "LSD"
    date_given = Column(Date, nullable=False)
    next_due = Column(Date, nullable=True)

    animal = relationship("Animal", back_populates="vaccinations")


class HelplineCall(Base):
    __tablename__ = "helpline_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("veterinary_cases.id"), nullable=False, index=True)
    provider = Column(String(20), nullable=False, default="vapi")
    provider_call_id = Column(String(80), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="initiated")  # initiated|ringing|in-progress|ended|failed
    transcript = Column(Text, nullable=True)
    tracking_number_extracted = Column(String(40), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    case = relationship("VeterinaryCase", back_populates="helpline_calls")


class OutbreakAlert(Base):
    __tablename__ = "outbreak_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tehsil = Column(String(100), nullable=False, index=True)
    disease = Column(String(120), nullable=False)
    case_count = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)
    window_hours = Column(Integer, nullable=False, default=72)
    notified = Column(Boolean, nullable=False, default=False)
    alerted_at = Column(DateTime(timezone=True), server_default=func.now())
