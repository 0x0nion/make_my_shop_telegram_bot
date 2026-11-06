"""add_stock_to_products

Revision ID: b7e2a1c9d3f5
Revises: a3f7c9d2e1b4
Create Date: 2026-11-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7e2a1c9d3f5'
down_revision: Union[str, None] = 'a3f7c9d2e1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Остаток на складе для реальных товаров (видимость клиента = is_active AND stock > 0)
    op.add_column(
        'products',
        sa.Column('stock', sa.Integer(), nullable=False, server_default='0'),
    )
    # Черновики каталога: остаток не сбрасывается при синхронизации,
    # новые товары получают 0 (не видны клиентам до первого пополнения)
    op.add_column(
        'temp_products',
        sa.Column('stock', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('temp_products', 'stock')
    op.drop_column('products', 'stock')
