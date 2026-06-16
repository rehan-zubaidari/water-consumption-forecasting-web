"""Add NIK column

Revision ID: 3dc6bf8e1e9a
Revises: a700b24e1b33
Create Date: 2025-08-28 18:42:34.321304

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3dc6bf8e1e9a'
down_revision = 'a700b24e1b33'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nik', sa.String(length=16), nullable=True))
        # kasih nama constraint unik eksplisit
        batch_op.create_unique_constraint('uq_user_nik', ['nik'])


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_nik', type_='unique')
        batch_op.drop_column('nik')

