"""인증 테스트 도우미. 사용자는 ORM 으로 바로 만들고 요청은 실제 HTTP 로 보낸다."""
import requests

from auth import hash_password
from models import User, UserRole, UserStatus

PW = "Passw0rd!long"


def make_user(Session, *, username, email=None, role=UserRole.user, status=UserStatus.active,
              password=PW, google_sub=None, email_verified=False, display_name=None) -> int:
    s = Session()
    try:
        u = User(username=username, email=email, role=role, status=status,
                 password_hash=hash_password(password) if password else None,
                 google_sub=google_sub, email_verified=email_verified,
                 display_name=display_name or username)
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def login(base, ident, password=PW):
    return requests.post(base + "/api/auth/login", json={"username": ident, "password": password})


def bearer(resp) -> dict:
    assert resp.status_code == 200, resp.text
    return {"Authorization": "Bearer " + resp.json()["access_token"]}
