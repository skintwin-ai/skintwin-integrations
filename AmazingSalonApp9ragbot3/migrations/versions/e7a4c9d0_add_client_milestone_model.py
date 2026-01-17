"""Add client milestone model

Revision ID: e7a4c9d0
Revises: 6b925a8b
Create Date: 2025-03-19 11:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'e7a4c9d0'
down_revision = '6b925a8b'
branch_labels = None
depends_on = None


def upgrade():
    # Create client_milestones table
    op.create_table(
        'client_milestones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('milestone_type', sa.String(length=100), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('importance', sa.Integer(), nullable=False, default=5),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('milestone_metadata', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    # Create index for faster client lookups
    op.create_index(op.f('ix_client_milestones_client_id'), 'client_milestones', ['client_id'], unique=False)
    # Create index for milestone type for filtering
    op.create_index(op.f('ix_client_milestones_milestone_type'), 'client_milestones', ['milestone_type'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_client_milestones_milestone_type'), table_name='client_milestones')
    op.drop_index(op.f('ix_client_milestones_client_id'), table_name='client_milestones')
    # Drop table
    op.drop_table('client_milestones')