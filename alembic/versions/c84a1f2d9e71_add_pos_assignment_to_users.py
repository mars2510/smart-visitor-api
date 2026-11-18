"""add POS assignment to users

Revision ID: c84a1f2d9e71
Revises: 4bf9e6bdf81e
Create Date: 2026-11-08 13:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c84a1f2d9e71"
down_revision: Union[str, Sequence[str], None] = "4bf9e6bdf81e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pengguna", sa.Column("id_pos", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_pengguna_pos",
        "pengguna",
        "pos",
        ["id_pos"],
        ["id_pos"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_pengguna_pos", "pengguna", type_="foreignkey")
    op.drop_column("pengguna", "id_pos")
