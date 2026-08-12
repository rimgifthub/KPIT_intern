import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.duplicate_analysis import DuplicateAnalysisService
from src.reporting import add_quality_indicators, build_similarity_report
from src.workflow import export_reports


class Week3Tests(unittest.TestCase):
    def test_duplicate_analysis_ranks_similar_ticket_first(self):
        tickets = pd.DataFrame([
            {"Issue key": "ONE-1", "Summary": "Login fails after update", "Description": "Login error"},
            {"Issue key": "ONE-2", "Summary": "Login error after software update", "Description": "Cannot login"},
            {"Issue key": "ONE-3", "Summary": "Export report", "Description": "Create spreadsheet"},
        ])
        result = DuplicateAnalysisService().analyze(tickets.iloc[0].to_dict(), tickets)
        self.assertEqual(result["ranked_matches"][0]["Issue key"], "ONE-2")
        self.assertEqual(len(build_similarity_report(tickets.iloc[0].to_dict(), result)), 2)

    def test_quality_score_uses_all_check_columns(self):
        scored = add_quality_indicators(pd.DataFrame([{"Description Check": "OK", "Priority Check": "WARNING: missing"}]))
        self.assertEqual(scored.loc[0, "Quality Score"], 50.0)
        self.assertEqual(scored.loc[0, "Quality Status"], "NEEDS REVIEW")

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
