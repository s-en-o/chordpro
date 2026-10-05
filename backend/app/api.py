"""FastAPI application exposing the PDF-to-ChordPro conversion endpoint."""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.adapters.ocr import OcrAdapter
from app.adapters.pdf import NoTextLayerError, PdfAdapter
from app.chordpro import serialize
from app.pipeline import convert_layout

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="ChordPro Converter")


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
    """Convert an uploaded PDF into ChordPro text plus a QA report."""
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=413, content={"error": "file too large"})

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=413, content={"error": "file too large"})

    used_ocr = False
    try:
        layout = await run_in_threadpool(PdfAdapter().to_layout, data)
    except NoTextLayerError:
        # No text layer (scanned or vector-outlined page): fall back to OCR.
        try:
            layout = await run_in_threadpool(OcrAdapter().to_layout, data)
            used_ocr = True
        except NoTextLayerError:
            return JSONResponse(
                status_code=400, content={"error": "not a text-based PDF"}
            )

    song = await run_in_threadpool(convert_layout, layout)
    qa = asdict(song.qa)
    if used_ocr:
        qa["notes"].append(
            "No text layer found; this file was read with OCR. "
            "Please review the result carefully."
        )
    return JSONResponse(
        status_code=200,
        content={"chordpro": serialize(song), "qa": qa},
    )


# In the Docker image the built frontend is copied to /app/frontend_dist.
# Locally, this path simply won't exist, so we only mount it when present.
_STATIC_DIR = Path(__file__).resolve().parent.parent / "frontend_dist"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
