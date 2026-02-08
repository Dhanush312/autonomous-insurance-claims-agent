"""Tests for routing engine."""
import pytest

from src.schemas import ExtractedFields, PolicyInfo, IncidentInfo, AssetDetails, InvolvedParty
from src.routing import get_missing_mandatory_fields, compute_route


def _minimal_extracted(
    policy_number="P1",
    policyholder_name="John",
    incident_date=None,
    location="123 Main St",
    description="Hit",
    claim_type="auto",
    estimated_damage=10000.0,
):
    from datetime import date
    policy = PolicyInfo(policy_number=policy_number, policyholder_name=policyholder_name)
    incident = IncidentInfo(
        date=incident_date or date(2024, 1, 15),
        location_street=location,
        description=description,
    )
    asset = AssetDetails(estimated_damage=estimated_damage, initial_estimate=estimated_damage) if estimated_damage is not None else None
    return ExtractedFields(
        policy=policy,
        incident=incident,
        claimant=InvolvedParty(name=policyholder_name),
        asset=asset,
        claim_type=claim_type,
        initial_estimate=estimated_damage,
    )


def test_missing_fields_empty_when_complete():
    ext = _minimal_extracted()
    missing = get_missing_mandatory_fields(ext)
    assert missing == []


def test_missing_fields_policy_number():
    ext = _minimal_extracted(policy_number="")
    missing = get_missing_mandatory_fields(ext)
    assert "policy_number" in missing


def test_missing_fields_estimated_damage():
    ext = _minimal_extracted(estimated_damage=None)
    ext.initial_estimate = None
    ext.asset = None
    missing = get_missing_mandatory_fields(ext)
    assert "initial_estimate_or_estimated_damage" in missing


def test_route_manual_review_when_missing():
    ext = _minimal_extracted(policy_number="")
    missing = get_missing_mandatory_fields(ext)
    route, reason = compute_route(ext, missing)
    assert route == "Manual review"
    assert "Missing" in reason or "missing" in reason


def test_route_fast_track():
    ext = _minimal_extracted(estimated_damage=10000.0)
    missing = get_missing_mandatory_fields(ext)
    route, reason = compute_route(ext, missing, threshold=25000)
    assert route == "Fast-track"
    assert "25" in reason or "fast" in reason.lower()


def test_route_investigation_flag():
    ext = _minimal_extracted(description="The incident appears staged and the account is inconsistent. Possible fraud.")
    missing = get_missing_mandatory_fields(ext)
    route, reason = compute_route(ext, missing)
    assert route == "Investigation Flag"
    assert "fraud" in reason.lower() or "investigation" in reason.lower()


def test_route_specialist_injury():
    ext = _minimal_extracted(claim_type="injury", description="Collision with injury.")
    ext.incident.description = "Collision with injury."
    missing = get_missing_mandatory_fields(ext)
    route, reason = compute_route(ext, missing)
    assert route == "Specialist Queue"
    assert "injury" in reason.lower() or "specialist" in reason.lower()


def test_route_standard_above_threshold():
    ext = _minimal_extracted(estimated_damage=50000.0)
    missing = get_missing_mandatory_fields(ext)
    route, reason = compute_route(ext, missing, threshold=25000)
    assert route == "Standard"
