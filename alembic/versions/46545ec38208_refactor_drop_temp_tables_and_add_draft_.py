"""refactor: drop temp tables and add draft flags to core models

Revision ID: 46545ec38208
Revises: 0418f092d6fc
Create Date: 2026-08-13 21:13:44.414424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46545ec38208'
down_revision: Union[str, Sequence[str], None] = '0418f092d6fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- CATEGORIES ---
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_draft', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('admin_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('original_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_categories_admin_id'), ['admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_categories_is_draft'), ['is_draft'], unique=False)
        batch_op.create_index(batch_op.f('ix_categories_original_id'), ['original_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_categories_original_id_categories',
            'categories',
            ['original_id'],
            ['id'],
            ondelete='SET NULL'
        )

    # --- LOCALE_TEXTS ---
    with op.batch_alter_table('locale_texts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_draft', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('admin_id', sa.BigInteger(), nullable=True))
        batch_op.alter_column(
            'text',
            existing_type=sa.VARCHAR(),
            type_=sa.Text(),
            existing_nullable=False
        )
        batch_op.drop_constraint('uq_entity_lang', type_='unique')
        batch_op.create_index(batch_op.f('ix_locale_texts_admin_id'), ['admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_locale_texts_is_draft'), ['is_draft'], unique=False)
        batch_op.create_unique_constraint(
            'uq_entity_lang_draft',
            ['entity_type', 'entity_id', 'language_code', 'is_draft', 'admin_id']
        )

    # --- PRODUCTS ---
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_draft', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('admin_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('original_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_products_admin_id'), ['admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_is_draft'), ['is_draft'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_original_id'), ['original_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_products_original_id_products',
            'products',
            ['original_id'],
            ['id'],
            ondelete='SET NULL'
        )

    # --- TEMPLATES ---
    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.create_unique_constraint(batch_op.f('uq_templates_name'), ['name'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_templates_name'), type_='unique')

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('fk_products_original_id_products', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_products_original_id'))
        batch_op.drop_index(batch_op.f('ix_products_is_draft'))
        batch_op.drop_index(batch_op.f('ix_products_admin_id'))
        batch_op.drop_column('original_id')
        batch_op.drop_column('admin_id')
        batch_op.drop_column('is_draft')

    with op.batch_alter_table('locale_texts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_entity_lang_draft', type_='unique')
        batch_op.drop_index(batch_op.f('ix_locale_texts_is_draft'))
        batch_op.drop_index(batch_op.f('ix_locale_texts_admin_id'))
        batch_op.create_unique_constraint('uq_entity_lang', ['entity_type', 'entity_id', 'language_code'])
        batch_op.alter_column(
            'text',
            existing_type=sa.Text(),
            type_=sa.VARCHAR(),
            existing_nullable=False
        )
        batch_op.drop_column('admin_id')
        batch_op.drop_column('is_draft')

    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_constraint('fk_categories_original_id_categories', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_categories_original_id'))
        batch_op.drop_index(batch_op.f('ix_categories_is_draft'))
        batch_op.drop_index(batch_op.f('ix_categories_admin_id'))
        batch_op.drop_column('original_id')
        batch_op.drop_column('admin_id')
        batch_op.drop_column('is_draft')