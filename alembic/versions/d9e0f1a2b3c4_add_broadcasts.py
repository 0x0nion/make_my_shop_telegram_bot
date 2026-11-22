"""add_broadcasts

Revision ID: d9e0f1a2b3c4
Revises: b4c5d6e7f8a9
Create Date: 2026-11-22

Добавляет рассылку (broadcast) для админ-панели:

- ``broadcasts`` — рассылки:
  - ``admin_id``     — кто создал (изоляция по администратору);
  - ``text``         — текст, который получают пользователи;
  - ``status``       — pending / running / cancelling / completed /
                       cancelled / interrupted;
  - ``total``        — получателей в снапшоте;
  - ``skipped``      — исключено при создании (cooldown / заблокировали
                       бота / администраторы);
  - ``sent`` / ``failed`` / ``blocked`` — счётчики (обновляются по чанкам);
  - ``created_at`` / ``started_at`` / ``finished_at``.

- ``broadcast_recipients`` — снапшот получателей (UNIQUE по паре
  ``broadcast_id + user_id`` — защита от дублей):
  - ``status``   — pending / sent / failed / blocked / skipped /
                   retry_async;
  - ``attempts`` — сколько раз пробовали отправить;
  - ``last_error`` — последняя ошибка (для диагностики).

- ``users.blocked_at`` — когда пользователь заблокировал бота (Telegram
  сообщает об этом при первой же попытке отправки). Неактивным
  пользователям рассылки больше не отправляются.

БД — единственный источник истины: после рестарта бота незавершённую
рассылку можно возобновить (статус ``interrupted``), повторные отправки
не происходят.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd9e0f1a2b3c4'
down_revision: str | None = 'b4c5d6e7f8a9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('blocked_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'broadcasts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_id', sa.BigInteger(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('blocked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_broadcasts_admin_id'), 'broadcasts', ['admin_id'])
    op.create_index(op.f('ix_broadcasts_status'), 'broadcasts', ['status'])

    op.create_table(
        'broadcast_recipients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('broadcast_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['broadcast_id'], ['broadcasts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('broadcast_id', 'user_id', name='uq_broadcast_recipients'),
    )
    op.create_index(
        op.f('ix_broadcast_recipients_broadcast_id'),
        'broadcast_recipients',
        ['broadcast_id'],
    )
    op.create_index(
        op.f('ix_broadcast_recipients_status'),
        'broadcast_recipients',
        ['broadcast_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_broadcast_recipients_status'), table_name='broadcast_recipients')
    op.drop_index(op.f('ix_broadcast_recipients_broadcast_id'), table_name='broadcast_recipients')
    op.drop_table('broadcast_recipients')
    op.drop_index(op.f('ix_broadcasts_status'), table_name='broadcasts')
    op.drop_index(op.f('ix_broadcasts_admin_id'), table_name='broadcasts')
    op.drop_table('broadcasts')
    op.drop_column('users', 'blocked_at')
