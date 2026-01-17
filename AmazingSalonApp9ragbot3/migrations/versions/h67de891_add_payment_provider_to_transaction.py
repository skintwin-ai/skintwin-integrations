"""Add payment provider to Transaction

Revision ID: h67de891
Revises: g45bc12d
Create Date: 2025-03-19 19:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h67de891'
down_revision = 'g45bc12d'
branch_labels = None
depends_on = None


def upgrade():
    # Add payment provider column
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_provider', sa.String(length=50), server_default='stripe', nullable=True))
        
        # Rename stripe_payment_intent_id to payment_intent_id for flexibility with different providers
        batch_op.alter_column('stripe_payment_intent_id', new_column_name='payment_intent_id')
    
    # Create index for faster lookups by payment provider
    op.create_index(op.f('ix_transactions_payment_provider'), 'transactions', ['payment_provider'], unique=False)


def downgrade():
    # Remove payment provider field and revert the payment_intent_id name change
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('payment_intent_id', new_column_name='stripe_payment_intent_id')
        batch_op.drop_column('payment_provider')
    
    # Drop index
    op.drop_index(op.f('ix_transactions_payment_provider'), table_name='transactions')