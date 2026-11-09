"""add_order_audit_fields

Revision ID: d5e9f2a1b7c4
Revises: c4d8e1f2a6b3
Create Date: 2026-11-07

Добавляет в ``orders`` поля аудита и создаёт таблицу
``order_status_history`` — журнал смены статусов заказа.

Поля ``orders``:
  - ``paid_at``      — когда заказ отмечен как оплаченный;
  - ``paid_by``      — кто (Telegram ID) отметил оплату (админ/клиент);
  - ``updated_at``   — когда заказ последний раз изменялся;
  - ``completed_at`` — когда заказ переведён в ``completed``;
  - ``cancelled_at`` — когда заказ переведён в ``cancelled``.

``order_status_history`` (append-only): каждая смена ``status`` фиксируется
строкой (old_status -> new_status, changed_by, reason, created_at).
Старые записи очищаются по политике хранения (RetentionService).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd5e9f2a1b7c4'
down_revision: str | None = 'c4d8e1f2a6b3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('paid_at', sa.DateTime(), nullable=True))
    op.add_column('orders', sa.Column('paid_by', sa.Integer(), nullable=True))
    op.add_column('orders', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.add_column('orders', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.add_column('orders', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    # Batch-режим: на PostgreSQL — нативный ADD CONSTRAINT, на SQLite —
    # пересоздание таблицы (SQLite не умеет добавлять FK в существующую).
    with op.batch_alter_table('orders') as batch_op:
        batch_op.create_foreign_key('fk_orders_paid_by_users', 'users', ['paid_by'], ['id'], ondelete='SET NULL')

    op.create_table(
        'order_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('old_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_order_status_history_order_created', 'order_status_history', ['order_id', 'created_at']
    )
    # Отдельный индекс по created_at — для периодической очистки по возрасту.
    op.create_index(
        'ix_order_status_history_created_at', 'order_status_history', ['created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_order_status_history_created_at', table_name='order_status_history')
    op.drop_index('ix_order_status_history_order_created', table_name='order_status_history')
    op.drop_table('order_status_history')
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_constraint('fk_orders_paid_by_users', type_='foreignkey')
    op.drop_column('orders', 'cancelled_at')
    op.drop_column('orders', 'completed_at')
    op.drop_column('orders', 'updated_at')
    op.drop_column('orders', 'paid_by')
    op.drop_column('orders', 'paid_at')
