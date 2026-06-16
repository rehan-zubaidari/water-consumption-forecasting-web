"""Update forecast table schema

Revision ID: 8306fe0b170b
Revises: d42a05697879
Create Date: 2025-08-24 11:35:55.446942

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8306fe0b170b'
down_revision = 'd42a05697879'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('forecast', schema=None) as batch_op:
        batch_op.alter_column('rute_id',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.alter_column('tanggal_entry',
               existing_type=sa.DATETIME(),
               nullable=True,
               existing_server_default=sa.text('(CURRENT_TIMESTAMP)'))

    with op.batch_alter_table('kategori_golongan', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_kategori_golongan_golongan', ['golongan'])

    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('kategori_golongan', schema=None) as batch_op:
        batch_op.drop_constraint('uq_kategori_golongan_golongan', type_='unique')

    with op.batch_alter_table('forecast', schema=None) as batch_op:
        batch_op.alter_column('tanggal_entry',
               existing_type=sa.DATETIME(),
               nullable=False,
               existing_server_default=sa.text('(CURRENT_TIMESTAMP)'))
        batch_op.alter_column('rute_id',
               existing_type=sa.INTEGER(),
               nullable=False)


    # ### end Alembic commands ###
