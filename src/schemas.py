"""Pydantic schemas for FNOL extraction and API output."""
from datetime import date as date_type, datetime as datetime_type
from typing import Any, Optional

from pydantic import BaseModel, Field


def _json_serial(val: Any) -> Any:
    """Make values JSON-serializable (e.g. date -> ISO string)."""
    if isinstance(val, (date_type, datetime_type)):
        return val.isoformat()
    return val


# --- Internal extraction models (align with assessment fields) ---


class PolicyInfo(BaseModel):
    """Policy information from FNOL."""

    policy_number: Optional[str] = None
    policyholder_name: Optional[str] = None
    effective_date_start: Optional[date_type] = None
    effective_date_end: Optional[date_type] = None


class IncidentInfo(BaseModel):
    """Incident/loss information."""

    date: Optional[date_type] = None
    time: Optional[str] = None
    location_street: Optional[str] = None
    location_city_state_zip: Optional[str] = None
    location_country: Optional[str] = None
    description: Optional[str] = None


class InvolvedParty(BaseModel):
    """Single party (claimant, third party, contact)."""

    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relation_to_insured: Optional[str] = None


class AssetDetails(BaseModel):
    """Asset (e.g. vehicle) details."""

    asset_type: Optional[str] = None
    asset_id: Optional[str] = None  # VIN, etc.
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    estimated_damage: Optional[float] = None
    initial_estimate: Optional[float] = None


class ExtractedFields(BaseModel):
    """All extracted FNOL fields (assessment output structure)."""

    policy: PolicyInfo = Field(default_factory=PolicyInfo)
    incident: IncidentInfo = Field(default_factory=IncidentInfo)
    claimant: Optional[InvolvedParty] = None
    third_parties: list[InvolvedParty] = Field(default_factory=list)
    contact_details: Optional[InvolvedParty] = None
    asset: Optional[AssetDetails] = None
    claim_type: Optional[str] = None
    attachments: list[str] = Field(default_factory=list)
    initial_estimate: float | None = None

    def to_flat_dict(self) -> dict[str, Any]:
        """Flatten for JSON output as extractedFields."""
        out: dict[str, Any] = {}
        for k, v in self.policy.model_dump(exclude_none=True).items():
            out[f"policy_{k}"] = v
        for k, v in self.incident.model_dump(exclude_none=True).items():
            out[f"incident_{k}"] = v
        if self.claimant:
            for k, v in self.claimant.model_dump(exclude_none=True).items():
                out[f"claimant_{k}"] = v
        for i, p in enumerate(self.third_parties):
            for k, v in p.model_dump(exclude_none=True).items():
                out[f"third_party_{i}_{k}"] = v
        if self.contact_details:
            for k, v in self.contact_details.model_dump(exclude_none=True).items():
                out[f"contact_{k}"] = v
        if self.asset:
            for k, v in self.asset.model_dump(exclude_none=True).items():
                out[f"asset_{k}"] = v
        if self.claim_type is not None:
            out["claim_type"] = self.claim_type
        if self.attachments:
            out["attachments"] = self.attachments
        if self.initial_estimate is not None:
            out["initial_estimate"] = self.initial_estimate
        return {k: _json_serial(v) for k, v in out.items()}


# --- Mandatory field names for routing (missing → manual review) ---

MANDATORY_FIELDS = [
    "policy_number",
    "policyholder_name",
    "incident_date",
    "incident_location",
    "incident_description",
    "claim_type",
    "initial_estimate_or_estimated_damage",
]


# --- API response (assessment output format) ---


class ClaimsProcessingResponse(BaseModel):
    """Response format per assessment: extractedFields, missingFields, recommendedRoute, reasoning."""

    extractedFields: dict[str, Any] = Field(default_factory=dict)
    missingFields: list[str] = Field(default_factory=list)
    recommendedRoute: str = ""
    reasoning: str = ""
