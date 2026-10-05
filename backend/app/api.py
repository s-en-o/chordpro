"""FastAPI application exposing the PDF-to-ChordPro conversion endpoint."""

from dataclasses import asdict

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from app.adapters.pdf import NoTextLayerError, PdfAdapter
from app.chordpro import serialize
from app.pipeline import convert_layout

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

app = FastAPI(title="ChordPro Converter")


@app.post("/api/convert")
async def convert(file: UploadFile = File(...)) -> JSONResponse:
    """Convert an uploaded PDF into ChordPro text plus a QA report."""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return JSONResponse(status_code=413, content={"error": "file too large"})

    try:
        layout = PdfAdapter().to_layout(data)
    except NoTextLayerError:
        return JSONResponse(
            status_code=400, content={"error": "not a text-based PDF"}
        )

    song = convert_layout(layout)
    return JSONResponse(
        status_code=200,
        content={"chordpro": serialize(song), "qa": asdict(song.qa)},
    )
