"""Margem do orçamento por marca

Revision ID: b8d0f2a4c6e9
Revises: a7c9e1f3b5d8
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8d0f2a4c6e9'
down_revision = 'a7c9e1f3b5d8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('organizacao', sa.Column('orc_margens_marca', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('organizacao', 'orc_margens_marca')
