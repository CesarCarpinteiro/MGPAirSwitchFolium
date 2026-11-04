"""obras: ligacao a registos e servicos (marcacoes automaticas)

Revision ID: e2f4b6c8d0a1
Revises: d7e9a1b4c6f8
Create Date: 2026-11-04 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2f4b6c8d0a1'
down_revision = 'd7e9a1b4c6f8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('obras') as batch_op:
        batch_op.add_column(sa.Column('registo_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('servico_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_obras_registo', 'registos', ['registo_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_obras_servico', 'servicos', ['servico_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('obras') as batch_op:
        batch_op.drop_constraint('fk_obras_servico', type_='foreignkey')
        batch_op.drop_constraint('fk_obras_registo', type_='foreignkey')
        batch_op.drop_column('servico_id')
        batch_op.drop_column('registo_id')
