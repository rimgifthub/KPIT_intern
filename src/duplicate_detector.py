"""Utilities for selecting prior tickets for duplicate analysis."""

import pandas as pd


TICKET_ID_COLUMNS = ["Key", "Issue key", "Issue Key", "Ticket ID", "Ticket Id", "ID"]


def get_historical_tickets(ticket, all_tickets):
    """Return all rows except the ticket currently being checked."""
    if not isinstance(all_tickets, pd.DataFrame):
        raise TypeError("all_tickets must be a pandas DataFrame")

    historical_tickets = all_tickets.copy()
    id_column = next((column for column in TICKET_ID_COLUMNS if column in historical_tickets.columns), None)
    if id_column is None:
        return historical_tickets.reset_index(drop=True)

    ticket_id = ticket.get(id_column)
    if ticket_id is None:
        return historical_tickets.reset_index(drop=True)

    current_id = str(ticket_id).strip().casefold()
    return historical_tickets.loc[
        historical_tickets[id_column].astype(str).str.strip().str.casefold() != current_id
    ].reset_index(drop=True)
