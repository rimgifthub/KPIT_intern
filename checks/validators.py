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

def detect_ticket_type(labels):
    if pd.isna(labels) or str(labels) == "No labels":
        return "WARNING: No matching ticket type"
    
    labels = str(labels)
    for label, ticket_type in TICKET_TYPE_MAPPING.items():
        if label in labels:
            return ticket_type
    return "WARNING: No matching ticket type"


def check_sample_labels(labels):
    if pd.isna(labels) or str(labels) == "No labels":
        return "WARNING: No sample label found"
    
    labels = str(labels)
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
    labels = str(row["Labels"])

    if pd.isna(classification):
        return "WARNING: Classification is missing"

    classification = str(classification).strip()
    if classification == "" or classification.lower() == "no classification":
        return "WARNING: Classification is missing"

    if classification in INVALID_CLASSIFICATIONS:
        return f"WARNING: Invalid classification ({classification})"

    if classification not in VALID_CLASSIFICATIONS:
        return f"WARNING: Unknown classification ({classification})"

    has_class_003_os_label = any(label in labels for label in CLASS_003_OS_LABELS)
    has_class_002_os_label = any(label in labels for label in CLASS_002_OS_LABELS)

    if classification == "Class_003" and not has_class_003_os_label:
        return "WARNING: Class_003 requires Label_025 or Label_007"
    if classification == "Class_002" and not has_class_002_os_label:
        return "WARNING: Class_002 requires Label_017 or Label_008"
    if classification == "Class_001" and not (has_class_003_os_label and has_class_002_os_label):
        return "WARNING: Class_001 requires labels from both OS groups"

    return "OK"


def check_priority(priority):
    if pd.isna(priority):
        return "WARNING: Priority is missing"
    priority = str(priority).strip()
    if priority == "" or priority.lower() == "no priority":
        return "WARNING: Priority is missing"
    return "OK"


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
    labels = str(row["Labels"])
    categorization = str(row["Custom field (Categorization)"]).strip() if not pd.isna(row["Custom field (Categorization)"]) else ""

    for label, expected_categorization in SAMPLE_LABEL_CATEGORIZATION_MAPPING.items():
        if label in labels and categorization != expected_categorization:
            return f"ERROR: {label} requires {expected_categorization}"
    return "OK"


def check_affects_version(row):
    labels = str(row["Labels"])
    affects_version = row["Affects Version/s"]

    if not any(label in labels for label in MANDATORY_AFFECTS_LABELS):
        return "OK"

    if pd.isna(affects_version) or str(affects_version).strip() == "" or str(affects_version).lower() == "none":
        return "WARNING: Affects Version/s is mandatory"
    return "OK"


def extract_label_values(labels):
    if pd.isna(labels) or str(labels) == "No labels":
        return []
    numbered_labels = re.findall(r"Label_\d+", str(labels))
    return sorted(set(numbered_labels + list(SAMPLE_LABEL_MAPPING.keys())))


def check_extra_labels(row):
    ticket_type = row["Ticket Type"]
    if str(ticket_type).startswith("WARNING"):
        return "WARNING: Cannot validate extra labels without a detected ticket type"

    labels = extract_label_values(row["Labels"])
    allowed_labels = set(COMMON_ALLOWED_LABELS + ALLOWED_LABELS_BY_TICKET_TYPE.get(ticket_type, []))
    unexpected_labels = [label for label in labels if label not in allowed_labels]

    if unexpected_labels:
        return "WARNING: Unexpected labels found (" + ", ".join(unexpected_labels) + ")"
    return "OK"


def check_tg_report_markers(row):
    text = collect_text(row, TG_TEXT_COLUMNS)
    missing_markers = [marker for marker in TG_REPORT_MARKERS if marker not in text]
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
    labels = str(row["Labels"])
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