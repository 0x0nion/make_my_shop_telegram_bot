"""add_order_discount_percent

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-11-16

Добавляет в ``orders`` поле ``discount_percent`` — снапшот персональной
скидки покупателя (в процентах, 0–100) на момент оформления заказа.
Сумма скидки не хранится, а выводится из состава заказа
(items_sum * discount_percent / 100). Скидка применяется только к
товарам, не к доставке.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: str | None = 'c7d8e9f0a1b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch-режим: на SQLite ``ADD COLUMN ... NOT NULL`` требует
    # ``server_default``; на PostgreSQL batch-режим деградирует в нативный DDL.
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(
            sa.Column('discount_percent', sa.Numeric(5, 2), nullable=False, server_default=sa.text('0'))
        )


def downgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('discount_percent')
