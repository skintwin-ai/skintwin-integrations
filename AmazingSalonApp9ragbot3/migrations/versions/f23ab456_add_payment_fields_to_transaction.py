"""Add payment fields to Transaction

Revision ID: f23ab456
Revises: d83f4a5e
Create Date: 2025-03-19 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f23ab456'
down_revision = 'd83f4a5e'
branch_labels = None
depends_on = None


def upgrade():
    # Add payment processing fields to the transactions table
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('payment_method_id', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('payment_status', sa.String(length=50), server_default='pending', nullable=True))
    
    # Create index for faster lookups by payment intent ID
    op.create_index(op.f('ix_transactions_stripe_payment_intent_id'), 'transactions', ['stripe_payment_intent_id'], unique=True)
    op.create_index(op.f('ix_transactions_payment_status'), 'transactions', ['payment_status'], unique=False)


def downgrade():
    # Remove columns and indices if needed
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_column('payment_status')
        batch_op.drop_column('payment_method_id')
        batch_op.drop_column('stripe_payment_intent_id')
    
    # Drop indices
    op.drop_index(op.f('ix_transactions_stripe_payment_intent_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_payment_status'), table_name='transactions')