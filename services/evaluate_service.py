import re
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from nltk.tokenize import sent_tokenize
import nltk

nltk.download("punkt")
nltk.download("punkt_tab")

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

def distinct_n_scores(generated_texts, n_list=[1, 2, 3]):
    scores = {}
    for n in n_list:
        ngrams = []
        for text in generated_texts:
            tokens = str(text).split()
            ngrams += [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]
        total = len(ngrams)
        unique = len(set(ngrams))
        scores[f"distinct-{n}"] = unique / total if total > 0 else 0
    return scores

def sentence_overlap_coherence(text):
    sentences = sent_tokenize(text)
    overlaps = []
    for i in range(len(sentences) - 1):
        words_a = set(sentences[i].lower().split())
        words_b = set(sentences[i+1].lower().split())
        if words_a and words_b:
            overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
            overlaps.append(overlap)
    return sum(overlaps) / len(overlaps) if overlaps else 0

def batch_coherence(generated_texts):
    clean_texts = [str(t) for t in generated_texts if isinstance(t, str) and len(t.split()) > 2]
    return [sentence_overlap_coherence(text) for text in clean_texts]

def evaluate_response(data: dict, similarity_threshold=0.3):
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

    semantic_only = df[df["Note"] != "RULE-BASED"]
    avg_semantic = semantic_only["Cosine Similarity"].mean()
    avg_all = df["Cosine Similarity"].mean()
    low_sim = semantic_only[semantic_only["Cosine Similarity"] < similarity_threshold]
    invalid_format = df[df["Format Valid"] == False]

    texts = list(data.values())
    distinct = distinct_n_scores(texts)
    coherence_scores = batch_coherence(texts)
    avg_coherence = sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0

    print("📊 Evaluation Summary")
    print(f"→ Avg cosine similarity (semantic fields): {avg_semantic:.3f}")
    print(f"→ Avg cosine similarity (ALL fields): {avg_all:.3f}")
    print(f"→ Fields with low semantic match (<{similarity_threshold}): {len(low_sim)}")
    print(f"→ Fields with invalid format: {len(invalid_format)}")
    print("→ Distinct-N:", distinct)
    print(f"→ Avg coherence: {avg_coherence:.3f}")

    return df, {
        "avg_semantic_similarity": avg_semantic,
        "avg_cosine_all": avg_all,
        "low_similarity_count": len(low_sim),
        "invalid_format_count": len(invalid_format),
        "distinct_scores": distinct,
        "avg_coherence": avg_coherence
    }