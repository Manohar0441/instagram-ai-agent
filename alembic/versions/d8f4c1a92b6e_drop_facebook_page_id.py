"""drop facebook_page_id

Revision ID: d8f4c1a92b6e
Revises: c3a71f4b28de
Create Date: 2026-08-01 22:14:07.318452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f4c1a92b6e'
down_revision: Union[str, Sequence[str], None] = 'c3a71f4b28de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Meta replaced the Facebook-Login-based Instagram Graph API with
    # Instagram API with Instagram Login in 2024; the new flow logs in
    # directly to an Instagram account with no Facebook Page involved.
    op.drop_column('instagram_accounts', 'facebook_page_id')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('instagram_accounts', sa.Column('facebook_page_id', sa.String(length=64), nullable=False))
