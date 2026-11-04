"""lembretes sms: preparados na vespera, com cancelar/enviar ja

Revision ID: f1a3c5e7b9d2
Revises: e2f4b6c8d0a1
Create Date: 2026-11-04 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a3c5e7b9d2'
down_revision = 'e2f4b6c8d0a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lembretes_sms',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('org_id', sa.Integer(), sa.ForeignKey('organizacao.id'), nullable=False),
        sa.Column('registo_id', sa.Integer(), sa.ForeignKey('registos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tipo', sa.String(length=5), nullable=False),
        sa.Column('referencia', sa.String(length=20), nullable=False),
        sa.Column('texto', sa.String(length=400), nullable=False),
        sa.Column('enviar_em', sa.Date(), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=True),
        sa.Column('motivo', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('enviado_em', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('registo_id', 'tipo', 'referencia', name='uq_lembrete_registo_tipo_ref'),
    )
    # Substituído pela tabela acima
    with op.batch_alter_table('registos') as batch_op:
        batch_op.drop_column('lembrete_10m')
        batch_op.drop_column('lembrete_8m')


def downgrade():
    with op.batch_alter_table('registos') as batch_op:
        batch_op.add_column(sa.Column('lembrete_8m', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('lembrete_10m', sa.String(length=20), nullable=True))
    op.drop_table('lembretes_sms')
