"""add_workers_table

Revision ID: b4c5d6e7f8a9
Revises: d8e9f0a1b2c3
Create Date: 2026-11-19

Добавляет таблицу ``workers`` — работники (администраторы, добавленные
через админ-панель «Работники»):
  - ``telegram_id`` — Telegram ID работника (уникальный);
  - ``position``    — должность (свободный текст);
  - ``created_at``  — когда работника добавили.

Главный администратор из env (``ADMIN_ID``) в таблице не хранится:
он виртуальный, всегда имеет доступ и не может быть удалён.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: str | None = 'd8e9f0a1b2c3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'workers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('position', sa.String(255), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workers_telegram_id'), 'workers', ['telegram_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_workers_telegram_id'), table_name='workers')
    op.drop_table('workers')
