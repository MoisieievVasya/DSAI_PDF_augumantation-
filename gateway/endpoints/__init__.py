from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from services.generate_service import generate_response
from services.evaluate_service import evaluate_response

router = APIRouter()

@router.post("/generate-pdf")
async def generate_pdf(
    prompt: str = Form(...),
    pdf_files: Optional[List[UploadFile]] = File(None),
    images: Optional[List[UploadFile]] = File(None)
):
    file_bytes = b""
    if pdf_files:
        for f in pdf_files:
            file_bytes += await f.read()
    elif images:
        for img in images:
            file_bytes += await img.read()

    result_pdf_path = generate_response(file_bytes, prompt)
    return FileResponse(result_pdf_path, media_type="application/pdf", filename="generated_invoice.pdf")

@router.post("/evaluate")
def eval(payload: dict):
    df, metrics = evaluate_response(payload)
    return {
        "table": df.to_dict(orient="records"),
        "metrics": metrics
    }