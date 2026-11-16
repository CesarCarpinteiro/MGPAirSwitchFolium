"""Link público para partilhar o orçamento

Revision ID: f5b7d9c1e3a6
Revises: e4a6c8b0d2f5
"""
from alembic import op
import sqlalchemy as sa

revision = 'f5b7d9c1e3a6'
down_revision = 'e4a6c8b0d2f5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orcamentos', sa.Column('partilha_token', sa.String(64), nullable=True))
    op.create_index('ix_orcamentos_partilha_token', 'orcamentos', ['partilha_token'], unique=True)


def downgrade():
    op.drop_index('ix_orcamentos_partilha_token', table_name='orcamentos')
    op.drop_column('orcamentos', 'partilha_token')
