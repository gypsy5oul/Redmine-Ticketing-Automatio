"""Add project Jira ID indexes

Revision ID: 009_add_project_indexes
Revises: 008_add_database_constraints
Create Date: 2025-02-14 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "009_add_project_indexes"
down_revision = "008_add_database_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize whitespace for consistency in lookups
    op.execute("UPDATE ticket_history SET project_jira_id = NULL WHERE project_jira_id = ''")
    op.execute("UPDATE ticket_history SET project_jira_id = TRIM(project_jira_id) WHERE project_jira_id IS NOT NULL")

    op.create_index(
        "ix_ticket_history_project_status",
        "ticket_history",
        ["project_jira_id", "status"],
    )
    op.create_index(
        "ix_ticket_history_project_sla",
        "ticket_history",
        ["project_jira_id", "sla_breached"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_history_project_sla", table_name="ticket_history")
    op.drop_index("ix_ticket_history_project_status", table_name="ticket_history")
