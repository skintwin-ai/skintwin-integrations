"""Add skincare fields to Client model

Revision ID: d83f4a5e
Revises: e7a4c9d0
Create Date: 2025-03-19 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd83f4a5e'
down_revision = 'e7a4c9d0'
branch_labels = None
depends_on = None


def upgrade():
    # Add new skin care specific columns to the clients table
    op.add_column('clients', sa.Column('skin_type', sa.String(20), server_default='normal'))
    op.add_column('clients', sa.Column('skin_concern', sa.String(50), server_default='hydration'))
    op.add_column('clients', sa.Column('sensitivity_level', sa.String(20), server_default='low'))


def downgrade():
    # Remove the skin care specific columns
    op.drop_column('clients', 'skin_type')
    op.drop_column('clients', 'skin_concern')
    op.drop_column('clients', 'sensitivity_level')