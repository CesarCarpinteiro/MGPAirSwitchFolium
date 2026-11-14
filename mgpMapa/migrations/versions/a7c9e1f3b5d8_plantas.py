"""plantas: planta da casa com o desenho da instalacao de AC

Revision ID: a7c9e1f3b5d8
Revises: f1a3c5e7b9d2
Create Date: 2026-11-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c9e1f3b5d8'
down_revision = 'f1a3c5e7b9d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'plantas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('org_id', sa.Integer(), sa.ForeignKey('organizacao.id'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('usuario.id', ondelete='SET NULL'), nullable=True),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('morada', sa.String(length=300), nullable=True),
        sa.Column('imagem', sa.String(length=100), nullable=False),
        sa.Column('largura', sa.Integer(), nullable=False),
        sa.Column('altura', sa.Integer(), nullable=False),
        sa.Column('desenho', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_plantas_org_id', 'plantas', ['org_id'])


def downgrade():
    op.drop_index('ix_plantas_org_id', table_name='plantas')
    op.drop_table('plantas')
