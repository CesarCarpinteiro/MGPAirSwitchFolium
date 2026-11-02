"""orcamento automatico: catalogo de produtos e linhas de orcamento

Revision ID: a3c5e7f9b1d2
Revises: 122fd4b793bd
Create Date: 2026-10-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c5e7f9b1d2'
down_revision = '122fd4b793bd'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('produtos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('org_id', sa.Integer(), nullable=False),
    sa.Column('marca', sa.String(length=100), nullable=True),
    sa.Column('modelo', sa.String(length=200), nullable=False),
    sa.Column('descricao', sa.String(length=300), nullable=True),
    sa.Column('categoria', sa.String(length=100), nullable=True),
    sa.Column('preco', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizacao.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_produtos_org_id', 'produtos', ['org_id'])
    op.create_table('orcamento_linhas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('orcamento_id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=True),
    sa.Column('descricao', sa.String(length=300), nullable=False),
    sa.Column('quantidade', sa.Float(), nullable=True),
    sa.Column('preco_unitario', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['orcamento_id'], ['orcamentos.id'], ),
    sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('orcamentos') as batch_op:
        batch_op.add_column(sa.Column('cliente_nif', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('cliente_contacto', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('cliente_email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('cliente_morada', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('desconto', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('iva_taxa', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('orcamentos') as batch_op:
        batch_op.drop_column('iva_taxa')
        batch_op.drop_column('desconto')
        batch_op.drop_column('cliente_morada')
        batch_op.drop_column('cliente_email')
        batch_op.drop_column('cliente_contacto')
        batch_op.drop_column('cliente_nif')
    op.drop_table('orcamento_linhas')
    op.drop_index('ix_produtos_org_id', table_name='produtos')
    op.drop_table('produtos')
