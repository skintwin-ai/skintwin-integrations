"""Add fulfillment id to Transaction

Revision ID: j12ab345
Revises: i89fg123
Create Date: 2026-10-02 06:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "j12ab345"
down_revision = "i89fg123"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fulfillment_id", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_column("fulfillment_id")
