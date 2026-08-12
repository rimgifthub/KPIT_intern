"""Text-similarity helpers used to rank possible duplicate tickets."""

from functools import lru_cache
from contextlib import redirect_stderr, redirect_stdout
import io
import os
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _clean_text(value):
    """Normalize Jira markup into compact plain text."""
    text = "" if value is None else str(value)
    text = text.replace("_x000D_", "\n").replace("\\r", "\n")
    text = re.sub(r"\[([^\]|]+)(?:\|[^\]]*)?\]", r"\1", text)
    text = re.sub(r"[{}*]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_section(description, start_pattern, end_patterns):
    """Extract one useful Jira section while avoiding the standard template."""
    match = re.search(start_pattern, description, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    content = description[match.end():]
    end_positions = [
        end_match.start()
        for pattern in end_patterns
        if (end_match := re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL))
    ]
    if end_positions:
        content = content[:min(end_positions)]
    return _clean_text(content)


def extract_ticket_evidence(summary, description):
    """Return the issue-specific evidence and omit repeated Jira boilerplate."""
    raw_description = "" if description is None else str(description).replace("_x000D_", "\n")
    evidence = []
    if _clean_text(summary):
        evidence.append(f"Summary: {_clean_text(summary)}")

    error_keyword = re.search(r"\|\s*\*?Error Keyword\*?\s*\|([^|\n]+)", raw_description, flags=re.IGNORECASE)
    if error_keyword:
        evidence.append(f"Error keyword: {_clean_text(error_keyword.group(1))}")

    section_boundaries = [
        r"\*?(?:Expected result|Actual result|Observation|Screenshot|Traces|Preconditions|Actions/steps)"
    ]
    for label, start_pattern in (
        ("Steps", r"\*?Actions/steps to \(re-\) produce the problem:?\*?"),
        ("Expected result", r"\*?Expected result/behavior:?\*?"),
        ("Actual result", r"\*?Actual result/behavior:?\*?"),
        ("Observation", r"\*?Observation:?\*?"),
    ):
        section = _extract_section(raw_description, start_pattern, section_boundaries)
        if section:
            evidence.append(f"{label}: {section}")

    # If structured fields are absent, keep only non-template prose lines.
    if len(evidence) == 1:
        useful_lines = []
        for line in raw_description.splitlines():
            cleaned_line = _clean_text(line)
            if not cleaned_line or line.lstrip().startswith("|"):
                continue
            if any(marker in cleaned_line.casefold() for marker in ("trace", "dashboard", "attachment", "ticket occurrence filter", "testmgmt")):
                continue
            useful_lines.append(cleaned_line)
        if useful_lines:
            evidence.append("Details: " + " ".join(useful_lines[:8]))

    return "\n".join(evidence)


def build_comparison_text(summary, description):
    """Create comparison text from issue-specific evidence, not Jira boilerplate."""
    return extract_ticket_evidence(summary, description)


def get_tfidf_similarity_scores(current_text, historical_texts):
    """Return cosine-similarity scores for the current ticket and each prior ticket."""
    if not historical_texts:
        return []
    documents = [current_text or ""] + [text or "" for text in historical_texts]
    if not any(document.strip() for document in documents):
        return [0.0] * len(historical_texts)

    matrix = TfidfVectorizer(stop_words="english").fit_transform(documents)
    return cosine_similarity(matrix[0:1], matrix[1:]).flatten().tolist()


@lru_cache(maxsize=1)
def _load_embedding_model(model_name):
    """Load and cache a sentence-transformers model for the current process."""
    from sentence_transformers import SentenceTransformer

    # Transformers may display its own loading progress even when encoding
    # progress is disabled. Keep the command-line interface concise.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return SentenceTransformer(model_name, local_files_only=os.getenv("JIRA_ALLOW_MODEL_DOWNLOAD", "").casefold() not in {"1", "true", "yes"})


def download_embedding_model(model_name=None):
    """Download the configured embedding model into the local Hugging Face cache."""
    model = model_name or os.getenv("JIRA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    try:
        import certifi
        ca_bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
    except ImportError:
        pass
    from sentence_transformers import SentenceTransformer

    SentenceTransformer(model, local_files_only=False)
    _load_embedding_model.cache_clear()
    return model

def get_sentence_embedding_similarity_scores(current_text, historical_texts, model_name=None, model=None):
    """Return semantic cosine-similarity scores using sentence embeddings."""
    if not historical_texts:
        return []

    documents = [current_text or ""] + [text or "" for text in historical_texts]
    if not any(document.strip() for document in documents):
        return [0.0] * len(historical_texts)

    embedding_model = model or _load_embedding_model(
        model_name or os.getenv("JIRA_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
    )
    max_length = int(os.getenv("JIRA_EMBEDDING_MAX_SEQ_LENGTH", "128"))
    if hasattr(embedding_model, "max_seq_length"):
        embedding_model.max_seq_length = min(embedding_model.max_seq_length, max_length)
    embeddings = embedding_model.encode(
        documents,
        batch_size=int(os.getenv("JIRA_EMBEDDING_BATCH_SIZE", "64")),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return (embeddings[0] @ embeddings[1:].T).tolist()


def get_similarity_scores(current_text, historical_texts, model_name=None):
    """Prefer semantic embeddings and fall back to TF-IDF when unavailable."""
    try:
        return get_sentence_embedding_similarity_scores(current_text, historical_texts, model_name), "sentence-embedding"
    except (ImportError, ModuleNotFoundError, OSError):
        return get_tfidf_similarity_scores(current_text, historical_texts), "tfidf-fallback"


def sort_similarity_results(records):
    """Sort ticket records from most to least similar."""
    return sorted(records, key=lambda record: record.get("SimilarityScore", 0), reverse=True)


