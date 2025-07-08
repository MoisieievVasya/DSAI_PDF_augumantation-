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

    result_pdf_path, filled_json = generate_response(file_bytes, prompt)

    # Save filled JSON for possible reuse
    with open(result_pdf_path + ".json", "w") as jf:
        import json
        json.dump(filled_json, jf)

    return FileResponse(result_pdf_path, media_type="application/pdf", filename="generated_invoice.pdf")

@router.post("/evaluate")
async def eval():
    result = evaluate_response()
    return result