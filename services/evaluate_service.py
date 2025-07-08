import json
import tempfile
from pathlib import Path

import pdfplumber

import openai
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re
import pandas as pd

import config

DEFAULT_PDF  = Path("/app/augmented.pdf")
DEFAULT_JSON = Path("/app/augmented.pdf.json")

def evaluate_response():

    pdf_text = extract_text_from_pdf(DEFAULT_PDF)

    json_path = Path(DEFAULT_JSON)
    if not json_path.exists():
        raise FileNotFoundError(f"{json_path} not found")
    payload_bytes = json_path.read_bytes()

    try:
        payload_json = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError("`payload_bytes` must contain valid JSON data.") from exc

    diversity_scores = augmentation_diversity([pdf_text])

    df = field_coherence(payload_json)

    doc_coh = document_coherence(pdf_text)

    semantic_only = df[df["Note"] != "RULE-BASED"]
    avg_semantic = semantic_only["Cosine Similarity"].mean()
    avg_all = df["Cosine Similarity"].mean()
    low_sim_cnt = semantic_only[semantic_only["Cosine Similarity"] < 0.3].shape[0]
    invalid_fmt_cnt = df[df["Format Valid"] == False].shape[0]

    metrics = {
        **diversity_scores,
        "avg_semantic_similarity": round(avg_semantic, 3) if pd.notna(avg_semantic) else None,
        "avg_all_similarity": round(avg_all, 3) if pd.notna(avg_all) else None,
        "low_similarity_fields": int(low_sim_cnt),
        "invalid_format_fields": int(invalid_fmt_cnt),
        "document_coherence": round(doc_coh, 3) if doc_coh is not None else None
    }

    return {
        "table": df.to_dict(orient="records"),
        "metrics": metrics
    }


def augmentation_diversity(generated_texts, n_list=[1, 2, 3]):
    scores = {}
    for n in n_list:
        ngrams = []
        for text in generated_texts:
            tokens = text.split()
            ngrams += [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]
        total = len(ngrams)
        unique = len(set(ngrams))
        scores[f"distinct-{n}"] = unique / total if total > 0 else 0
    return scores


client = openai.OpenAI(api_key=config.get_required_env(config.OPEN_AI_KEY_ENV))

encoder = SentenceTransformer('all-MiniLM-L6-v2')


def is_valid_email(val): return bool(re.match(r"[^@]+@[^@]+\.[^@]+", val))


def is_valid_date(val): return bool(re.match(r"\d{4}-\d{2}-\d{2}", val))


def is_valid_phone(val): return bool(re.match(r"\+?[\d\s\-\(\)]+", val))


def is_number(val): return bool(re.match(r"^\$?\d+(\.\d+)?%?$", val))


TECHNICAL_KEYWORDS = [
    "email", "e-mail", "phone", "tel", "mobile", "iban", "swift", "id", "sku",
    "date", "due", "discount", "total", "amount", "cost", "price", "quantity", "number", "tax"
]


def is_technical_field(key: str):
    key = key.lower()
    return any(word in key for word in TECHNICAL_KEYWORDS)


def validate_field_format(key, value):
    key = key.lower()
    value = str(value).strip()

    if any(word in key for word in ["email", "e-mail"]):
        return is_valid_email(value), True
    elif any(word in key for word in ["date", "due"]):
        return is_valid_date(value), True
    elif any(word in key for word in ["phone", "tel", "mobile"]):
        return is_valid_phone(value), True
    elif any(word in key for word in ["tax", "iban", "swift", "id", "sku"]):
        return len(value) > 5, True
    elif any(word in key for word in ["amount", "total", "price", "discount", "cost", "quantity", "subtotal"]):
        return is_number(value), True
    return True, False


def field_coherence(data: dict, similarity_threshold=0.3):
    results = []

    for key, val in data.items():
        format_valid, is_rule_based = validate_field_format(key, val)

        if is_rule_based or is_technical_field(key):
            cosine_val = 1.0 if format_valid else 0.0
            note = "RULE-BASED"
        else:
            key_emb = encoder.encode(key.replace("_", " ").lower())
            val_emb = encoder.encode(str(val))
            cosine_val = cosine_similarity([key_emb], [val_emb])[0][0]
            note = ""

        results.append((key, cosine_val, format_valid, note))

    df = pd.DataFrame(results, columns=["Field", "Cosine Similarity", "Format Valid", "Note"])

    # Averages
    semantic_only = df[df["Note"] != "RULE-BASED"]
    avg_semantic = semantic_only["Cosine Similarity"].mean()
    avg_all = df["Cosine Similarity"].mean()

    low_sim = semantic_only[semantic_only["Cosine Similarity"] < similarity_threshold]
    invalid_format = df[df["Format Valid"] == False]

    print("📊 Evaluation Summary")
    print(f"→ Avg cosine similarity (semantic fields): {avg_semantic:.3f}")
    print(f"→ Avg cosine similarity (ALL fields): {avg_all:.3f}")
    print(f"→ Fields with low semantic match (<{similarity_threshold}): {len(low_sim)}")
    print(f"→ Fields with invalid format: {len(invalid_format)}")

    return df.sort_values("Cosine Similarity")


def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


SYSTEM_PROMPT = (
    "You are a strict text–quality evaluator. "
    "When the user gives you a document, respond with ONLY a number "
    "between 0 and 1 that reflects its overall coherence. "
    "0 = totally incoherent, 1 = perfectly coherent."
)


def document_coherence(text, model="gpt-3.5-turbo"):
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
             "content": f"Rate coherence (0-1):\n\n{text}"}
        ],
        temperature=0
    )
    score_str = resp.choices[0].message.content.strip()

    m = re.search(r"[01](?:\.\d+)?", score_str)
    return float(m.group()) if m else None
