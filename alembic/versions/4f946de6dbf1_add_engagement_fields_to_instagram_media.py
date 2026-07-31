"""add engagement fields to instagram media

Revision ID: 4f946de6dbf1
Revises: 8adb28f8f995
Create Date: 2026-07-31 22:17:23.159390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f946de6dbf1'
down_revision: Union[str, Sequence[str], None] = '8adb28f8f995'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('instagram_media', sa.Column('like_count', sa.Integer(), nullable=True))
    op.add_column('instagram_media', sa.Column('comments_count', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('instagram_media', 'comments_count')
    op.drop_column('instagram_media', 'like_count')
