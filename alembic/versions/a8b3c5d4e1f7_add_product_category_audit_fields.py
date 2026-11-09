"""add_product_category_audit_fields

Revision ID: a8b3c5d4e1f7
Revises: f7a2b4c3d9e6
Create Date: 2026-11-07

Добавляет в ``products`` и ``categories`` поля аудита:
  - ``created_at`` — когда сущность создана;
  - ``updated_at`` — когда последний раз изменялась;
  - ``updated_by`` — кто (Telegram ID) последний раз изменял.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a8b3c5d4e1f7'
down_revision: str | None = 'f7a2b4c3d9e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ('products', 'categories'):
        # Batch-режим: пересоздание таблицы нужно для ``created_at`` с
        # ``DEFAULT CURRENT_TIMESTAMP`` (SQLite не умеет ``ADD COLUMN ... NOT NULL``
        # с таким default на заполненную таблицу) и для добавления FK.
        # На PostgreSQL batch-режим деградирует в нативный DDL.
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False)
            )
            batch_op.add_column(sa.Column('updated_at', sa.DateTime(), nullable=True))
            batch_op.add_column(sa.Column('updated_by', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f'fk_{table}_updated_by_users', 'users', ['updated_by'], ['id'], ondelete='SET NULL'
            )


def downgrade() -> None:
    for table in ('categories', 'products'):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_updated_by_users', type_='foreignkey')
        op.drop_column(table, 'updated_by')
        op.drop_column(table, 'updated_at')
        op.drop_column(table, 'created_at')
