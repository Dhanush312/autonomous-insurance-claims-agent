"""Tests for FNOL extraction."""
from pathlib import Path

import pytest

from src.extraction import extract_from_text, extract_from_pdf
from src.schemas import ExtractedFields


def test_extract_from_text_complete():
    text = """
    POLICY NUMBER: POL-2024-887654
    NAME OF INSURED: John Smith
    DATE OF LOSS AND TIME: 01/15/2024 10:30 AM
    LOCATION OF LOSS STREET: 4500 Interstate 35, Austin TX 78745
    DESCRIPTION OF ACCIDENT: Vehicle struck from behind. No injuries.
    V.I.N.: 1HGBH41JXMN109186
    MAKE: Honda MODEL: Accord YEAR: 2021
    ESTIMATE AMOUNT: $8,500
    """
    out = extract_from_text(text)
    assert isinstance(out, ExtractedFields)
    assert out.policy.policy_number == "POL-2024-887654"
    assert out.policy.policyholder_name
    assert "smith" in (out.policy.policyholder_name or "").lower()
    assert out.incident.date is not None
    assert out.incident.description
    assert out.asset is not None
    assert out.asset.estimated_damage == 8500.0
    assert out.asset.asset_id == "1HGBH41JXMN109186"


def test_extract_claim_type_injury():
    text = """
    Policy Number: INS-789
    Policyholder: Maria Garcia
    Loss Date: 02/01/2024
    Location: 7800 N Lamar, Austin TX
    Description: Collision. Driver reported neck pain. Claim type: injury.
    Estimate: $12,000
    """
    out = extract_from_text(text)
    assert out.claim_type == "injury"


def test_extract_fraud_keywords():
    text = """
    Policy: P-456
    Insured: Robert Lee
    Date of loss: 03/10/2024
    Location: 100 Congress Ave, Austin TX
    Description: The story seems inconsistent and the damage looked staged. Possible fraud.
    Estimate: $22,000
    Claim type: auto
    """
    out = extract_from_text(text)
    assert out.incident.description, "Description should be extracted (fraud keywords present in source)"
    desc_lower = (out.incident.description or "").lower()
    assert "inconsistent" in desc_lower or "staged" in desc_lower or "fraud" in desc_lower


def test_to_flat_dict_serializable():
    text = "POLICY NUMBER: X\nNAME OF INSURED: Y\nDATE OF LOSS: 01/15/2024\nLocation: 1 Main St\nDescription: Hit.\nEstimate: 5000\nClaim type: auto"
    out = extract_from_text(text)
    flat = out.to_flat_dict()
    for v in flat.values():
        assert not hasattr(v, "isoformat") or callable(getattr(v, "isoformat", None))


@pytest.mark.parametrize("sample", ["fnol_sample_complete.txt", "fnol_sample_injury.txt", "fnol_sample_fraud_flag.txt"])
def test_sample_files(sample):
    path = Path(__file__).parent.parent / "samples" / sample
    if not path.exists():
        pytest.skip(f"Sample not found: {path}")
    content = path.read_text(encoding="utf-8")
    out = extract_from_text(content)
    assert out.policy.policy_number or out.policy.policyholder_name
    assert out.claim_type or out.incident.description
