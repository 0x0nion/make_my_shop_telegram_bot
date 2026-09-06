"""set_default_is_active_true

Revision ID: 0a19a4fad51a
Revises: 2afe68beccaa
Create Date: 2026-08-07 18:45:00.158007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a19a4fad51a'
down_revision: Union[str, Sequence[str], None] = '2afe68beccaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Проставляем True (1) всем существенным записям
    op.execute("UPDATE categories SET is_active = 1 WHERE is_active IS NULL OR is_active = 0")
    op.execute("UPDATE products SET is_active = 1 WHERE is_active IS NULL OR is_active = 0")
    op.execute("UPDATE temp_categories SET is_active = 1 WHERE is_active IS NULL OR is_active = 0")
    op.execute("UPDATE temp_products SET is_active = 1 WHERE is_active IS NULL OR is_active = 0")


def downgrade() -> None:
    pass
