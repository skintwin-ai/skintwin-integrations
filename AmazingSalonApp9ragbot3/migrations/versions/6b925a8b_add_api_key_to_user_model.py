"""Add API key to User model

Revision ID: 6b925a8b
Revises: c45e7a8bc9d5
Create Date: 2025-03-19 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6b925a8b'
down_revision = 'c45e7a8bc9d5'
branch_labels = None
depends_on = None


def upgrade():
    # Add api_key column to users table
    op.add_column('users', sa.Column('openai_api_key', sa.String(255), nullable=True))


def downgrade():
    # Remove api_key column from users table
    op.drop_column('users', 'openai_api_key')