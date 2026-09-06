"""add_delivery_address_type_to_orders

Revision ID: b7e2c9d4a1f3
Revises: 46545ec38208
Create Date: 2026-09-02 12:00:00.000000

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e2c9d4a1f3'
down_revision: Union[str, Sequence[str], None] = '46545ec38208'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('delivery_address_type', sa.String(length=20), nullable=True)
        )

    # Data migration: normalize existing delivery_address values and set the type.
    # Old format was always "<a href='X'>label</a>"; extract X, then classify by prefix.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, delivery_address FROM orders WHERE delivery_address IS NOT NULL")
    ).fetchall()
    pattern = re.compile(r"<a href='(.*?)'>.*?</a>")
    for row in rows:
        raw = row.delivery_address
        match = pattern.match(raw)
        if match:
            raw = match.group(1)
        addr_type = "location" if raw.startswith("http") else "text"
        conn.execute(
            sa.text(
                "UPDATE orders SET delivery_address = :addr, "
                "delivery_address_type = :addr_type WHERE id = :id"
            ),
            {"addr": raw, "addr_type": addr_type, "id": row.id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('delivery_address_type')
