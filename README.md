# Jira Ticket Quality and Duplicate Analysis

This project validates Jira ticket quality, identifies likely duplicate tickets, and exports a review-ready Excel report.

## Features

- Validates mandatory ticket rules and records `WARNING` or blocking `ERROR` results.
- Marks a ticket `Not Valid` only when at least one validation result is an `ERROR`.
- Enforces classification/label combinations and requires a resolution for closed tickets.
- Detects likely duplicates only among tickets created before the selected ticket.
- Clearly reports when duplicate analysis cannot run because the creation date is missing or invalid.
- Exports quality KPIs, selected-ticket results, and a duplicate-analysis report to Excel.

## Prerequisites

- Python 3.10 or newer
- `pip`
- An Excel input workbook with the required Jira-export columns:
  `Labels`, `Description`, `Priority`, `Custom field (Categorization)`, and `Affects Version/s`
- A creation-date column (`Created`, `Created Date`, `Creation date`, or `Created at`) for duplicate analysis

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

Use the included workbook and default output location:

```powershell
python main\main.py
```

Or choose the input workbook, output workbook, and ticket key explicitly:

```powershell
python main\main.py --input local_input_tickets.xlsx --output reports\local_analysis_output.xlsx --ticket ISSUE-123
```

Run `run_local.bat` on Windows as an alternative.

## Outputs

The output workbook contains:

- `Quality KPI Dataset` — every ticket with validation results and quality indicators
- `Quality KPIs` — aggregated pass rates and ticket counts
- `Selected Ticket` — the selected ticket’s analysis
- `Similarity Report` — ranked duplicate candidates, or `NOT ANALYSED` with a reason when no valid creation date is available

`Valid_or_Not` is the single validity field. Warnings mean information needs review; errors mean a rule is not respected and the ticket is not valid.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Final presentation

`Final_Presentation.pptx` is generated from `tools/create_presentation.py`:

```powershell
python tools\create_presentation.py
```
