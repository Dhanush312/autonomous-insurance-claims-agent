"""Routing rules: Fast-track, Manual review, Investigation Flag, Specialist Queue."""
import re

from src.schemas import ExtractedFields
from src.config import settings


# Phrases that trigger investigation (assessment: fraud, inconsistent, staged)
INVESTIGATION_KEYWORDS = re.compile(
    r"\b(fraud|inconsistent|staged)\b",
    re.IGNORECASE,
)


def get_missing_mandatory_fields(extracted: ExtractedFields) -> list[str]:
    """Return list of missing mandatory field names for routing (manual review if any)."""
    missing: list[str] = []
    p = extracted.policy
    i = extracted.incident
    if not (p.policy_number and p.policy_number.strip()):
        missing.append("policy_number")
    if not (p.policyholder_name and p.policyholder_name.strip()):
        missing.append("policyholder_name")
    if not i.date:
        missing.append("incident_date")
    loc = (i.location_street or "").strip() or (i.location_city_state_zip or "").strip()
    if not loc:
        missing.append("incident_location")
    if not (i.description and i.description.strip()):
        missing.append("incident_description")
    if not (extracted.claim_type and extracted.claim_type.strip()):
        missing.append("claim_type")
    damage = None
    if extracted.asset:
        damage = extracted.asset.estimated_damage or extracted.asset.initial_estimate
    if extracted.initial_estimate is not None:
        damage = extracted.initial_estimate
    if damage is None:
        missing.append("initial_estimate_or_estimated_damage")
    return missing


def compute_route(
    extracted: ExtractedFields,
    missing: list[str],
    threshold: float | None = None,
) -> tuple[str, str]:
    """
    Apply assessment routing rules. Returns (recommended_route, reasoning).
    Rules (order matters):
    1. Any mandatory field missing → Manual review
    2. Description contains fraud/inconsistent/staged → Investigation Flag
    3. Claim type = injury → Specialist Queue
    4. Estimated damage < threshold (default 25,000) → Fast-track
    5. Else → Standard
    """
    if threshold is None:
        threshold = settings.fast_track_damage_threshold
    reasons: list[str] = []

    if missing:
        return (
            "Manual review",
            f"Missing mandatory field(s): {', '.join(missing)}. Cannot auto-route.",
        )

    desc = (extracted.incident.description or "").strip()
    if INVESTIGATION_KEYWORDS.search(desc):
        return (
            "Investigation Flag",
            "Description contains terms suggesting possible fraud or inconsistency; flagged for investigation.",
        )

    if (extracted.claim_type or "").strip().lower() == "injury":
        return (
            "Specialist Queue",
            "Claim type is injury; routed to specialist queue.",
        )

    damage = None
    if extracted.asset:
        damage = extracted.asset.estimated_damage or extracted.asset.initial_estimate
    if extracted.initial_estimate is not None:
        damage = extracted.initial_estimate
    if damage is not None and damage < threshold:
        return (
            "Fast-track",
            f"Estimated damage ({damage}) is below threshold ({threshold}); eligible for fast-track.",
        )

    return (
        "Standard",
        "All mandatory fields present; no special flags; above fast-track threshold; routed to standard workflow.",
    )
