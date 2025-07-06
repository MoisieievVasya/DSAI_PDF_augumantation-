import tempfile
import config
import json
import re
import pdfplumber
import pikepdf
from openai import OpenAI
from pikepdf import Stream, Array


def generate_response(file_bytes: bytes, prompt: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    structure = extract_template(tmp_path)

    filled = generate_content_openai(structure, prompt=prompt)

    out_pdf = merge_filled_content(tmp_path, filled)
    return out_pdf

def extract_template(pdf_path):
    """Витягає текст та поля {{field}} із PDF."""
    structure = {"pages": []}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            fields = re.findall(r"{{(.*?)}}", text)
            structure["pages"].append({
                "page_number": i,
                "text": text,
                "fields": fields
            })
    return structure
def generate_content_openai(template_struct, prompt=""):
    """Заповнює поля за допомогою OpenAI GPT (v1 SDK)."""
    openai_model = "gpt-3.5-turbo"
    client = OpenAI(api_key=config.get_required_env(config.OPEN_AI_KEY_ENV))
    prompt_text = (
        f"You are given a JSON template structure. Fill each placeholder with appropriate text and "
        f"ONLY output the filled fields as a JSON object mapping field names to content. "
        f"Template: {json.dumps(template_struct, ensure_ascii=False)}"
    )
    resp = client.chat.completions.create(
        model=openai_model,
        messages=[
            {"role": "system", "content": "Fill the JSON template fields and output pure JSON."},
            {"role": "user", "content": prompt_text}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    content = resp.choices[0].message.content.strip()
    print("Raw OpenAI response:", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        import re as _re
        match = _re.search(r"\{[\s\S]*\}", content)
        if match:
            return json.loads(match.group(0))
        raise

def merge_filled_content(pdf_path, filled_json, output_pdf_path="augmented.pdf"):
    pdf = pikepdf.open(pdf_path)

    for page_idx, page in enumerate(pdf.pages, start=1):
        contents = page.obj["/Contents"]
        streams = [contents] if isinstance(contents, Stream) else list(contents)

        patched_streams = []
        for stream in streams:
            raw = stream.read_bytes()
            text = raw.decode("latin-1", errors="ignore")

            # 1) Find & print any placeholders
            found = re.findall(r"\{\{(.*?)\}\}", text)
            if found:
                print(f"[DEBUG] Page {page_idx}: placeholders found → {found}")

            # 2) Replace them
            for field, replacement in filled_json.items():
                print(field, replacement)
                if not isinstance(replacement, str):
                    replacement = json.dumps(replacement, ensure_ascii=False)
                pattern = r"\{\{\s*"+re.escape(field)+r"\s*\}\}"
                text = re.sub(pattern, replacement, text)

            # 3) Build a new Stream for writing
            patched_streams.append(Stream(pdf, text.encode("latin-1")))

        # 4) Re‑assign the page’s /Contents
        if isinstance(contents, Array):
            page.obj["/Contents"] = Array(patched_streams)
        else:
            page.obj["/Contents"] = patched_streams[0]

    pdf.save(output_pdf_path)
    return output_pdf_path