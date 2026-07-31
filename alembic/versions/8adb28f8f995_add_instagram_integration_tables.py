"""add instagram integration tables

Revision ID: 8adb28f8f995
Revises: 7baedb55cfeb
Create Date: 2026-07-31 21:52:28.284778

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8adb28f8f995'
down_revision: Union[str, Sequence[str], None] = '7baedb55cfeb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'instagram_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('instagram_user_id', sa.String(length=64), nullable=False),
        sa.Column('facebook_page_id', sa.String(length=64), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('account_type', sa.String(length=50), nullable=True),
        sa.Column('biography', sa.Text(), nullable=True),
        sa.Column('profile_picture_url', sa.Text(), nullable=True),
        sa.Column('followers_count', sa.Integer(), nullable=True),
        sa.Column('media_count', sa.Integer(), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_instagram_accounts_user_id'), 'instagram_accounts', ['user_id'], unique=True)
    op.create_index(op.f('ix_instagram_accounts_instagram_user_id'), 'instagram_accounts', ['instagram_user_id'], unique=True)

    op.create_table(
        'instagram_media',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instagram_account_id', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.String(length=64), nullable=False),
        sa.Column('media_type', sa.String(length=50), nullable=False),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('media_url', sa.Text(), nullable=True),
        sa.Column('permalink', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['instagram_account_id'], ['instagram_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_instagram_media_instagram_account_id'), 'instagram_media', ['instagram_account_id'], unique=False)
    op.create_index(op.f('ix_instagram_media_media_id'), 'instagram_media', ['media_id'], unique=True)

    op.create_table(
        'media_insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.Integer(), nullable=False),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['media_id'], ['instagram_media.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_media_insights_media_id'), 'media_insights', ['media_id'], unique=False)

    op.create_table(
        'account_insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('instagram_account_id', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=False),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['instagram_account_id'], ['instagram_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_account_insights_instagram_account_id'), 'account_insights', ['instagram_account_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_account_insights_instagram_account_id'), table_name='account_insights')
    op.drop_table('account_insights')

    op.drop_index(op.f('ix_media_insights_media_id'), table_name='media_insights')
    op.drop_table('media_insights')

    op.drop_index(op.f('ix_instagram_media_media_id'), table_name='instagram_media')
    op.drop_index(op.f('ix_instagram_media_instagram_account_id'), table_name='instagram_media')
    op.drop_table('instagram_media')

    op.drop_index(op.f('ix_instagram_accounts_instagram_user_id'), table_name='instagram_accounts')
    op.drop_index(op.f('ix_instagram_accounts_user_id'), table_name='instagram_accounts')
    op.drop_table('instagram_accounts')
