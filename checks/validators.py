import os
import sys

import re
import pandas as pd

# Direct execution (``python checks/validators.py``) sets ``checks`` as the
# import root. Add the project root so sibling packages remain importable.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.constants import *
from utils.helpers import get_text, get_first_available_text, collect_text


LABEL_PATTERN = re.compile(r"(?<![A-Za-z0-9_])Label_\d+(?![A-Za-z0-9_])")


def is_blank(value):
    """Safely identify blank scalar or collection values from Excel exports."""
    if value is None:
        return True
    if isinstance(value, (list, tuple, set)):
        return not any(not is_blank(item) for item in value)
    return bool(pd.isna(value)) or not str(value).strip()


def parse_labels(labels):
    """Return exact anonymised label tokens from a Jira label cell."""
    if is_blank(labels):
        return set()
    text = " | ".join(map(str, labels)) if isinstance(labels, (list, tuple, set)) else str(labels)
    if text.strip().casefold() in {"no labels", "none"}:
        return set()
    return set(LABEL_PATTERN.findall(text))

def detect_ticket_type(labels):
    if not parse_labels(labels):
        return "WARNING: No matching ticket type"
    
    labels = parse_labels(labels)
    for label, ticket_type in TICKET_TYPE_MAPPING.items():
        if label in labels:
            return ticket_type
    return "WARNING: No matching ticket type"


def check_sample_labels(labels):
    if not parse_labels(labels):
        return "WARNING: No sample label found"
    
    labels = parse_labels(labels)
    found_samples = [name for lbl, name in SAMPLE_LABEL_MAPPING.items() if lbl in labels]
    
    if found_samples:
        return "OK: " + ", ".join(sorted(set(found_samples)))
    return "WARNING: No sample label found"


def check_description(description):
    if pd.isna(description):
        return "OK"
    
    description = str(description)
    for placeholder in PLACEHOLDERS:
        if placeholder in description:
            return f"WARNING: Placeholder found ({placeholder})"
    return "OK"


def check_occurrence_filter_description(description):
    if pd.isna(description):
        return "WARNING: Occurrence Filter text not found"
    
    description = str(description)
    for term in OCCURRENCE_FILTER_TERMS:
        if term in description:
            return "OK"
    return "WARNING: Occurrence Filter text not found"


def check_classification(row, classification_column):
    if classification_column is None:
        return "WARNING: Classification column is missing"

    classification = row[classification_column]
    labels = parse_labels(row["Labels"])

    if pd.isna(classification):
        return "WARNING: Classification is missing"

    classification = str(classification).strip()
    if classification == "" or classification.lower() == "no classification":
        return "WARNING: Classification is missing"

    if classification in INVALID_CLASSIFICATIONS:
        return f"ERROR: Invalid classification ({classification})"

    if classification not in VALID_CLASSIFICATIONS:
        return f"ERROR: Unknown classification ({classification})"

    has_class_003_os_label = bool(labels.intersection(CLASS_003_OS_LABELS))
    has_class_002_os_label = bool(labels.intersection(CLASS_002_OS_LABELS))

    if classification == "Class_003" and not has_class_003_os_label:
        return "ERROR: Class_003 requires Label_025 or Label_007"
    if classification == "Class_002" and not has_class_002_os_label:
        return "ERROR: Class_002 requires Label_017 or Label_008"
    if classification == "Class_001" and not (has_class_003_os_label and has_class_002_os_label):
        return "ERROR: Class_001 requires labels from both OS groups"

    return "OK"


def check_priority(priority):
    if pd.isna(priority):
        return "WARNING: Priority is missing"
    priority = str(priority).strip()
    if priority == "" or priority.lower() == "no priority":
        return "WARNING: Priority is missing"
    return "OK"


def check_closed_ticket_resolution(row):
    """Require a resolution only when the Jira status is Closed."""
    if "Status" not in row or "Resolution" not in row:
        return "WARNING: Status or Resolution field is missing"
    status = get_text(row, "Status")
    if status.casefold() != "closed":
        return "OK: Ticket is not closed"
    resolution = get_text(row, "Resolution")
    if not resolution or resolution.casefold() in {"none", "unresolved", "no resolution"}:
        return "ERROR: Closed ticket has no resolution"
    return "OK: Closed ticket is resolved"


def check_categorization(categorization):
    if pd.isna(categorization):
        return "WARNING: Categorization is empty"
    
    categorization = str(categorization).strip()
    if categorization == "":
        return "WARNING: Categorization is empty"
    if "placeholder" in categorization.lower() or categorization.lower() == "no categorization":
        return "WARNING: Categorization placeholder value found"
    if categorization not in VALID_CATEGORIZATIONS:
        return f"WARNING: Invalid categorization ({categorization})"
    return "OK"


def check_sample_label_categorization(row):
    labels = parse_labels(row["Labels"])
    categorization = str(row["Custom field (Categorization)"]).strip() if not pd.isna(row["Custom field (Categorization)"]) else ""

    for label, expected_categorization in SAMPLE_LABEL_CATEGORIZATION_MAPPING.items():
        if label in labels and categorization != expected_categorization:
            return f"ERROR: {label} requires {expected_categorization}"
    return "OK"


