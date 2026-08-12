"""Build prompts and obtain optional local-LLM duplicate assessments."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.similarity import extract_ticket_evidence


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
MAX_FIELD_LENGTH = 700


def _short_text(value, limit=MAX_FIELD_LENGTH):
    """Keep local-model prompts fast and bounded for long Jira fields."""
    text = "" if value is None else str(value).strip()
    return text if len(text) <= limit else text[:limit] + " ...[truncated]"

def build_duplicate_llm_prompt(ticket, ranked_matches, max_candidates=5):
    """Build a focused prompt for a model to assess likely duplicate tickets."""
    if not ranked_matches:
        return ""

    current_evidence = _short_text(extract_ticket_evidence(ticket.get("Summary", ""), ticket.get("Description", "")))
    candidates = []
    for match in ranked_matches[:max_candidates]:
        ticket_id = next(
            (match[key] for key in ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID") if key in match),
            "UNKNOWN",
        )
        candidates.append(
            "\n".join(
                [
                    f"Candidate: {ticket_id}",
                    f"Similarity score: {float(match.get('SimilarityScore', 0)):.1%}",
                    f"Issue-specific evidence: {_short_text(extract_ticket_evidence(match.get('Summary', ''), match.get('Description', '')))}",
                ]
            )
        )

    return "\n".join(
        [
            "You are reviewing Jira tickets for possible duplicates.",
            "Compare the actual issue-specific evidence only. Ignore generic Jira templates, trace tables, links, labels, and shared project wording.",
            "Do not treat a similarity score as proof. State the best candidate ID (or NONE), a verdict of DUPLICATE, RELATED, or NOT_DUPLICATE, and a concise reason.",
            "Current ticket evidence:",
            current_evidence,
            "Candidates:",
            "\n\n".join(candidates),
        ]
    )


def review_duplicate_candidates(prompt, model_name=None, base_url=None, timeout=None):
    """Ask a local Ollama model to review candidates without sending data to a cloud API."""
    if not prompt:
        return {"status": "not-run", "assessment": "No duplicate candidates were available."}

    model = model_name or os.getenv("JIRA_LLM_MODEL", DEFAULT_OLLAMA_MODEL)
    # Local CPU inference can take several minutes for a ticket plus five
    # detailed candidates, especially on the first request after model load.
    timeout = timeout or int(os.getenv("JIRA_LLM_TIMEOUT", "240"))
    endpoint = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)).rstrip("/") + "/api/generate"
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 150},
        }
    ).encode("utf-8")
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return {
            "status": "complete",
            "model": body.get("model", model),
            "assessment": body.get("response", "").strip(),
        }
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        return {
            "status": "unavailable",
            "model": model,
            "assessment": f"Local LLM was not available: {error}",
        }
