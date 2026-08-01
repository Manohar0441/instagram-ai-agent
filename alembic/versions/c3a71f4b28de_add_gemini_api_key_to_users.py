"""add gemini api key to users

Revision ID: c3a71f4b28de
Revises: 4f946de6dbf1
Create Date: 2026-08-01 11:42:18.104772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3a71f4b28de'
down_revision: Union[str, Sequence[str], None] = '4f946de6dbf1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fernet ciphertext, so Text rather than a bounded String. Nullable
    # because existing users have no key and fall back to GOOGLE_API_KEY.
    op.add_column('users', sa.Column('gemini_api_key', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'gemini_api_key')
