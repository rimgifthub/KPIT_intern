"""Build export-ready duplicate and ticket-quality reports."""

import pandas as pd


def is_passing_result(value):
    return str(value).strip().upper().startswith("OK")


def is_error_result(value):
    return str(value).strip().upper().startswith("ERROR")


def is_warning_result(value):
    return str(value).strip().upper().startswith("WARNING")


def add_quality_indicators(tickets):
    result = tickets.copy()
    # Older exports used a misspelled validity column.  Do not carry it into
    # new reports; Valid_or_Not is the single authoritative validity field.
    legacy_validity_columns = [
        column for column in result.columns if str(column).casefold() == "valid_no_not"
    ]
    if legacy_validity_columns:
        result = result.drop(columns=legacy_validity_columns)
    check_columns = [column for column in result.columns if column.endswith(" Check")]
    if not check_columns:
        result["Count_Warnings"] = 0
        result["Valid_or_Not"] = "Valid"
        result["Quality Score"] = 0.0
        result["Quality Status"] = "NOT EVALUATED"
        return result
    passed = result[check_columns].map(is_passing_result).sum(axis=1)
    result["Count_Warnings"] = result[check_columns].apply(lambda row: row.map(is_warning_result).sum(), axis=1)
    result["Count_Errors"] = result[check_columns].apply(lambda row: row.map(is_error_result).sum(), axis=1)
    # Warnings identify missing information for review. Only an explicit rule
    # violation (ERROR) makes a ticket invalid.
    result["Valid_or_Not"] = result["Count_Errors"].map(
        lambda count: "Not Valid" if count else "Valid"
    )
    result["Quality Score"] = (passed / len(check_columns) * 100).round(1)
    result["Quality Status"] = result.apply(lambda row: "PASS" if row["Count_Errors"] == 0 and row["Count_Warnings"] == 0 else "NEEDS REVIEW", axis=1)
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
    if duplicate_result.get("analysis_status") == "not-performed":
        return pd.DataFrame([{
            "Source Ticket": source_id,
            "Rank": "",
            "Candidate Ticket": "",
            "Candidate Summary": "",
            "Similarity Score (%)": "",
            "Potential Duplicate": "NOT ANALYSED",
            "LLM Review Status": llm_review.get("status", "not-run"),
            "LLM Assessment": duplicate_result.get("analysis_message", "Duplicate analysis not performed."),
        }])
    for rank, match in enumerate(duplicate_result.get("ranked_matches", []), start=1):
        candidate_id = next((str(match[column]) for column in ticket_columns if column in match), "UNKNOWN")
        score = float(match.get("SimilarityScore", 0))
        review_status = "REVIEW - HIGH SIMILARITY" if score >= 0.7 else "REVIEW - RELATED" if score >= 0.5 else "NO - LOW SIMILARITY"
        rows.append({"Source Ticket": source_id, "Rank": rank, "Candidate Ticket": candidate_id, "Candidate Summary": match.get("Summary", ""), "Similarity Score (%)": round(score * 100, 1), "Potential Duplicate": review_status, "LLM Review Status": llm_review.get("status", "not-run"), "LLM Assessment": llm_review.get("assessment", "")})
    return pd.DataFrame(rows)
