"""Add system config model

Revision ID: g45bc12d
Revises: f23ab456
Create Date: 2025-03-19 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'g45bc12d'
down_revision = 'f23ab456'
branch_labels = None
depends_on = None


def upgrade():
    # Create the system_config table
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='general'),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key')
    )
    
    # Create index for faster lookups by key
    op.create_index(op.f('ix_system_config_category'), 'system_config', ['category'], unique=False)


def downgrade():
    # Drop the table if needed
    op.drop_index(op.f('ix_system_config_category'), table_name='system_config')
    op.drop_table('system_config')