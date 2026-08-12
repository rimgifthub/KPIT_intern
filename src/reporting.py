"""Build export-ready duplicate and ticket-quality reports."""

import pandas as pd


def is_passing_result(value):
    return str(value).strip().upper().startswith("OK")


def add_quality_indicators(tickets):
    result = tickets.copy()
    check_columns = [column for column in result.columns if column.endswith(" Check")]
    if not check_columns:
        result["Count_Warnings"] = 0
        result["valid_no_Not"] = "Valid"
        result["Quality Score"] = 0.0
        result["Quality Status"] = "NOT EVALUATED"
        return result
    passed = result[check_columns].map(is_passing_result).sum(axis=1)
    result["Count_Warnings"] = result[check_columns].apply(
        lambda row: row.map(lambda value: str(value).strip().upper().startswith("WARNING")).sum(),
        axis=1,
    )
    result["valid_no_Not"] = result["Count_Warnings"].map(
        lambda warning_count: "Valid" if warning_count == 0 else "Not Valid"
    )
    result["Quality Score"] = (passed / len(check_columns) * 100).round(1)
    result["Quality Status"] = result["Quality Score"].map(lambda score: "PASS" if score == 100 else "NEEDS REVIEW")
    return result


def build_quality_kpis(tickets):
    scored = add_quality_indicators(tickets)
    checks = [column for column in scored.columns if column.endswith(" Check")]
    rows = [
        {"Metric": "Tickets analysed", "Value": len(scored)},
        {"Metric": "Average quality score (%)", "Value": scored["Quality Score"].mean().round(1)},
        {"Metric": "Tickets passed", "Value": int((scored["Quality Status"] == "PASS").sum())},
        {"Metric": "Tickets needing review", "Value": int((scored["Quality Status"] == "NEEDS REVIEW").sum())},
    ]
    rows.extend({"Metric": f"{column} pass rate (%)", "Value": (scored[column].map(is_passing_result).mean() * 100).round(1)} for column in checks)
    return pd.DataFrame(rows)


def build_similarity_report(ticket, duplicate_result):
    ticket_columns = ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID")
    source_id = next((str(ticket[column]) for column in ticket_columns if column in ticket), "UNKNOWN")
    rows = []
    llm_review = duplicate_result.get("llm_review", {})
    for rank, match in enumerate(duplicate_result.get("ranked_matches", []), start=1):
        candidate_id = next((str(match[column]) for column in ticket_columns if column in match), "UNKNOWN")
        score = float(match.get("SimilarityScore", 0))
        review_status = "REVIEW - HIGH SIMILARITY" if score >= 0.7 else "REVIEW - RELATED" if score >= 0.5 else "NO - LOW SIMILARITY"
        rows.append({"Source Ticket": source_id, "Rank": rank, "Candidate Ticket": candidate_id, "Candidate Summary": match.get("Summary", ""), "Similarity Score (%)": round(score * 100, 1), "Potential Duplicate": review_status, "LLM Review Status": llm_review.get("status", "not-run"), "LLM Assessment": llm_review.get("assessment", "")})
    return pd.DataFrame(rows)
