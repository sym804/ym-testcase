"""users.token_version 추가 - 발급한 JWT 를 되돌리는 수단

Revision ID: c2f8a90b3d14
Revises: b7c31d9e42f8
Create Date: 2026-09-17 00:00:00.000000

JWT 는 발급하면 만료까지 서버가 막을 수 없다. 로그인 유지가 3650일이었고
로그아웃은 쿠키만 지웠으므로, 본문으로 받은 access_token 하나가 10년 동안
유효했다. 비밀번호를 바꿔도 그 토큰은 그대로 통했다.

사용자 행에 버전을 두고 토큰에 실어 요청마다 대조하면, 비밀번호가 바뀌는
자리에서 값을 올리는 것만으로 그 사용자의 옛 토큰이 한 번에 막힌다.

기존 행은 0 으로 채운다. 이 배포 이전에 발급된 토큰에는 `ver` 클레임이 아예
없으므로, 대조에서 None != 0 이 되어 함께 막힌다. 한 번은 다시 로그인해야 한다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2f8a90b3d14"
down_revision: Union[str, Sequence[str], None] = "b7c31d9e42f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