def check_affects_version(row):
    labels = parse_labels(row["Labels"])
    affects_version = row["Affects Version/s"]

    if not labels.intersection(MANDATORY_AFFECTS_LABELS):
        return "OK"

    if is_blank(affects_version) or str(affects_version).strip().casefold() == "none":
        return "WARNING: Affects Version/s is mandatory"
    return "OK"


def extract_label_values(labels):
    return sorted(parse_labels(labels))


def check_known_expected_label(row):
    """Pass when at least one documented ticket-type label is present."""
    labels = set(extract_label_values(row["Labels"]))
    matched_types = [ticket_type for label, ticket_type in TICKET_TYPE_MAPPING.items() if label in labels]
    if matched_types:
        return "OK: " + ", ".join(matched_types)
    return "WARNING: No known expected ticket-type label"


def check_extra_labels(row):
    """Report undocumented labels without treating them as invalid."""
    labels = set(extract_label_values(row["Labels"]))
    expected_type_labels = set(TICKET_TYPE_MAPPING)
    documented_non_type_labels = set().union(
        SAMPLE_LABEL_MAPPING,
        CLASS_003_OS_LABELS,
        CLASS_002_OS_LABELS,
        MANDATORY_AFFECTS_LABELS,
    )
    known_labels = expected_type_labels | documented_non_type_labels
    unknown_labels = sorted(labels - known_labels)

    if unknown_labels:
        return "WARNING: Undocumented labels found (" + ", ".join(unknown_labels) + ")"
    return "OK: No undocumented labels"


def check_tg_report_markers(row):
    text = collect_text(row, TG_TEXT_COLUMNS)
    normalized = text.casefold()
    applicable = any(marker.casefold() in normalized for marker in TG_REPORT_MARKERS)
    if not applicable:
        return "NOT APPLICABLE: No TG report reference"
    missing_markers = [marker for marker in TG_REPORT_MARKERS if marker.casefold() not in normalized]
    if missing_markers:
        return "WARNING: Missing TG report markers (" + ", ".join(missing_markers) + ")"
    return "OK"


def extract_tg_task_ids(row):
    text = collect_text(row, TG_TEXT_COLUMNS)
    task_ids = re.findall(r"Exec_\d+", text)
    return ", ".join(sorted(set(task_ids)))


def check_infra_process(row):
    if row["Ticket Type"] != "INFRA":
        return "OK"

    assignee = get_text(row, "Assignee")
    priority = get_text(row, "Priority").lower()
    description = get_text(row, "Description").lower()
    follow_up_information = get_first_available_text(row, FOLLOW_UP_COLUMNS)
    follow_up_required = "follow-up required" in description or "follow up required" in description

    if priority in CRITICAL_PRIORITIES and not assignee:
        return "WARNING: Critical ticket requires an owner"
    if follow_up_required and not follow_up_information:
        return "WARNING: Follow-up information is required"
    if not assignee:
        return "WARNING: Assignee is missing"
    return "OK"


def check_tc_validation(row):
    other_text = get_first_available_text(row, ["Custom field (Other Text)", "Other Text"])
    combined_text = collect_text(row, TC_TEXT_COLUMNS)
    labels = parse_labels(row["Labels"])
    test_related = "test" in combined_text.lower() or "TC_" in combined_text or "Label_015" in labels
    tc_ids = re.findall(r"TC_\d+", combined_text)

    if not other_text:
        return "WARNING: Custom field (Other Text) is empty"

    for placeholder in PLACEHOLDERS:
        if placeholder in other_text:
            return f"WARNING: Placeholder found in Custom field (Other Text) ({placeholder})"

    if test_related and not tc_ids:
        return "WARNING: Test-related ticket does not contain a TC_xxx ID"
    return "OK"
def afficher_resume_ticket(ticket_data):
    """Affiche uniquement les métriques essentielles dans le terminal."""
    print("\n" + "=" * 50)
    print(f"  RÉSUMÉ DU TICKET : {ticket_data.get('key')}")
    print("=" * 50)
    print(f"   Résumé    : {ticket_data.get('summary')}")
    print(f"   Assigné à : {ticket_data.get('assignee')}")
    print(f"  Statut    : {ticket_data.get('status')}")
    print(f"   Priorité  : {ticket_data.get('priority')}")
    print("=" * 50 + "\n")


def _contains_any(text, markers):
    normalized_text = "" if pd.isna(text) else str(text).lower()
    return any(marker.lower() in normalized_text for marker in markers)


def check_reproduction_steps(description):
    """Require a recognisable reproduction-steps section in the description."""
    return "OK" if _contains_any(description, REPRODUCTION_STEP_MARKERS) else "WARNING: Reproduction steps are missing"


def check_expected_results(description):
    """Require a recognisable expected-result section in the description."""
    return "OK" if _contains_any(description, EXPECTED_RESULT_MARKERS) else "WARNING: Expected result is missing"


def check_attachments_or_logs(description):
    """Require an attachment, log, or trace reference for diagnostic evidence."""
    return "OK" if _contains_any(description, ATTACHMENT_LOG_MARKERS) else "WARNING: Attachment, log, or trace is missing"
