import unittest
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from io import StringIO
from contextlib import redirect_stdout

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.duplicate_analysis import DuplicateAnalysisService
from checks.validators import check_closed_ticket_resolution, check_extra_labels, check_known_expected_label, check_sample_labels, extract_label_values
from src.reporting import add_quality_indicators, build_similarity_report
from src.workflow import export_reports, print_ticket_quality_results


class Week3Tests(unittest.TestCase):
    def test_duplicate_analysis_ranks_similar_ticket_first(self):
        tickets = pd.DataFrame([
            {"Issue key": "ONE-1", "Created": "2026-01-03", "Summary": "Login fails after update", "Description": "Login error"},
            {"Issue key": "ONE-2", "Created": "2026-01-02", "Summary": "Login error after software update", "Description": "Cannot login"},
            {"Issue key": "ONE-3", "Created": "2026-01-01", "Summary": "Export report", "Description": "Create spreadsheet"},
        ])
        result = DuplicateAnalysisService().analyze(tickets.iloc[0].to_dict(), tickets)
        self.assertEqual(result["ranked_matches"][0]["Issue key"], "ONE-2")
        self.assertEqual(len(build_similarity_report(tickets.iloc[0].to_dict(), result)), 2)

    def test_quality_score_uses_all_check_columns(self):
        scored = add_quality_indicators(pd.DataFrame([{"Description Check": "OK", "Priority Check": "WARNING: missing"}]))
        self.assertEqual(scored.loc[0, "Quality Score"], 50.0)
        self.assertEqual(scored.loc[0, "Quality Status"], "NEEDS REVIEW")
        self.assertEqual(scored.loc[0, "Valid_or_Not"], "Valid")

    def test_duplicate_analysis_excludes_future_tickets(self):
        tickets = pd.DataFrame([
            {"Issue key": "ONE-1", "Created": "2026-01-02", "Summary": "Login fails", "Description": "Login error"},
            {"Issue key": "ONE-2", "Created": "2026-01-01", "Summary": "Login error", "Description": "Cannot login"},
            {"Issue key": "ONE-3", "Created": "2026-01-03", "Summary": "Login error", "Description": "Future ticket"},
        ])
        result = DuplicateAnalysisService().analyze(tickets.iloc[0].to_dict(), tickets)
        self.assertEqual([row["Issue key"] for row in result["historical_tickets"].to_dict("records")], ["ONE-2"])

    def test_labels_are_exact_tokens(self):
        self.assertEqual(check_sample_labels("Label_0380"), "WARNING: No sample label found")
        self.assertEqual(extract_label_values(""), [])
        self.assertEqual(extract_label_values(["Label_038", "Label_015"]), ["Label_015", "Label_038"])

    def test_unknown_extra_labels_are_warnings_not_errors(self):
        result = check_extra_labels({"Labels": "Label_003 | Label_999", "Ticket Type": "INFRA"})
        self.assertTrue(result.startswith("WARNING: Undocumented labels found"))
        self.assertNotIn("ERROR", result)
        self.assertEqual(check_known_expected_label({"Labels": "Label_003"}), "OK: INFRA")
        self.assertEqual(check_extra_labels({"Labels": "Label_003"}), "OK: No undocumented labels")

    def test_ticket_type_is_shown_in_terminal_results(self):
        output = StringIO()
        with redirect_stdout(output):
            print_ticket_quality_results({"Summary": "Example", "Ticket Type": "SW_BUG"})
        self.assertIn("Ticket type: SW_BUG", output.getvalue())

    def test_closed_tickets_require_a_resolution(self):
        self.assertEqual(check_closed_ticket_resolution({"Status": "Closed", "Resolution": "Done"}), "OK: Closed ticket is resolved")
        self.assertEqual(check_closed_ticket_resolution({"Status": "Closed", "Resolution": " "}), "WARNING: Closed ticket has no resolution")
        self.assertEqual(check_closed_ticket_resolution({"Status": "Open", "Resolution": ""}), "OK: Ticket is not closed")

    def test_export_reports_does_not_duplicate_existing_results(self):
        report = pd.DataFrame([{"Ticket": "ONE-1"}])
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            output = Path(directory) / "report.xlsx"
            export_reports(output, report, report, report, report)
            export_reports(output, report, report, report, report)

            with pd.ExcelFile(output) as workbook:
                for sheet_name in workbook.sheet_names:
                    saved = pd.read_excel(output, sheet_name=sheet_name)
                    self.assertEqual(len(saved), 1)


if __name__ == "__main__":
    unittest.main()
