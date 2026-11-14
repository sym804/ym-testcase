"""스테이징 업로드 주소 발급의 사용자별 상한(SYM-219).

발급 한 번이 최대 50MB 저장소 자리다. 정리는 하루 뒤 Cron 이 하므로, 상한이 없으면 로그인한
사용자 하나가 발급을 반복해 저장소 용량과 요금을 소모시킬 수 있다.

- 최근 1시간에 발급하고 처리하지 않은(consumed_at 이 빈) 업로드 개수와 선언 크기 합계에 상한
- 시간당 발급 횟수에 상한(처리했든 안 했든 센다)
"""
import pytest
import requests
from fastapi import HTTPException

from auth_helpers import bearer, login, make_user
from models import StagedUpload, User, now_kst
from services import staged_upload

MB = 1024 * 1024


def _new(Session, uid, size=10, purpose="tc_import"):
    with Session() as s:
        row = staged_upload.new_upload(s, s.get(User, uid), purpose, "a.xlsx", size, None)
        s.commit()
        return row.id


def _consume(Session, upload_id):
    with Session() as s:
        s.get(StagedUpload, upload_id).consumed_at = now_kst()
        s.commit()


def test_처리하지_않은_업로드_개수_상한(auth_env, monkeypatch):
    monkeypatch.setenv("STAGING_MAX_PENDING", "3")
    uid = make_user(auth_env.Session, username="st1")
    ids = [_new(auth_env.Session, uid) for _ in range(3)]
    with pytest.raises(HTTPException) as e:
        _new(auth_env.Session, uid)
    assert e.value.status_code == 429
    assert e.value.detail == staged_upload.TOO_MANY_PENDING
    # 하나를 처리하면 자리가 난다
    _consume(auth_env.Session, ids[0])
    _new(auth_env.Session, uid)


def test_처리하지_않은_업로드_선언_크기_합계_상한(auth_env, monkeypatch):
    monkeypatch.setenv("STAGING_MAX_PENDING_MB", "1")
    uid = make_user(auth_env.Session, username="st2")
    _new(auth_env.Session, uid, size=600 * 1024)
    with pytest.raises(HTTPException) as e:
        _new(auth_env.Session, uid, size=600 * 1024)
    assert (e.value.status_code, e.value.detail) == (429, staged_upload.TOO_MANY_PENDING)
    # 합계가 상한 안이면 받는다
    _new(auth_env.Session, uid, size=300 * 1024)


def test_시간당_발급_상한은_처리한_업로드도_센다(auth_env, monkeypatch):
    monkeypatch.setenv("STAGING_MAX_PER_HOUR", "2")
    uid = make_user(auth_env.Session, username="st3")
    for _ in range(2):
        _consume(auth_env.Session, _new(auth_env.Session, uid))
    with pytest.raises(HTTPException) as e:
        _new(auth_env.Session, uid)
    assert (e.value.status_code, e.value.detail) == (429, staged_upload.TOO_MANY_UPLOADS)


def test_거절된_발급은_시간당_횟수에_세지_않는다(auth_env, monkeypatch):
    """크기 초과(413)나 개수 상한(429)으로 거절된 요청까지 세면, 막힌 동안 계속 시도한 사용자가
    상한이 풀린 뒤에도 한 시간 더 막힌다."""
    monkeypatch.setenv("STAGING_MAX_PER_HOUR", "3")
    monkeypatch.setenv("STAGING_MAX_PENDING", "1")
    uid = make_user(auth_env.Session, username="st4")
    for _ in range(3):
        with pytest.raises(HTTPException) as e:
            _new(auth_env.Session, uid, size=11 * MB)
        assert e.value.status_code == 413
    first = _new(auth_env.Session, uid)  # 1회
    for _ in range(3):
        with pytest.raises(HTTPException) as e:
            _new(auth_env.Session, uid)
        assert (e.value.status_code, e.value.detail) == (429, staged_upload.TOO_MANY_PENDING)
    _consume(auth_env.Session, first)
    _consume(auth_env.Session, _new(auth_env.Session, uid))  # 2회
    _new(auth_env.Session, uid)  # 3회. 거절 6건을 셌다면 여기서 막힌다


def test_다른_사용자는_영향이_없다(auth_env, monkeypatch):
    monkeypatch.setenv("STAGING_MAX_PENDING", "1")
    a = make_user(auth_env.Session, username="st5a")
    b = make_user(auth_env.Session, username="st5b")
    _new(auth_env.Session, a)
    with pytest.raises(HTTPException):
        _new(auth_env.Session, a)
    _new(auth_env.Session, b)


