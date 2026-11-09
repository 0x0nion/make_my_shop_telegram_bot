"""add_stock_movement_comment

Revision ID: f7a2b4c3d9e6
Revises: e6f1a3b2c8d5
Create Date: 2026-11-07

Добавляет в ``stock_movements`` поле ``comment`` — комментарий
администратора (причина/примечание) к складскому движению.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7a2b4c3d9e6'
down_revision: str | None = 'e6f1a3b2c8d5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('stock_movements', sa.Column('comment', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('stock_movements', 'comment')
