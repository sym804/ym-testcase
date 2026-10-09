"""연결된 Google 계정의 이메일 칸: users.google_email.

email 칸은 다른 계정이 그 주소를 쥐고 있으면 비어 있게 된다. 관리자가 어느 Google 계정이
연결됐는지 확인할 수 있게 연결·로그인 때마다 따로 남긴다. 기존 연결은 다음 Google 로그인 때 채워진다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_google_email"
down_revision = "0007_account_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_email", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "google_email")
