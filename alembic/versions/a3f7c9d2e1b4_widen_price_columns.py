"""widen_price_columns

Revision ID: a3f7c9d2e1b4
Revises: e2cd576ea91c
Create Date: 2026-10-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f7c9d2e1b4'
down_revision: Union[str, None] = 'e2cd576ea91c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # products.price
    op.alter_column(
        'products', 'price',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=28, scale=18),
        existing_nullable=False,
    )
    # orders.delivery_price
    op.alter_column(
        'orders', 'delivery_price',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=28, scale=18),
        existing_nullable=False,
    )
    # orders.total_price
    op.alter_column(
        'orders', 'total_price',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=28, scale=18),
        existing_nullable=False,
    )
    # order_items.price_at_purchase
    op.alter_column(
        'order_items', 'price_at_purchase',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=28, scale=18),
        existing_nullable=False,
    )
    # temp_products.price
    op.alter_column(
        'temp_products', 'price',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Numeric(precision=28, scale=18),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'temp_products', 'price',
        existing_type=sa.Numeric(precision=28, scale=18),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        'order_items', 'price_at_purchase',
        existing_type=sa.Numeric(precision=28, scale=18),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        'orders', 'total_price',
        existing_type=sa.Numeric(precision=28, scale=18),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        'orders', 'delivery_price',
        existing_type=sa.Numeric(precision=28, scale=18),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
    op.alter_column(
        'products', 'price',
        existing_type=sa.Numeric(precision=28, scale=18),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
    )
