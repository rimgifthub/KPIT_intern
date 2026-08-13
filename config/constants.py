from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = PROJECT_ROOT / "local_input_tickets.xlsx"
OUTPUT_FILE = PROJECT_ROOT / "reports" / "local_analysis_output.xlsx"

TICKET_TYPE_MAPPING = {
    "Label_003": "INFRA", 
    "Label_026": "AMTS",
    "Label_034": "REFACTOR_TECHNICA",
    "Label_132": "REFACTOR_OTHER", 
    "Label_015": "SW_BUG"
}

SAMPLE_LABEL_MAPPING = {
    "Label_038": "B0", "Label_055": "B1", "Label_014": "C0",
    "Label_121": "C0", "Label_059": "C1", "Label_066": "D0", "Label_023": "D1"
}

PLACEHOLDERS = [
    "PlaceHolderTCCoBeName", "TCNamePlaceholder",
    "TC where we detected the issue", "<PlaceHolderClassification>"
]

OCCURRENCE_FILTER_TERMS = ["Tickets Occurrence Filter", "Tickets Occurence Filter", "Occurrence Filter"]

VALID_CLASSIFICATIONS = ["Class_001", "Class_002", "Class_003"]
INVALID_CLASSIFICATIONS = ["Class_004"]
CLASS_003_OS_LABELS = ["Label_025", "Label_007"]
CLASS_002_OS_LABELS = ["Label_017", "Label_008"]
CLASSIFICATION_COLUMN_CANDIDATES = ["Custom field (Classification)", "Classification"]

VALID_CATEGORIZATIONS = [f"Category_00{i}" for i in range(1, 8)]

SAMPLE_LABEL_CATEGORIZATION_MAPPING = {
    "Label_038": "Category_001", "Label_055": "Category_005", "Label_014": "Category_003",
    "Label_121": "Category_003", "Label_059": "Category_006", "Label_066": "Category_002",
    "Label_023": "Category_004"
}

MANDATORY_AFFECTS_LABELS = ["Label_015", "Label_004", "Label_133"]

COMMON_ALLOWED_LABELS = [
    "D0_Sample", "D1_Sample", "B0_Sample", "B1_Sample", "C0_Sample", "C1_Sample",
    "Label_007", "Label_008", "Label_014", "Label_017", "Label_023", "Label_025",
    "Label_038", "Label_055", "Label_059", "Label_066", "Label_121"
]

ALLOWED_LABELS_BY_TICKET_TYPE = {
    "INFRA": ["Label_003"],
    "AMTS": ["Label_026"],
    "REFACTOR_TECHNICA": ["Label_034"],
    "REFACTOR_OTHER": ["Label_132"],
    "SW_BUG": [ "Label_015"]
}

# A Jira export may redact URLs, so a literal URL placeholder is not evidence of
# a missing report.  TG validation is only applicable when a ticket refers to
# TG/occurrence-filter information at all.
TG_REPORT_MARKERS = ["TestMgmt", "Occurrence Filter"]
TG_TEXT_COLUMNS = ["Description", "Custom field (Other Text)", "Other Text"]
TC_TEXT_COLUMNS = ["Description", "Custom field (Other Text)", "Other Text"]
FOLLOW_UP_COLUMNS = ["Follow-up", "Follow Up", "Followup", "Custom field (Follow-up)", "Custom field (Follow Up)"]
CRITICAL_PRIORITIES = ["critical", "blocker", "highest"]

DISABLED_CHECKS = [
    "Jira API validation", "JQL execution", "TG API calls", "TG task fetching",
    "TG verdict analysis", "Real branch validation", "Real test case validation",
    "Real user validation", "Pull Request detection"
]

REPRODUCTION_STEP_MARKERS = [
    "steps to reproduce", "reproduction steps", "actions/steps to (re-) produce",
    "actions to reproduce", "how to reproduce",
]
EXPECTED_RESULT_MARKERS = ["expected result", "expected result/behavior", "expected behaviour"]
ATTACHMENT_LOG_MARKERS = ["attachment", "attachments", "log", "logs", "trace", "traces", "[^", "!"]
