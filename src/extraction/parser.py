"""Extract structured FNOL fields from PDF and plain text (ACORD-aware)."""
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from src.schemas import (
    AssetDetails,
    ExtractedFields,
    IncidentInfo,
    InvolvedParty,
    PolicyInfo,
)


def _extract_text_from_pdf(path: Path) -> str:
    """Extract raw text from PDF using PyMuPDF."""
    doc = fitz.open(path)
    parts = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    return "\n".join(parts)


def _parse_date(s: str | None) -> date | None:
    if not s or not s.strip():
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(s: str | None) -> float | None:
    if s is None:
        return None
    s = re.sub(r"[^\d.]", "", s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_year(s: str | None) -> int | None:
    if not s:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", s)
    return int(m.group(0)) if m else None


# Known ACORD/form labels that must not be stored as extracted values (blank forms)
_LABEL_PATTERNS = re.compile(
    r"^(OTHER|STREET:|CITY,?\s*STATE,?\s*ZIP:?|NAME\s+OF\s+INSURED|INSURED'S\s+MAILING|"
    r"PRIMARY\s+PHONE|SECONDARY\s+E-MAIL|PRIMARY\s+E-MAIL|DRIVER'S\s+NAME|OWNER'S\s+NAME|"
    r"CHECK\s+IF\s+SAME|PHONE\s*#|CELL|HOME|BUS|LOSS\s*$|ACORD\s+101|ADDITIONAL\s+REMARKS|"
    r"INSURED\s+VEHICLE|SECONDARY|PRIMARY|NUMBER|VEHICLE)$",
    re.IGNORECASE,
)
_LABEL_SUBSTRINGS = (
    "same as owner", "same as insured", "mailing address", "additional remarks",
    "may be attached", "if more space", "check if same", "phone #", "e-mail address",
    "if not at specific", "street address", "(first, middle, last)", "first, middle, last",
)


def _is_form_label_or_placeholder(value: str | None, max_reasonable_len: int = 200) -> bool:
    """Return True if value looks like a form label/placeholder, not real data."""
    if not value or not value.strip():
        return True
    s = value.strip()
    # Single colon or only punctuation
    if s in (":", "") or re.match(r"^[\s.:\-]+$", s):
        return True
    if len(s) > max_reasonable_len and "\n" in s and s.count("\n") > 2:
        return True  # Long multi-line blob is likely concatenated labels
    if _LABEL_PATTERNS.match(s):
        return True
    lower = s.lower()
    if any(sub in lower for sub in _LABEL_SUBSTRINGS):
        return True
    # Placeholder words when they are the whole value (e.g. "number" for policy number)
    if lower in ("number", "name", "date", "address", "other"):
        return True
    if s.upper() == "OTHER" or s.upper() == "Y" or s.upper() == "N":
        return True
    return False


def _extract_from_raw_text(text: str) -> ExtractedFields:
    """Parse raw FNOL text (ACORD-style and generic) into ExtractedFields."""
    policy = PolicyInfo()
    incident = IncidentInfo()
    claimant: InvolvedParty | None = None
    asset: AssetDetails | None = None
    claim_type: str | None = None
    initial_estimate: float | None = None
    attachments: list[str] = []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    full = text.upper()
    # Normalize for keyword search
    lower = text.lower()

    # --- Policy ---
    for pattern, setter in [
        (r"POLICY\s*NUMBER[:\s]*([A-Za-z0-9\-]+)", lambda m: setattr(policy, "policy_number", m.group(1).strip())),
        (r"NAIC\s*CODE[:\s]*\S+\s*CARRIER[:\s]*\S+\s*POLICY\s*NUMBER[:\s]*([^\s\n]+)", lambda m: setattr(policy, "policy_number", m.group(1).strip())),
    ]:
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()
            if not _is_form_label_or_placeholder(val, max_reasonable_len=50):
                policy.policy_number = val

    if not policy.policy_number:
        m = re.search(r"(?:policy\s*#?|policy\s*number)\s*[:\s]*([A-Za-z0-9\-]+)", lower)
        if m:
            val = m.group(1).strip()
            if not _is_form_label_or_placeholder(val, max_reasonable_len=50):
                policy.policy_number = val

    # Policyholder / Insured name (ACORD: NAME OF INSURED)
    m = re.search(r"NAME\s+OF\s+INSURED\s*\([^)]*\)\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()[:200]
        if not _is_form_label_or_placeholder(val):
            policy.policyholder_name = val
    if not policy.policyholder_name:
        m = re.search(r"(?:insured|policyholder)\s*(?:name)?\s*[:\s]*([^\n]+)", lower)
        if m:
            val = m.group(1).strip()[:200]
            if not _is_form_label_or_placeholder(val):
                policy.policyholder_name = val

    # --- Incident ---
    m = re.search(r"DATE\s+OF\s+LOSS\s+AND\s+TIME\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        part = m.group(1)
        d = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", part)
        if d:
            incident.date = _parse_date(d.group(1))
        t = re.search(r"(\d{1,2}\s*:\s*\d{2}\s*(?:AM|PM)?|\d{1,2}\s*AM|\d{1,2}\s*PM)", part, re.IGNORECASE)
        if t:
            incident.time = t.group(1).strip()

    if not incident.date:
        m = re.search(r"(?:loss\s+date|date\s+of\s+loss|incident\s+date)\s*[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", lower)
        if m:
            incident.date = _parse_date(m.group(1))

    # Location
    m = re.search(r"LOCATION\s+OF\s+LOSS\s*(?:STREET[:\s]*)?([^\n]+?)(?:\s*CITY|$)", text, re.IGNORECASE | re.DOTALL)
    if m:
        val = m.group(1).strip()[:300]
        if not _is_form_label_or_placeholder(val):
            incident.location_street = val
    m = re.search(r"CITY,?\s*STATE,?\s*ZIP[:\s]*([^\n]+)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if not _is_form_label_or_placeholder(val, max_reasonable_len=100):
            incident.location_city_state_zip = val
    m = re.search(r"COUNTRY[:\s]*([^\n]+)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if not _is_form_label_or_placeholder(val, max_reasonable_len=80):
            incident.location_country = val

    # Description (reject when it's clearly form labels concatenated)
    m = re.search(r"DESCRIPTION\s+OF\s+ACCIDENT\s*([^\n]+(?:\n(?!POLICY|INSURED|LOCATION|DATE)[^\n]+)*)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()[:2000]
        if not _is_form_label_or_placeholder(val, max_reasonable_len=2000):
            incident.description = val
    if not incident.description:
        m = re.search(r"(?:description\s+of\s+(?:loss|accident)|accident\s+description)\s*[:\s]*([^\n]+(?:\n[^\n]+)*?)(?=\n[A-Z\s]{3,}:|\n\n|$)", lower, re.DOTALL)
        if m:
            val = m.group(1).strip()[:2000]
            if not _is_form_label_or_placeholder(val, max_reasonable_len=2000):
                incident.description = val
    if not incident.description:
        m = re.search(r"Description(?:\s+of\s+(?:loss|accident))?\s*[:\s]*([^\n]+(?:\n[^\n]+)*)", text, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()[:2000]
            if not _is_form_label_or_placeholder(val, max_reasonable_len=2000):
                incident.description = val

    # Location fallback (generic "Location:")
    if not (incident.location_street or incident.location_city_state_zip):
        m = re.search(r"Location(?:\s+of\s+loss)?\s*[:\s]*([^\n]+)", text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()[:300]
            if not _is_form_label_or_placeholder(val):
                incident.location_street = val

    # --- Claimant / Driver / Owner (ACORD) ---
    m = re.search(r"DRIVER'S\s+NAME\s+AND\s+ADDRESS\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        val = m.group(1).strip()
        if not _is_form_label_or_placeholder(val):
            claimant = InvolvedParty(name=val)
    if not claimant:
        m = re.search(r"OWNER'S\s+NAME\s+AND\s+ADDRESS\s*([^\n]+)", text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if not _is_form_label_or_placeholder(val):
                claimant = InvolvedParty(name=val)
    if not claimant and policy.policyholder_name:
        claimant = InvolvedParty(name=policy.policyholder_name)

    # Phone/email from CONTACT or PRIMARY PHONE
    m = re.search(r"PRIMARY\s+PHONE\s*#\s*[:\s]*([^\n]+)", text, re.IGNORECASE)
    if m and claimant:
        val = m.group(1).strip()[:50]
        if not _is_form_label_or_placeholder(val, max_reasonable_len=30):
            claimant.phone = val
    m = re.search(r"PRIMARY\s+E-MAIL\s*[:\s]*([^\s\n@]+@[^\s\n]+)", text, re.IGNORECASE)
    if m and claimant:
        claimant.email = m.group(1).strip()

    # --- Asset (vehicle) ---
    vin = re.search(r"V\.?I\.?N\.?[:\s]*([A-HJ-NPR-Z0-9]{17})", text, re.IGNORECASE)
    make = re.search(r"MAKE[:\s]*([^\n\t]+?)(?:\s+YEAR|\s+MODEL|$)", text, re.IGNORECASE)
    model = re.search(r"MODEL[:\s]*([^\n\t]+?)(?:\s+BODY|\s+TYPE|$)", text, re.IGNORECASE)
    year = re.search(r"YEAR[:\s]*(\d{4})", text, re.IGNORECASE)
    est = re.search(r"ESTIMATE\s+AMOUNT[:\s]*([^\n]+)", text, re.IGNORECASE)
    if not est:
        est = re.search(r"(?:Estimate|initial\s+estimate)\s*[:\s]*([^\n]+)", text, re.IGNORECASE)
    if vin or make or model or year or est:
        make_val = make.group(1).strip() if make else None
        if make_val and _is_form_label_or_placeholder(make_val, max_reasonable_len=50):
            make_val = None
        model_val = model.group(1).strip() if model else None
        if model_val and _is_form_label_or_placeholder(model_val, max_reasonable_len=50):
            model_val = None
        asset = AssetDetails(
            asset_type="vehicle",
            asset_id=vin.group(1).strip() if vin else None,
            make=make_val,
            model=model_val,
            year=int(year.group(1)) if year else None,
            estimated_damage=_parse_float(est.group(1)) if est else None,
            initial_estimate=_parse_float(est.group(1)) if est else None,
        )
    if asset:
        if asset.initial_estimate is None and asset.estimated_damage is not None:
            asset.initial_estimate = asset.estimated_damage
        initial_estimate = asset.initial_estimate or asset.estimated_damage

    # --- Claim type --- (infer injury only from description narrative, not section headers)
    desc_for_type = (incident.description or "").lower()
    if desc_for_type and ("injury" in desc_for_type or "injured" in desc_for_type):
        claim_type = "injury"
    elif "vehicle" in lower or "automobile" in lower or "auto" in lower or "ACORD" in full:
        claim_type = "auto"
    else:
        claim_type = "property"

    # Attachments (mention in text)
    if "attachment" in lower or "attached" in lower:
        attachments.append("document_attached")

    return ExtractedFields(
        policy=policy,
        incident=incident,
        claimant=claimant,
        third_parties=[],
        contact_details=claimant,
        asset=asset,
        claim_type=claim_type,
        attachments=attachments or [],
        initial_estimate=asset.initial_estimate if asset else initial_estimate,
    )


def extract_from_pdf(file_path: Path) -> ExtractedFields:
    """Extract FNOL fields from a PDF file."""
    text = _extract_text_from_pdf(file_path)
    return _extract_from_raw_text(text)


def extract_from_text(content: str) -> ExtractedFields:
    """Extract FNOL fields from plain text content."""
    return _extract_from_raw_text(content)
