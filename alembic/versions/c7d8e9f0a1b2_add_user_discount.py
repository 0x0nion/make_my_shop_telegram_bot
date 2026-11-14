"""add_user_discount

Revision ID: c7d8e9f0a1b2
Revises: b9c4d6e5f2a8
Create Date: 2026-11-12

Добавляет в ``users`` поле ``discount`` — персональная скидка клиента
в процентах (0–100). Устанавливается администратором в карточке
пользователя (раздел «Юзеры»).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: str | None = 'b9c4d6e5f2a8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch-режим: на SQLite ``ADD COLUMN ... NOT NULL`` требует
    # ``server_default``; на PostgreSQL batch-режим деградирует в нативный DDL.
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('discount', sa.Numeric(5, 2), nullable=False, server_default=sa.text('0'))
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('discount')
