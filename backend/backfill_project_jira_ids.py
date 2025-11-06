#!/usr/bin/env python3
"""Backfill project Jira IDs for existing tickets."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

from app.core.database import SessionLocal
from app.models.ticket import TicketHistory
from app.services.redmine_service import RedmineService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

CUSTOM_FIELD_NAME = "Project Jira ID"
BATCH_SIZE = 100


def extract_project_id(issue: Dict) -> Optional[str]:
    """Pull the Jira ID from Redmine custom fields."""
    for field in issue.get("custom_fields", []):
        name = (field.get("name") or "").strip()
        if name.lower() == CUSTOM_FIELD_NAME.lower():
            value = field.get("value")
            if isinstance(value, dict):
                value = value.get("value")
            if value:
                return str(value).strip() or None
    return None


def chunked(iterable: Iterable, size: int) -> Iterable[List]:
    chunk: List = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def backfill() -> None:
    session = SessionLocal()
    redmine = RedmineService()

    try:
        query = (
            session.query(TicketHistory.id, TicketHistory.redmine_ticket_id)
            .filter(
                (TicketHistory.project_jira_id.is_(None))
                | (TicketHistory.project_jira_id == "")
            )
            .order_by(TicketHistory.created_at.asc())
        )

        total_missing = query.count()
        if total_missing == 0:
            logger.info("All tickets already have Jira IDs. Nothing to do.")
            return

        logger.info("Found %s tickets missing Jira IDs", total_missing)

        updated = 0
        skipped = 0

        for batch in chunked(query, BATCH_SIZE):
            ticket_map = {row.redmine_ticket_id: row.id for row in batch}
            redmine_payloads = redmine.get_issues_by_ids(list(ticket_map.keys()))

            for redmine_id, record_id in ticket_map.items():
                issue = redmine_payloads.get(redmine_id)
                if not issue:
                    skipped += 1
                    logger.warning("Redmine issue %s not found; skipping", redmine_id)
                    continue

                project_id = extract_project_id(issue)
                ticket = session.query(TicketHistory).get(record_id)
                if not ticket:
                    skipped += 1
                    logger.warning("Ticket %s missing locally; skipping", record_id)
                    continue

                if project_id:
                    ticket.project_jira_id = project_id
                    updated += 1
                else:
                    skipped += 1
                    logger.warning(
                        "Redmine issue %s lacks '%s'; skipping",
                        redmine_id,
                        CUSTOM_FIELD_NAME,
                    )

            session.commit()
            logger.info("Processed batch: %s updated, %s skipped so far", updated, skipped)

        logger.info("Backfill complete → %s updated, %s skipped", updated, skipped)

    finally:
        session.close()


if __name__ == "__main__":
    backfill()
