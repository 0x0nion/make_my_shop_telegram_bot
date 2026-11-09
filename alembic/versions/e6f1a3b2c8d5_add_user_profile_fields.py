"""add_user_profile_fields

Revision ID: e6f1a3b2c8d5
Revises: d5e9f2a1b7c4
Create Date: 2026-11-07

Добавляет в ``users`` поля профиля клиента (из Telegram):
  - ``first_name`` — имя клиента;
  - ``username``   — username в Telegram;
  - ``created_at`` — когда пользователь впервые появился в системе.

Заполняются при первом обращении и обновляются, если были пустыми.
Используются в отчётах и карточках клиентов.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e6f1a3b2c8d5'
down_revision: str | None = 'd5e9f2a1b7c4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Batch-режим: пересоздание таблицы нужно для ``created_at`` с
    # ``DEFAULT CURRENT_TIMESTAMP`` — SQLite не умеет ``ADD COLUMN ... NOT NULL``
    # с таким (нестандартным) default на заполненную таблицу. На PostgreSQL
    # batch-режим деградирует в нативный DDL.
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('first_name', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('username', sa.String(255), nullable=True))
        batch_op.add_column(
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False)
        )


def downgrade() -> None:
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'username')
    op.drop_column('users', 'first_name')
