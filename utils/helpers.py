"""Small, defensive helpers for reading Jira-export rows."""

import pandas as pd


def get_text(row, column):
    """Return a trimmed text value for *column*, or an empty string."""
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()


def get_first_available_text(row, columns):
    """Return the first non-empty value available from *columns*."""
    for column in columns:
        value = get_text(row, column)
        if value:
            return value
    return ""


def collect_text(row, columns):
    """Combine the non-empty text values in *columns* for text checks."""
    return "\n".join(get_text(row, column) for column in columns if get_text(row, column))
