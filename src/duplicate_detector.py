"""Utilities for selecting prior tickets for duplicate analysis."""

import pandas as pd


TICKET_ID_COLUMNS = ["Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID"]
CREATED_COLUMNS = ["Created", "Created Date", "Creation date", "Created at"]


def get_historical_tickets(ticket, all_tickets):
    """Return tickets created strictly before *ticket* (never future tickets)."""
    if not isinstance(all_tickets, pd.DataFrame):
        raise TypeError("all_tickets must be a pandas DataFrame")

    historical_tickets = all_tickets.copy()
    id_column = next((column for column in TICKET_ID_COLUMNS if column in historical_tickets.columns), None)
    created_column = next((column for column in CREATED_COLUMNS if column in historical_tickets.columns), None)
    if created_column is None:
        raise ValueError("Input workbook has no creation-date column for historical duplicate analysis.")

    current_created = pd.to_datetime(ticket.get(created_column), errors="coerce")
    if pd.isna(current_created):
        return historical_tickets.iloc[0:0].copy()
    candidate_created = pd.to_datetime(historical_tickets[created_column], errors="coerce")
    historical_tickets = historical_tickets.loc[candidate_created < current_created]

    if id_column is None:
        return historical_tickets.reset_index(drop=True)

    ticket_id = ticket.get(id_column)
    if ticket_id is None:
        return historical_tickets.reset_index(drop=True)

    current_id = str(ticket_id).strip().casefold()
    return historical_tickets.loc[
        historical_tickets[id_column].astype(str).str.strip().str.casefold() != current_id
    ].reset_index(drop=True)
