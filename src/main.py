"""FastAPI application: FNOL upload and processing."""
import logging
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.config import settings
from src.schemas import ClaimsProcessingResponse, ExtractedFields
from src.extraction import extract_from_pdf, extract_from_text
from src.routing import compute_route, get_missing_mandatory_fields

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous Insurance Claims Processing Agent",
    description="Extract FNOL fields, detect missing/inconsistent data, classify and route claims.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_extracted(extracted: ExtractedFields) -> ClaimsProcessingResponse:
    """Build assessment-format response from extracted fields."""
    missing = get_missing_mandatory_fields(extracted)
    route, reasoning = compute_route(extracted, missing)
    return ClaimsProcessingResponse(
        extractedFields=extracted.to_flat_dict(),
        missingFields=missing,
        recommendedRoute=route,
        reasoning=reasoning,
    )


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to API docs."""
    return RedirectResponse(url="/docs", status_code=302)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/process", response_model=ClaimsProcessingResponse)
async def process_fnol(file: UploadFile = File(...)):
    """
    Upload a FNOL document (PDF or TXT). Returns extracted fields, missing fields,
    recommended route, and reasoning.
    """
    suffix = (Path(file.filename or "").suffix or "").lower()
    if suffix not in (".pdf", ".txt"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and TXT files are supported.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    try:
        if suffix == ".pdf":
            with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                path = Path(tmp.name)
            try:
                extracted = extract_from_pdf(path)
            finally:
                path.unlink(missing_ok=True)
        else:
            text = content.decode("utf-8", errors="replace")
            extracted = extract_from_text(text)
    except Exception as e:
        logger.exception("Extraction failed")
        raise HTTPException(status_code=422, detail=f"Document processing failed: {e!s}") from e

    return process_extracted(extracted)


class TextInput(BaseModel):
    content: str


@app.post("/api/v1/process/text", response_model=ClaimsProcessingResponse)
async def process_fnol_text(body: TextInput):
    """Process FNOL from raw text (JSON body: {\"content\": \"...\"})."""
    if not (body.content and body.content.strip()):
        raise HTTPException(status_code=400, detail="Empty text.")
    extracted = extract_from_text(body.content)
    return process_extracted(extracted)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
