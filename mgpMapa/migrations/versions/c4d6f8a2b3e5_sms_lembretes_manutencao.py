"""sms: lembretes automaticos de manutencao

Revision ID: c4d6f8a2b3e5
Revises: b8e2d4f6a1c3
Create Date: 2026-11-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d6f8a2b3e5'
down_revision = 'b8e2d4f6a1c3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('registos') as batch_op:
        batch_op.add_column(sa.Column('lembrete_8m', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('lembrete_10m', sa.String(length=20), nullable=True))
    with op.batch_alter_table('organizacao') as batch_op:
        batch_op.add_column(sa.Column('sms_lembretes', sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('organizacao') as batch_op:
        batch_op.drop_column('sms_lembretes')
    with op.batch_alter_table('registos') as batch_op:
        batch_op.drop_column('lembrete_10m')
        batch_op.drop_column('lembrete_8m')