def test_발급_API_는_429_와_사유를_준다(auth_env, monkeypatch):
    monkeypatch.setenv("STAGING_MAX_PENDING", "1")
    make_user(auth_env.Session, username="st6")
    h = bearer(login(auth_env.base, "st6"))

    def post():
        return requests.post(auth_env.base + "/api/uploads", headers=h, json={
            "purpose": "tc_import", "filename": "a.xlsx", "size": 10, "content_type": None})

    assert post().status_code == 201
    r = post()
    assert (r.status_code, r.json()["detail"]) == (429, staged_upload.TOO_MANY_PENDING)


def test_한_시간_지난_미처리_업로드는_세지_않는다(auth_env, monkeypatch):
    """미리보기·dry run 은 처리 표시를 롤백한다. 그만둔 업로드를 정리(하루 뒤)까지 세면 그동안
    업로드를 전혀 못 한다(QA1 지적)."""
    from datetime import timedelta

    monkeypatch.setenv("STAGING_MAX_PENDING", "2")
    uid = make_user(auth_env.Session, username="st7")
    ids = [_new(auth_env.Session, uid) for _ in range(2)]
    with pytest.raises(HTTPException):
        _new(auth_env.Session, uid)
    with auth_env.Session() as s:
        for i in ids:
            s.get(StagedUpload, i).created_at = now_kst() - timedelta(hours=1, minutes=1)
        s.commit()
    _new(auth_env.Session, uid)


def test_선언_크기_합계는_상한과_같으면_받고_1바이트_넘으면_거절(auth_env, monkeypatch):
    monkeypatch.setenv("STAGING_MAX_PENDING_MB", "1")
    a = make_user(auth_env.Session, username="st8a")
    _new(auth_env.Session, a, size=512 * 1024)
    _new(auth_env.Session, a, size=512 * 1024)
    b = make_user(auth_env.Session, username="st8b")
    _new(auth_env.Session, b, size=512 * 1024)
    with pytest.raises(HTTPException):
        _new(auth_env.Session, b, size=512 * 1024 + 1)


def test_서명_주소를_받는_동안_할당량_잠금을_쥐지_않는다(auth_env, monkeypatch):
    """서명은 외부 호출(최대 30초)이다. 잠금을 쥔 채 부르면 같은 사용자의 다음 발급이 409 다(QA1 지적)."""
    from routes import uploads as uploads_route

    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "300")
    uid = make_user(auth_env.Session, username="st9")
    h = bearer(login(auth_env.base, "st9"))
    inner = []
    real = staged_upload.upload_target

    def slow_target(row):
        if not inner:
            # 첫 발급이 서명을 기다리는 동안 같은 사용자가 또 발급한다
            inner.append(_new(auth_env.Session, uid))
        return real(row)

    monkeypatch.setattr(uploads_route.staged_upload, "upload_target", slow_target)
    r = requests.post(auth_env.base + "/api/uploads", headers=h, json={
        "purpose": "tc_import", "filename": "a.xlsx", "size": 10, "content_type": None})
    assert r.status_code == 201, r.text
    assert len(inner) == 1


def test_서명_주소_발급이_실패하면_발급_기록을_지운다(auth_env, monkeypatch):
    from routes import uploads as uploads_route

    uid = make_user(auth_env.Session, username="st10")
    h = bearer(login(auth_env.base, "st10"))

    def broken(row):
        raise RuntimeError("storage down")

    monkeypatch.setattr(uploads_route.staged_upload, "upload_target", broken)
    r = requests.post(auth_env.base + "/api/uploads", headers=h, json={
        "purpose": "tc_import", "filename": "a.xlsx", "size": 10, "content_type": None})
    assert r.status_code == 500
    with auth_env.Session() as s:
        assert s.query(StagedUpload).filter(StagedUpload.user_id == uid).count() == 0


def test_동시에_발급해도_미처리_상한을_넘지_못한다(auth_env, monkeypatch):
    """잠금 없이 세면 동시에 온 발급이 모두 0건을 보고 통과한다(PostgreSQL 전환 뒤 4건 동시 성공과 같은 유형)."""
    import threading
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("STAGING_MAX_PENDING", "1")
    uid = make_user(auth_env.Session, username="st11")
    barrier = threading.Barrier(6)

    def run(_):
        barrier.wait()
        try:
            _new(auth_env.Session, uid)
            return 201
        except HTTPException as e:
            return e.status_code

    with ThreadPoolExecutor(max_workers=6) as ex:
        codes = list(ex.map(run, range(6)))
    assert sorted(codes) == [201] + [429] * 5, codes


def test_상한_기본값(monkeypatch):
    for k in ("STAGING_MAX_PENDING", "STAGING_MAX_PENDING_MB", "STAGING_MAX_PER_HOUR"):
        monkeypatch.delenv(k, raising=False)
    assert staged_upload._pending_limit() == 30
    assert staged_upload._pending_bytes_limit() == 500 * MB
    assert staged_upload._hourly_limit() == 120
