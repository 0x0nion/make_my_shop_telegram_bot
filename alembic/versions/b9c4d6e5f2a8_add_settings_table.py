"""add_settings_table

Revision ID: b9c4d6e5f2a8
Revises: a8b3c5d4e1f7
Create Date: 2026-11-07

Создаёт таблицу ``settings`` — ключ-значение для настроек магазина
(базовая инфраструктура). Одна строка на ``key``. ``updated_by`` хранит
Telegram ID администратора, который последний раз менял значение.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b9c4d6e5f2a8'
down_revision: str | None = 'a8b3c5d4e1f7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'settings',
        sa.Column('key', sa.String(100), nullable=False),
        sa.Column('value', sa.String(255), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('settings')
