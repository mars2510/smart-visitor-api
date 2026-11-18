from typing import Sequence, Union

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c84a1f2d9e71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

from sqlalchemy import Column, String
from alembic import op

def upgrade() -> None:
    op.add_column("pengguna", Column("email", String, nullable=True))
    op.create_index(op.f("ix_pengguna_email"), "pengguna", ["email"], unique=True)

def downgrade() -> None:
    op.drop_index(op.f("ix_pengguna_email"), table_name="pengguna")
    op.drop_column("pengguna", "email")