"""add_stock_movements

Revision ID: c4d8e1f2a6b3
Revises: ff6beb0c78ea
Create Date: 2026-11-05

Добавляет таблицу ``stock_movements`` — журнал всех складских движений:
пополнения, списания, бронирования, снятия брони и списаний по
завершённым заказам. Каждое движение фиксируется в той же транзакции,
что и обновление балансов ``products`` (stock/reserved/total_*).

``quantity`` всегда положительное — направление задаёт ``type``.
Снимки ``stock_after`` / ``reserved_after`` позволяют сверить текущие
балансы по журналу.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d8e1f2a6b3'
down_revision: str | None = 'ff6beb0c78ea'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('stock_after', sa.Integer(), nullable=False),
        sa.Column('reserved_after', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('admin_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_stock_movements_product_created', 'stock_movements', ['product_id', 'created_at']
    )
    op.create_index('ix_stock_movements_order_id', 'stock_movements', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_stock_movements_order_id', table_name='stock_movements')
    op.drop_index('ix_stock_movements_product_created', table_name='stock_movements')
    op.drop_table('stock_movements')
