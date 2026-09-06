"""add_is_paid_to_orders

Revision ID: cc9d7d12bd8a
Revises: 238f7be6911a
Create Date: 2026-08-10 19:02:02.304230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc9d7d12bd8a'
down_revision: Union[str, Sequence[str], None] = '238f7be6911a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_paid', sa.Boolean(), nullable=False, server_default=sa.text('false'))
        )
        batch_op.alter_column(
            'payment_proof_type',
            existing_type=sa.VARCHAR(length=20),
            type_=sa.String(length=255),
            existing_nullable=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.alter_column(
            'payment_proof_type',
            existing_type=sa.String(length=255),
            type_=sa.VARCHAR(length=20),
            existing_nullable=True
        )
        batch_op.drop_column('is_paid')