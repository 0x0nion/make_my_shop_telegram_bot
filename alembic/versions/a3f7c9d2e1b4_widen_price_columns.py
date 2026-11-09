"""widen_price_columns

Revision ID: a3f7c9d2e1b4
Revises: e2cd576ea91c
Create Date: 2026-10-10

Смена типа цен ``Numeric(10,2) -> Numeric(28,18)`` выполнена через
batch-режим: на PostgreSQL это нативный ``ALTER COLUMN ... TYPE``,
на SQLite — пересоздание таблицы (copy-and-move), т.к. SQLite не
поддерживает смену типа колонки на месте.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f7c9d2e1b4'
down_revision: str | None = 'e2cd576ea91c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = sa.Numeric(precision=10, scale=2)
_NEW = sa.Numeric(precision=28, scale=18)


def _widen(table: str, columns: tuple[str, ...], old: sa.Numeric, new: sa.Numeric) -> None:
    with op.batch_alter_table(table) as batch_op:
        for column in columns:
            batch_op.alter_column(
                column,
                existing_type=old,
                type_=new,
                existing_nullable=False,
            )


def upgrade() -> None:
    _widen('products', ('price',), _OLD, _NEW)
    _widen('orders', ('delivery_price', 'total_price'), _OLD, _NEW)
    _widen('order_items', ('price_at_purchase',), _OLD, _NEW)
    _widen('temp_products', ('price',), _OLD, _NEW)


def downgrade() -> None:
    _widen('temp_products', ('price',), _NEW, _OLD)
    _widen('order_items', ('price_at_purchase',), _NEW, _OLD)
    _widen('orders', ('total_price', 'delivery_price'), _NEW, _OLD)
    _widen('products', ('price',), _NEW, _OLD)
