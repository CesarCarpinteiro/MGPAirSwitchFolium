"""Margens por marca em cada orçamento e itens incluídos nas linhas

Revision ID: d1f3b5a7c9e2
Revises: c9e1a3b5d7f0
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1f3b5a7c9e2'
down_revision = 'c9e1a3b5d7f0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('orcamentos', sa.Column('margens', sa.Text(), nullable=True))
    op.add_column('organizacao', sa.Column('orc_incluidos', sa.Text(), nullable=True))
    op.add_column('orcamento_linhas', sa.Column('incluido', sa.Boolean(), nullable=True))
    op.add_column('orcamento_linhas', sa.Column('preco_catalogo', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('orcamento_linhas', 'preco_catalogo')
    op.drop_column('orcamento_linhas', 'incluido')
    op.drop_column('organizacao', 'orc_incluidos')
    op.drop_column('orcamentos', 'margens')
