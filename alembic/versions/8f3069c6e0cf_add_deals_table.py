"""add deals table

Revision ID: 8f3069c6e0cf
Revises: d8f4c1a92b6e
Create Date: 2026-08-03 17:12:08.838321

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f3069c6e0cf'
down_revision: Union[str, Sequence[str], None] = 'd8f4c1a92b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'deals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('brand_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('deliverables', sa.Text(), nullable=True),
        sa.Column('deal_status', sa.String(length=20), server_default='negotiating', nullable=False),
        sa.Column('shoot_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), server_default='INR', nullable=False),
        sa.Column('payment_status', sa.String(length=10), server_default='unpaid', nullable=False),
        sa.Column('payment_due_date', sa.Date(), nullable=True),
        sa.Column('work_link', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deals_user_id'), 'deals', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_deals_user_id'), table_name='deals')
    op.drop_table('deals')
