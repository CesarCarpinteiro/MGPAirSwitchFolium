"""orcamento: termos, condicoes de pagamento e definicoes da organizacao

Revision ID: b8e2d4f6a1c3
Revises: a3c5e7f9b1d2
Create Date: 2026-10-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e2d4f6a1c3'
down_revision = 'a3c5e7f9b1d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('orcamentos') as batch_op:
        batch_op.add_column(sa.Column('termos', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('condicoes_pagamento', sa.Text(), nullable=True))
    with op.batch_alter_table('organizacao') as batch_op:
        batch_op.add_column(sa.Column('designacao_social', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('morada', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('redes', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('nif', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('logo', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('orc_margem', sa.Float(), nullable=True, server_default='35'))
        batch_op.add_column(sa.Column('orc_termos', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('orc_pagamento', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('organizacao') as batch_op:
        for col in ['orc_pagamento', 'orc_termos', 'orc_margem', 'logo', 'nif', 'redes', 'email', 'morada',
                    'designacao_social']:
            batch_op.drop_column(col)
    with op.batch_alter_table('orcamentos') as batch_op:
        batch_op.drop_column('condicoes_pagamento')
        batch_op.drop_column('termos')
