""" validation, duplicate detection, and Excel reporting."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

import config.constants as const
from checks import validators as val
from src.duplicate_analysis import DuplicateAnalysisService
from src.similarity import download_embedding_model
from src.reporting import add_quality_indicators, build_quality_kpis, build_similarity_report


def apply_quality_checks(tickets):
    """Apply the configured validation rules and calculate ticket-quality scores."""
    df = tickets.copy()
    required_columns = ["Labels", "Description", "Priority", "Custom field (Categorization)", "Affects Version/s"]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError("Input workbook is missing required columns: " + ", ".join(missing))

    df["Ticket Type"] = df["Labels"].apply(val.detect_ticket_type)
    df["Sample Label Check"] = df["Labels"].apply(val.check_sample_labels)
    df["Description Check"] = df["Description"].apply(val.check_description)
    df["Reproduction Steps Check"] = df["Description"].apply(val.check_reproduction_steps)
    df["Expected Result Check"] = df["Description"].apply(val.check_expected_results)
    df["Attachments and Logs Check"] = df["Description"].apply(val.check_attachments_or_logs)
    df["Occurrence Filter Description Check"] = df["Description"].apply(val.check_occurrence_filter_description)
    classification_column = next((column for column in const.CLASSIFICATION_COLUMN_CANDIDATES if column in df.columns), None)
    df["Classification Check"] = df.apply(lambda row: val.check_classification(row, classification_column), axis=1)
    df["Priority Check"] = df["Priority"].apply(val.check_priority)
    df["Closed Ticket Resolution Check"] = df.apply(val.check_closed_ticket_resolution, axis=1)
    df["Categorization Check"] = df["Custom field (Categorization)"].apply(val.check_categorization)
    df["Sample Label Categorization Check"] = df.apply(val.check_sample_label_categorization, axis=1)
    df["Affects Version Check"] = df.apply(val.check_affects_version, axis=1)
    df["Expected Ticket Type Label Check"] = df.apply(val.check_known_expected_label, axis=1)
    df["Extra Label Check"] = df.apply(val.check_extra_labels, axis=1)
    df["TG Report Check"] = df.apply(val.check_tg_report_markers, axis=1)
    df["Infra Process Check"] = df.apply(val.check_infra_process, axis=1)
    df["TC Check"] = df.apply(val.check_tc_validation, axis=1)
    return add_quality_indicators(df)


def find_ticket(tickets, ticket_id):
    """Find one ticket using the supported Jira key-column names."""
    key_column = next((column for column in ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID") if column in tickets.columns), None)
    if key_column is None:
        raise ValueError("Input workbook has no Jira ticket key column.")
    requested_id = ticket_id.strip()
    if requested_id.casefold() in {"your-123", "your-ticket-key", "ticket-key"}:
        examples = ", ".join(tickets[key_column].dropna().astype(str).head(5).tolist())
        raise ValueError(f"'{ticket_id}' is a placeholder. Use a real ticket key, for example: {examples}")
    match = tickets[tickets[key_column].astype(str).str.strip().str.casefold() == requested_id.casefold()]
    if match.empty:
        examples = ", ".join(tickets[key_column].dropna().astype(str).head(5).tolist())
        raise ValueError(f"Ticket '{ticket_id}' was not found. Check the key or use one from the workbook, for example: {examples}")
    return match.iloc[0].to_dict()


def print_ticket_information(ticket, ticket_id):
    """Print the main details of the selected Jira ticket."""
    fields = [
        ("Issue Key", ticket_id),
        ("Summary", ticket.get("Summary", "")),
        ("Issue Type", ticket.get("Issue Type", "")),
        ("Status", ticket.get("Status", "")),
        ("Priority", ticket.get("Priority", "")),
        ("Assignee", ticket.get("Assignee", "")),
        ("Labels", ticket.get("Labels", "")),
        ("Quality Score", f"{ticket.get('Quality Score', 0)}% ({ticket.get('Quality Status', 'NOT EVALUATED')})"),
    ]
    print("\n" + "=" * 64)
    print("TICKET INFORMATION")
    print("=" * 64)
    for label, value in fields:
        text = "Not provided" if pd.isna(value) or not str(value).strip() else str(value).strip()
        if len(text) > 90:
            text = text[:87] + "..."
        print(f"{label:<15}: {text}")
    print("=" * 64)

def print_analysis_summary(quality_dataset, duplicate_result, quality_kpis):
    """Show completion of the requested analysis deliverables in the terminal."""
    ranked_matches = duplicate_result.get("ranked_matches", [])
    potential_duplicates = sum(float(match.get("SimilarityScore", 0)) >= 0.5 for match in ranked_matches)
    method = duplicate_result.get("similarity_method", "unknown")
    historical_count = len(duplicate_result.get("historical_tickets", []))
    kpis = dict(zip(quality_kpis["Metric"], quality_kpis["Value"]))

    print("\n" + "=" * 64)
    print("ANALYSIS COMPLETION SUMMARY")
    print("=" * 64)
    print(f"Historical tickets analysed     : {historical_count}")
    print(f"Text similarity method         : {method}")
    print(f"Duplicate candidates detected  : {potential_duplicates} of {len(ranked_matches)} top matches (score >= 50%)")
  
    print(f"Quality indicators generated   : {len(quality_dataset)} tickets")
    print(f"Average quality score          : {kpis.get('Average quality score (%)', 0)}%")
    print(f"Tickets passed / needing review: {kpis.get('Tickets passed', 0)} / {kpis.get('Tickets needing review', 0)}")
    print("=" * 64)


def print_analysis_dashboard(ticket_id, ticket_count, duplicate_result, ticket):
    """Present duplicate results in a concise, readable terminal layout."""
    ranked_matches = duplicate_result.get("ranked_matches", [])
    method = duplicate_result.get("similarity_method", "tfidf-fallback")
    model_message = "Model loaded successfully" if method == "sentence-embedding" else "Using TF-IDF similarity fallback"

    print("\n" + "=" * 60)
    print("              JIRA TICKET ANALYSIS")
    print("=" * 60)
    print(f"\n[OK] {model_message}")
    print(f"[OK] {ticket_count} tickets loaded")
    print(f"[OK] Analysing ticket: {ticket_id}")
    print_ticket_quality_results(ticket)
    print("\n" + "-" * 60)
    print("TOP SIMILAR TICKETS")
    print("-" * 60)
    print(f"{'Rank':<7}{'Ticket':<13}{'Similarity':>12}")
    print(f"{'-' * 4:<7}{'-' * 10:<13}{'-' * 10:>12}")
    if not ranked_matches:
        print("No historical tickets are available for comparison.")
    else:
        for rank, match in enumerate(ranked_matches, start=1):
            match_id = next(
                (str(match[column]).strip() for column in ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID") if column in match),
                "UNKNOWN",
            )
            print(f"{rank:<7}{match_id:<13}{float(match.get('SimilarityScore', 0)):>12.2%}")
    llm_review = duplicate_result.get("llm_review", {})
    if llm_review.get("status") != "not-run":
        print("\n" + "-" * 60)
        print("LOCAL LLM DUPLICATE REVIEW")
        print("-" * 60)
        print(f"Status: {llm_review.get('status', 'unknown')}")
        print(f"Model: {llm_review.get('model', 'Not available')}")
        print(llm_review.get("assessment", "No assessment returned."))
    print("\n" + "-" * 60)
    print("Analysis completed successfully.")
    print("-" * 60)


def print_ticket_quality_results(ticket):
    """Show all validation results for the selected ticket in a readable table."""
    check_columns = [column for column in ticket if column.endswith(" Check")]
    print("\n" + "-" * 60)
    print("TICKET QUALITY RESULTS")
    print("-" * 60)
    print(f"Summary: {str(ticket.get('Summary', 'Not provided'))[:90]}")
    print(f"Ticket type: {ticket.get('Ticket Type', 'Not detected')}")
    print(f"Quality score: {ticket.get('Quality Score', 0)}%")
    print(f"Warnings: {ticket.get('Count_Warnings', 0)}")
    print(f"Validity: {ticket.get('Valid_or_Not', 'Not evaluated')}")
    print("\n" + f"{'Check':<35} Result")
    print(f"{'-' * 35}  {'-' * 45}")
    for column in check_columns:
        check_name = column.removesuffix(" Check")
        result = str(ticket.get(column, ""))
        if len(result) > 60:
            result = result[:57] + "..."
        print(f"{check_name:<35} {result}")

def export_reports(output_file, quality_dataset, quality_kpis, ticket_report, similarity_report):
    """Save reports while keeping only one result for each Jira ticket."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    reports = {
        "Quality KPI Dataset": quality_dataset,
        "Quality KPIs": quality_kpis,
        "Selected Ticket": ticket_report,
        "Similarity Report": similarity_report,
    }
    ticket_already_exists = False
    if output_path.exists():
        with pd.ExcelFile(output_path) as workbook:
            if "Selected Ticket" in workbook.sheet_names:
                existing_tickets = pd.read_excel(workbook, sheet_name="Selected Ticket")
                key_column = next((column for column in ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID") if column in ticket_report.columns and column in existing_tickets.columns), None)
                if key_column is not None and not ticket_report.empty:
                    ticket_key = str(ticket_report.iloc[0][key_column]).strip().casefold()
                    ticket_already_exists = existing_tickets[key_column].astype(str).str.strip().str.casefold().eq(ticket_key).any()

    if not output_path.exists():
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, report in reports.items():
                report.to_excel(writer, sheet_name=sheet_name, index=False)
        return ticket_already_exists

    with pd.ExcelWriter(output_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        for sheet_name, report in reports.items():
            if sheet_name not in writer.book.sheetnames:
                report.to_excel(writer, sheet_name=sheet_name, index=False)
                continue
            existing = pd.read_excel(output_path, sheet_name=sheet_name)
            combined = pd.concat([existing, report], ignore_index=True)
            if sheet_name in {"Quality KPI Dataset", "Selected Ticket"}:
                key_column = next((column for column in ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID") if column in combined.columns), None)
                if key_column is not None:
                    combined = combined.drop_duplicates(subset=key_column, keep="last")
            elif sheet_name == "Similarity Report":
                unique_columns = [column for column in ("Source Ticket", "Rank") if column in combined.columns]
                if unique_columns:
                    combined = combined.drop_duplicates(subset=unique_columns, keep="last")
            elif sheet_name == "Quality KPIs" and "Metric" in combined.columns:
                combined = combined.drop_duplicates(subset="Metric", keep="last")
            combined = combined.drop_duplicates(keep="last")
            combined.to_excel(writer, sheet_name=sheet_name, index=False)
    return ticket_already_exists


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assess Jira ticket quality and find likely duplicates.")
    parser.add_argument("--input", "-i", default=const.INPUT_FILE, help="Source Jira export workbook (.xlsx).")
    parser.add_argument("--output", "-o", default=const.OUTPUT_FILE, help="Output report workbook (.xlsx).")
    parser.add_argument("--ticket", "-t", help="Jira ticket key to analyse. Omit for an interactive prompt.")
    parser.add_argument("--top", type=int, default=5, help="Number of duplicate candidates to report.")
    parser.add_argument("--llm", action="store_true", help="Use a local Ollama model to review duplicate candidates.")
    parser.add_argument("--download-embedding-model", action="store_true", help="Download the sentence-embedding model, then exit.")
    parser.add_argument("--list-tickets", action="store_true", help="List Jira ticket keys in the input workbook, then exit.")
    args = parser.parse_args(argv)

    if args.download_embedding_model:
        try:
            model = download_embedding_model()
        except Exception as error:
            parser.error(f"Could not download the embedding model: {error}")
        print(f"Embedding model ready: {model}")
        return

    source = pd.read_excel(args.input)
    if args.list_tickets:
        key_column = next((column for column in ("Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID") if column in source.columns), None)
        if key_column is None:
            parser.error("Input workbook has no Jira ticket key column.")
        for ticket_key in source[key_column].dropna().astype(str):
            print(ticket_key)
        return
    quality_dataset = apply_quality_checks(source)
    ticket_id = args.ticket
    while True:
        ticket = None
        is_command_line_ticket = ticket_id is not None
        while ticket is None:
            if ticket_id is None:
                ticket_id = input("\nEnter Issue Key to analyse: ").strip()
            if not ticket_id:
                print("A Jira ticket key is required.")
                ticket_id = None
                continue
            normalized_input = ticket_id.casefold()
            if normalized_input in {"q", "quit", "exit"}:
                print("Ticket analysis cancelled.")
                return
            if "python.exe" in normalized_input or normalized_input.endswith(".py"):
                print("The checker is already running. At this prompt, enter only a Jira key such as ISSUE_001.")
                print("Returning to PowerShell.")
                return
            try:
                ticket = find_ticket(quality_dataset, ticket_id)
            except ValueError as error:
                if is_command_line_ticket:
                    parser.error(str(error))
                print(f"{error} Enter a Jira key , not a Python command.")
                ticket_id = None

        duplicate_result = DuplicateAnalysisService(top_n=args.top, use_llm=args.llm).analyze(ticket, quality_dataset)
        similarity_report = build_similarity_report(ticket, duplicate_result)
        selected_ticket = pd.DataFrame([ticket])
        quality_kpis = build_quality_kpis(quality_dataset)

        print_analysis_dashboard(ticket_id, len(quality_dataset), duplicate_result, ticket)

        while True:
            save_choice = input("\nSave results to Excel? [Yes/No]: ").strip().casefold()
            if save_choice in {"yes", "y"}:
                try:
                    already_exists = export_reports(args.output, quality_dataset, quality_kpis, selected_ticket, similarity_report)
                except PermissionError:
                    print(f"Cannot save because this Excel file is open: {Path(args.output).resolve()}")
                    print("Close the workbook in Excel, then choose Yes again.")
                    continue
                print("\n[OK] Report saved successfully:")
                print(f"  {Path(args.output).resolve()}")
                if already_exists:
                    print(f"Ticket {ticket_id} already exists in the report. No duplicate ticket entry was added.")
                else:
                    print(f"Ticket {ticket_id} was added to the report.")
                break
            if save_choice in {"no", "n"}:
                print("Results were not saved.")
                break
            print("Please enter Yes or No.")

        # Keep the program open so the next Jira key can be analysed immediately.
        ticket_id = None
if __name__ == "__main__":
    main()
