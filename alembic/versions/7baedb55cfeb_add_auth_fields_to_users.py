"""add auth fields to users

Revision ID: 7baedb55cfeb
Revises: fd4ce6257d73
Create Date: 2026-07-31 19:03:45.276254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7baedb55cfeb'
down_revision: Union[str, Sequence[str], None] = 'fd4ce6257d73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email', sa.String(length=255), nullable=False))
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=False))
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_column('users', 'hashed_password')
    op.drop_column('users', 'email')
