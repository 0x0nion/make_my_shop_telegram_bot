"""add_stock_metrics_to_products

Revision ID: ff6beb0c78ea
Revises: b7e2a1c9d3f5
Create Date: 2026-11-03

Добавляет в ``products`` метрики склада:
  - ``reserved``         — заморожено активными заказами (бронирование);
  - ``total_sold``       — всего продано (накопительно, по завершённым заказам);
  - ``total_arrived``    — всего пришло/пополнено (накопительно);
  - ``total_written_off``— всего списано вручную (накопительно).

Доступный остаток для клиента = ``stock - reserved``.
Только реальные товары (черновики каталога не участвуют в заказах).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ff6beb0c78ea'
down_revision: str | None = 'b7e2a1c9d3f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('reserved', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'products',
        sa.Column('total_sold', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'products',
        sa.Column('total_arrived', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'products',
        sa.Column('total_written_off', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('products', 'total_written_off')
    op.drop_column('products', 'total_arrived')
    op.drop_column('products', 'total_sold')
    op.drop_column('products', 'reserved')
