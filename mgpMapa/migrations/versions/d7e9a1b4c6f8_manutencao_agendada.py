"""registos: data da proxima manutencao ja agendada

Revision ID: d7e9a1b4c6f8
Revises: c4d6f8a2b3e5
Create Date: 2026-11-04 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e9a1b4c6f8'
down_revision = 'c4d6f8a2b3e5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('registos') as batch_op:
        batch_op.add_column(sa.Column('manutencao_agendada', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('registos') as batch_op:
        batch_op.drop_column('manutencao_agendada')
