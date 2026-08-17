"""Rank likely duplicate Jira tickets using semantic sentence similarity."""

import pandas as pd

from src.duplicate_detector import CREATED_COLUMNS, get_historical_tickets
from src.duplicate_llm import build_duplicate_llm_prompt, review_duplicate_candidates
from src.similarity import (
    build_comparison_text,
    get_similarity_scores,
    sort_similarity_results,
)


TOP_DUPLICATE_CANDIDATES = 5
TICKET_ID_COLUMNS = ["Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID"]


class DuplicateAnalysisService:
    """Find, optionally review, and format the most similar historical tickets."""

    def __init__(self, top_n=TOP_DUPLICATE_CANDIDATES, use_llm=False):
        self.top_n = top_n
        self.use_llm = use_llm

    def analyze(self, ticket, all_tickets):
        created_column = next((column for column in CREATED_COLUMNS if column in all_tickets.columns), None)
        if created_column is None:
            return self._not_performed(
                all_tickets,
                "Duplicate analysis not performed — creation-date column is missing.",
            )
        if pd.isna(pd.to_datetime(ticket.get(created_column), errors="coerce")):
            return self._not_performed(
                all_tickets,
                "Duplicate analysis not performed — creation date missing or invalid.",
            )

        historical_tickets = get_historical_tickets(ticket, all_tickets)
        if historical_tickets.empty:
            return {
                "historical_tickets": historical_tickets,
                "ranked_matches": [],
                "llm_prompt": "",
                "llm_review": {"status": "not-run", "assessment": "No historical tickets were found."},
                "similarity_method": "sentence-embedding",
                "analysis_status": "completed",
                "analysis_message": "No historical tickets were found.",
            }

        current_text = build_comparison_text(ticket.get("Summary"), ticket.get("Description"))
        historical_texts = historical_tickets.apply(
            lambda row: build_comparison_text(row.get("Summary"), row.get("Description")),
            axis=1,
        ).tolist()
        scores, similarity_method = get_similarity_scores(current_text, historical_texts)
        ranked_matches = sort_similarity_results(
            historical_tickets.assign(SimilarityScore=scores).to_dict(orient="records")
        )[: self.top_n]
        llm_prompt = build_duplicate_llm_prompt(ticket, ranked_matches, max_candidates=self.top_n)
        if self.use_llm:
            print("Requesting local LLM duplicate review...")
        llm_review = review_duplicate_candidates(llm_prompt) if self.use_llm else {
            "status": "not-run",
            "assessment": "Local LLM review was not requested.",
        }
        return {
            "historical_tickets": historical_tickets,
            "ranked_matches": ranked_matches,
            "llm_prompt": llm_prompt,
            "llm_review": llm_review,
            "similarity_method": similarity_method,
            "analysis_status": "completed",
            "analysis_message": "Duplicate analysis completed.",
        }

    @staticmethod
    def _not_performed(all_tickets, message):
        """Return an explicit result when chronological comparison is impossible."""
        return {
            "historical_tickets": all_tickets.iloc[0:0].copy(),
            "ranked_matches": [],
            "llm_prompt": "",
            "llm_review": {"status": "not-run", "assessment": message},
            "similarity_method": "not-performed",
            "analysis_status": "not-performed",
            "analysis_message": message,
        }

    def format_summary(self, ticket, duplicate_result):
        if duplicate_result.get("analysis_status") == "not-performed":
            return duplicate_result["analysis_message"]
        ranked_matches = duplicate_result.get("ranked_matches", [])
        if not ranked_matches:
            return "No historical duplicate candidates were found."

        lines = ["Top similarity matches:"]
        for match in ranked_matches:
            ticket_id = next(
                (
                    str(match[column]).strip()
                    for column in TICKET_ID_COLUMNS
                    if column in match and match[column] is not None and str(match[column]).strip()
                ),
                "UNKNOWN",
            )
            lines.append(f"- {ticket_id}: {match.get('SimilarityScore', 0):.2%}")
        llm_review = duplicate_result.get("llm_review", {})
        if llm_review.get("status") != "not-run":
            lines.extend(["", f"Local LLM review ({llm_review.get('status', 'unknown')}):", llm_review.get("assessment", "")])
        return "\n".join(lines)
