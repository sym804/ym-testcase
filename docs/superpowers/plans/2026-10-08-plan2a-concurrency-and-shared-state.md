# 계획 2a: 동시성 계약과 공유 상태 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PostgreSQL 에서 동시 요청이 와도 번호, 회차, 최초 관리자, 결과 수정, 1회용 코드가 깨지지 않고, 로그인 잠금이 여러 실행 환경에서 같은 횟수를 본다.

**Architecture:** 프로젝트 단위 advisory lock 을 라우터 의존성으로 걸어 TC·시트 변경 요청을 프로젝트별로 줄 세운다. 행 하나를 다투는 경쟁(결과 수정, 1회용 코드)은 `SELECT ... FOR UPDATE` 로 막는다. 로그인 실패와 계정 요청 제출 횟수는 DB 테이블로 옮기고, 요청 세션과 무관한 자체 트랜잭션으로 기록한다.

**Tech Stack:** PostgreSQL 17 advisory lock, SQLAlchemy 2.0 `with_for_update`, Alembic, pytest + 실서버 스레드 동시 요청.

**Spec:** `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md` (동시성 계약, 공유 상태, 시간 절)

## Global Constraints

- 작업 위치: worktree `C:\Users\ymseo\Documents\tc_manager-pg`, 브랜치 `feat/postgresql`. 계획 1 위에 쌓는다.
- 테스트 실행: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 TEST_ADMIN_PASSWORD=test1234 python -m pytest ...`
- 동시성 테스트는 배리어로 시작을 맞추고, 성공 건수·증가량·중복 0건을 정확히 단언하며, 잠금을 뺀 코드에서 실패하는지 먼저 확인한다(스펙 테스트 절).
- 잠금 키는 `pg_advisory_xact_lock(int4, int4)` 두 정수 형태. 첫째는 용도(`services/locks.py` 의 `LockNs`), 둘째는 대상 id.
- 엠대시, 엔대시 금지.

## Review Focus

- 잠금 의존성보다 먼저 `commit()` 하는 의존성(API 키 사용 시각 갱신)이 있으면 잠금이 그 뒤 새 트랜잭션에서 잡히는가. Task 1 테스트가 API 키 인증 요청으로도 동시 복제를 돌려 고정한다.
- 라우트 안의 중간 `commit()` 뒤 번호를 읽는 곳: 잠금이 풀린 상태다. Task 1 에서 대상 라우트의 `commit()` 위치를 전수 확인하고, 번호를 읽기 전 커밋이 있으면 잠금을 다시 잡는다.
- 프록시 헤더가 없는 로컬과 있는 배포에서 IP 판정이 다르게 나오는 경우. Task 6 테스트가 두 경우를 고정한다.
- 접수 제한 테이블이 커지는 경우: 오래된 행을 지우는 함수가 있고 Cron(계획 2b)이 부른다. Task 6 테스트가 지우기 함수를 고정한다.
- 시간대: 리포트 파일명 날짜가 서버 시간대(UTC)와 무관하게 KST 인가. Task 7 테스트가 `TZ=UTC` 하위 프로세스로 고정한다.

---

### Task 1: 프로젝트 단위 쓰기 잠금

**Files:**
- Create: `backend/services/locks.py`
- Modify: `backend/routes/testcases.py` (모든 POST/PUT/DELETE 라우트에 의존성 추가)
- Modify: `backend/routes/sheets.py` (POST/PUT/DELETE 라우트)
- Modify: `backend/routes/testruns.py` (런 복제·다음 회차 라우트)
- Modify: `backend/test_tc_clone_concurrent.py`

**Interfaces:**
- Produces:
  - `services.locks.LockNs(IntEnum)`: `PROJECT_WRITE = 1`, `FIRST_ADMIN = 2`, `CRON = 3`
  - `services.locks.advisory_xact_lock(db: Session, ns: LockNs, key: int = 0) -> None`
  - `services.locks.project_write_lock(project_id: int, db: Session = Depends(get_db)) -> None` (FastAPI 의존성)

- [ ] **Step 1: 동시 복제 테스트를 정확한 단언으로 바꾼다 (실패하는 테스트)**

`test_tc_clone_concurrent.py` 의 두 테스트에서 `created` 단언을 바꾼다.

```python
    statuses = [r.status_code for r in responses]
    assert statuses == [201] * FANOUT, f"동시 복제 중 실패가 있다: {statuses}"
    created = [r.json()["no"] for r in responses]
```

`bulk` 테스트도 같은 방식으로 `[201] * FANOUT` 을 단언하고, 최종 번호 목록이 `list(range(1, FANOUT + 2))` 와 같은지 본다(원본 1 + 복제 FANOUT). 파일 docstring 의 "`no` 에 유니크 제약이 없어" 문장은 "유니크 제약이 실패 쪽을 409 로 만들어 번호는 이어지지만 요청이 실패한다" 로 고친다.

스레드 시작을 맞추기 위해 `threading.Barrier(FANOUT)` 를 두고 각 작업이 `barrier.wait()` 뒤 요청을 보낸다.

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest test_tc_clone_concurrent.py -q`
Expected: FAIL, 상태 목록에 409 또는 500 이 섞인다. 섞이지 않으면 `FANOUT` 을 16 으로 올려 다시 본다. 그래도 통과하면 잠금 없이 경쟁이 재현되지 않는 것이므로 원장에 기록하고 Step 4 의 잠금 제거 확인으로 대신한다.

- [ ] **Step 3: 구현**

`backend/services/locks.py`:

```python
"""PostgreSQL advisory lock 으로 요청을 줄 세운다.

SQLite 는 쓰기를 파일 잠금으로 한 줄로 세워서, "최댓값을 읽고 +1 해서 쓰는" 코드가
우연히 안전했다. PostgreSQL 은 두 트랜잭션이 같은 값을 읽고 둘 다 쓴다.

★트랜잭션 잠금(xact)만 쓴다. 커밋이나 롤백에서 저절로 풀리므로 Supabase 트랜잭션
  풀러에서도 같은 트랜잭션 안에서는 유지된다. 세션 잠금은 풀러에서 다른 요청과 섞인다.
★중간 commit() 뒤에는 잠금이 풀린 새 트랜잭션이다. 번호를 다시 읽으면 다시 잡는다.
"""
from enum import IntEnum

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db


class LockNs(IntEnum):
    PROJECT_WRITE = 1
    FIRST_ADMIN = 2
    CRON = 3


def advisory_xact_lock(db: Session, ns: LockNs, key: int = 0) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(:ns, :key)"), {"ns": int(ns), "key": int(key)})


def project_write_lock(project_id: int, db: Session = Depends(get_db)) -> None:
    """TC·시트를 바꾸는 요청을 프로젝트별로 줄 세운다.

    번호(no), TC ID, 시트 순서, 다음 회차가 모두 "현재 값을 읽고 정하는" 구조라
    라우트마다 따로 잠그면 빠뜨린다. 프로젝트 단위로 한 번에 잡는다.
    """
    advisory_xact_lock(db, LockNs.PROJECT_WRITE, project_id)
```

라우트에는 의존성을 인증 의존성 **뒤에** 둔다. 인증이 API 키 사용 시각을 커밋하면 그 뒤에 잡아야 잠금이 요청 끝까지 유지된다.

```python
@router.post("/{tc_id}/clone", response_model=TestCaseResponse, status_code=201)
def clone_testcase(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
    _lock: None = Depends(project_write_lock),
):
```

`routes/testcases.py` 의 `create_testcase`, `bulk_update_testcases`, `reorder_testcases`, `update_testcase`, `bulk_delete_testcases`, `delete_testcase`, `restore_testcase`, `bulk_clone_testcases`, `clone_testcase`, `import_testcases` 와 `routes/sheets.py` 의 `create_sheet`, `rename_sheet`, `move_sheet`, `delete_sheet`, `routes/testruns.py` 의 런 복제 라우트(`_clone_run` 을 부르는 라우트)에 같은 줄을 넣는다. 의존성 인자가 항상 마지막이 되게 한다.

각 대상 라우트에서 번호를 읽는 줄보다 앞에 `db.commit()` 이 있는지 확인한다. 있으면 그 커밋 바로 뒤에 `advisory_xact_lock(db, LockNs.PROJECT_WRITE, project_id)` 를 한 번 더 부른다.

- [ ] **Step 4: 통과 확인과 이빨 확인**

Run: `python -m pytest test_tc_clone_concurrent.py -q`
Expected: PASS

`services/locks.py` 의 `advisory_xact_lock` 본문을 잠시 `return` 으로 바꿔 다시 돌린다.
Expected: FAIL. 확인 뒤 원복하고 다시 PASS 를 본다.

- [ ] **Step 5: 회귀 확인과 커밋**

Run: `python -m pytest test_tc_* test_sheet* tests_unit -q`
Expected: 실패 0

```bash
git add backend/services/locks.py backend/routes/testcases.py backend/routes/sheets.py backend/routes/testruns.py backend/test_tc_clone_concurrent.py
git commit -m "fix: TC·시트 변경을 프로젝트 단위 advisory lock 으로 직렬화 (SYM-6)"
```

---

### Task 2: 다음 회차 유니크 제약

**Files:**
- Create: `backend/alembic/versions/0002_unique_run_round.py`
- Modify: `backend/models.py` (`TestRun.__table_args__`)
- Test: `backend/tests_unit/test_run_round_unique.py`

**Interfaces:**
- Produces: 인덱스 `uq_test_runs_project_name_round` (`project_id`, `name`, `round`) unique

- [ ] **Step 1: 실패하는 테스트**

```python
"""같은 프로젝트, 같은 이름의 수행은 회차가 겹치지 않는다."""
import pytest
from sqlalchemy.exc import IntegrityError

from models import Project, TestRun, User


def test_같은_이름_같은_회차는_거부된다(pg_session):
    s = pg_session
    u = User(username="u", password_hash="x", display_name="u")
    s.add(u); s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p); s.flush()
    s.add(TestRun(project_id=p.id, name="R", round=1, created_by=u.id)); s.flush()
    s.add(TestRun(project_id=p.id, name="R", round=1, created_by=u.id))
    with pytest.raises(IntegrityError):
        s.flush()


def test_이름이_다르면_같은_회차도_된다(pg_session):
    s = pg_session
    u = User(username="u", password_hash="x", display_name="u")
    s.add(u); s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p); s.flush()
    s.add(TestRun(project_id=p.id, name="R", round=1, created_by=u.id))
    s.add(TestRun(project_id=p.id, name="Q", round=1, created_by=u.id))
    s.flush()
```

Run: `python -m pytest tests_unit/test_run_round_unique.py -q`
Expected: 첫 테스트 FAIL (중복이 들어감)

- [ ] **Step 2: 모델과 마이그레이션**

`models.py` 의 `TestRun.__table_args__` 에 더한다.

```python
        # 다음 회차는 max(round)+1 이다. 잠금(Task 1)이 줄을 세우지만 DB 도 막는다.
        Index("uq_test_runs_project_name_round", "project_id", "name", "round", unique=True),
```

`0002_unique_run_round.py`:

```python
"""수행 회차 유일성: (project_id, name, round)

추가 전에 중복을 확인한다. 있으면 멈추고 목록을 낸다. 자동으로 고치지 않는다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_unique_run_round"
down_revision = "0001_pg_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dup = op.get_bind().execute(sa.text(
        "SELECT project_id, name, round, count(*) FROM test_runs "
        "GROUP BY project_id, name, round HAVING count(*) > 1"
    )).all()
    if dup:
        raise RuntimeError(f"같은 회차가 둘 이상인 수행이 있다. 먼저 정리한다: {dup}")
    op.create_index("uq_test_runs_project_name_round", "test_runs",
                    ["project_id", "name", "round"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_test_runs_project_name_round", table_name="test_runs")
```

`tests_unit/test_baseline_schema.py` 의 `test_리비전은_하나다` 를 `test_리비전_파일` 로 바꿔 기대 목록에 `0002_unique_run_round.py` 를 더한다.

- [ ] **Step 3: 통과 확인과 커밋**

Run: `python -m pytest tests_unit/test_run_round_unique.py tests_unit/test_baseline_schema.py tests_unit/test_run_next_round.py -q`
Expected: PASS

```bash
git add backend/models.py backend/alembic/versions/0002_unique_run_round.py backend/tests_unit/test_run_round_unique.py backend/tests_unit/test_baseline_schema.py
git commit -m "fix: 같은 수행 이름의 회차 중복을 유니크 제약으로 차단 (SYM-6)"
```

---

### Task 3: 최초 관리자 판정을 잠금으로

**Files:**
- Modify: `backend/routes/auth.py:95-123` (`register`)
- Delete: `backend/services/first_admin.py`, `backend/tests_unit/test_first_admin.py`
- Test: `backend/tests_unit/test_first_admin_concurrent.py`

- [ ] **Step 1: 실패하는 테스트**

동시 가입을 실제 연결 여럿으로 재현한다. 서버 대신 라우트 함수를 독립 세션으로 직접 부른다.

```python
"""동시에 가입해도 관리자는 한 명이다."""
import threading

from sqlalchemy.orm import sessionmaker

from models import User, UserRole
from routes.auth import register
from schemas import UserCreate

N = 8


def test_빈_DB_에_동시에_가입해도_관리자는_한_명(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    barrier = threading.Barrier(N)
    errors = []

    def go(i):
        s = Session()
        try:
            barrier.wait()
            register(UserCreate(username=f"user{i}", password="Passw0rd!", display_name=f"u{i}"), db=s)
        except Exception as e:
            errors.append(repr(e))
        finally:
            s.close()

    threads = [threading.Thread(target=go, args=(i,)) for i in range(N)]
    for t in threads: t.start()
    for t in threads: t.join()

    s = Session()
    roles = [u.role for u in s.query(User).all()]
    s.close()
    assert errors == []
    assert len(roles) == N
    assert roles.count(UserRole.admin) == 1, roles
```

`UserCreate` 의 비밀번호 규칙이 다르면 `schemas.py` 의 검증을 통과하는 값으로 바꾼다.

Run: `python -m pytest tests_unit/test_first_admin_concurrent.py -q`
Expected: 지금 코드(삽입 후 강등)는 READ COMMITTED 에서 서로의 미커밋 행을 못 봐 관리자가 둘 이상 남을 수 있다. FAIL 이 나오면 Step 2 로. 통과하면 N 을 32 로 올려 다시 보고, 그래도 통과하면 원장에 기록하고 Step 3 의 잠금 제거 확인으로 대신한다.

- [ ] **Step 2: 구현**

`register` 의 `user_count = db.query(User).count()` 앞에 잠금을 넣고 강등 로직을 지운다.

```python
    # ★가입을 전역 잠금으로 줄 세운다. 잠금은 커밋까지 유지되므로 다음 가입은 앞선
    #   가입이 커밋된 뒤에 count 를 본다. 삽입 뒤 강등하던 방식은 SQLite 의 쓰기 잠금에
    #   기대고 있어서 PostgreSQL 에서는 서로의 미커밋 행을 못 봤다.
    advisory_xact_lock(db, LockNs.FIRST_ADMIN)
    user_count = db.query(User).count()
```

`existing` 아이디 중복 확인도 잠금 뒤로 옮긴다. `demote_if_not_first` 임포트와 호출, `services/first_admin.py`, `tests_unit/test_first_admin.py` 를 지운다.

- [ ] **Step 3: 통과 확인, 이빨 확인, 커밋**

Run: `python -m pytest tests_unit/test_first_admin_concurrent.py test_security.py -q`
Expected: PASS

잠금 줄을 주석 처리하고 다시 돌려 FAIL 을 확인한 뒤 원복한다.

```bash
git add -A backend/routes/auth.py backend/services/first_admin.py backend/tests_unit/test_first_admin.py backend/tests_unit/test_first_admin_concurrent.py
git commit -m "fix: 최초 관리자 판정을 advisory lock 으로 (SYM-6)"
```

---

### Task 4: 결과 수정 충돌 검사를 행 잠금으로

**Files:**
- Modify: `backend/routes/testruns.py:386-391` (`existing_results` 조회)
- Test: `backend/tests_unit/test_result_conflict_concurrent.py`

- [ ] **Step 1: 실패하는 테스트**

`tests_unit/test_result_conflict.py` 의 env 픽스처와 같은 방식으로 앱을 띄워(`app.dependency_overrides[get_db]`), 같은 결과 행을 같은 `expected_executed_at` 으로 두 스레드가 동시에 저장한다. 하나는 200, 하나는 409 여야 한다. 그 파일의 픽스처와 헬퍼를 먼저 읽고 그대로 가져다 쓴다.

```python
def test_같은_행을_같은_기준으로_동시에_저장하면_하나만_성공(env):
    # env 는 test_result_conflict.py 와 같은 픽스처(서버, 런, 결과 행 1개, 토큰)
    ...
    barrier = threading.Barrier(2)
    def save(val):
        barrier.wait()
        return requests.put(url, headers=h, json={"results": [{
            "test_case_id": tc_id, "result": val,
            "expected_executed_at": seen_executed_at,
        }]})
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(r.status_code for r in pool.map(save, ["PASS", "FAIL"]))
    assert codes == [200, 409]
```

`...` 자리는 `test_result_conflict.py` 의 픽스처가 돌려주는 값(URL, 헤더, TC id, 읽어 둔 executed_at)을 꺼내는 코드로 채운다. 그 파일의 실제 이름을 쓴다.

Run: `python -m pytest tests_unit/test_result_conflict_concurrent.py -q`
Expected: FAIL, `[200, 200]`

- [ ] **Step 2: 구현**

```python
    # ★행을 잠그고 읽는다. 잠그지 않으면 두 요청이 같은 executed_at 을 보고 둘 다
    #   충돌 검사를 통과한다. 잠금을 기다린 쪽은 앞선 커밋 뒤의 값을 다시 읽으므로
    #   검사에서 걸린다. 교착을 피하려고 id 순서로 잠근다.
    existing_results = db.query(TestResult).filter(
        TestResult.test_run_id == run_id,
        TestResult.test_case_id.in_(tc_ids),
    ).order_by(TestResult.id).with_for_update().all()
```

- [ ] **Step 3: 통과 확인, 이빨 확인, 커밋**

Run: `python -m pytest tests_unit/test_result_conflict_concurrent.py tests_unit/test_result_conflict.py -q`
Expected: PASS. `.with_for_update()` 를 빼고 FAIL 확인 후 원복.

```bash
git add backend/routes/testruns.py backend/tests_unit/test_result_conflict_concurrent.py
git commit -m "fix: 결과 동시 수정 충돌 검사를 행 잠금으로 (SYM-6)"
```

---

### Task 5: 1회용 코드 소비를 행 잠금으로

**Files:**
- Modify: `backend/routes/account_requests.py:253-263`
- Test: `backend/test_account_requests.py` (동시 소비 테스트 추가)

- [ ] **Step 1: 실패하는 테스트**

`test_account_requests.py` 에 이미 있는 "승인 후 코드로 재설정" 흐름 헬퍼를 쓴다. 같은 코드로 서로 다른 새 비밀번호를 두 스레드가 동시에 보낸다.

```python
def test_같은_코드를_동시에_두_번_쓰면_하나만_성공한다(...):
    # 이 파일의 승인·코드 발급 헬퍼로 code 를 얻는다
    barrier = threading.Barrier(2)
    def use(pw):
        barrier.wait()
        return requests.post(f"{BASE}/api/auth/reset-password/verify",
                             json={"username": uname, "code": code, "new_password": pw})
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(r.status_code for r in pool.map(use, ["NewPassA1!", "NewPassB1!"]))
    assert codes[0] == 200 and codes[1] != 200
```

인자와 헬퍼 이름은 그 파일의 기존 재설정 테스트에서 가져온다.

Run: `python -m pytest test_account_requests.py -q -k 동시`
Expected: FAIL, 둘 다 200

- [ ] **Step 2: 구현**

```python
    # ★행을 잠그고 고른다. 잠그지 않으면 같은 코드로 두 요청이 동시에 통과해 서로 다른
    #   비밀번호를 쓴다. 기다린 쪽은 앞선 커밋으로 status 가 바뀐 행을 다시 평가해 빠진다.
    approved = (
        db.query(AccountRequest)
        .filter(...)  # 기존 조건 그대로
        .order_by(AccountRequest.resolved_at.desc().nulls_last(), AccountRequest.id.desc())
        .with_for_update()
        .all()
    )
```

`nulls_last()` 는 SQLite 와 PostgreSQL 의 NULL 정렬 차이 때문에 넣는다(스펙 시간 절). 승인된 행은 `resolved_at` 이 있지만 명시한다.

- [ ] **Step 3: 통과 확인, 이빨 확인, 커밋**

Run: `python -m pytest test_account_requests.py -q`
Expected: PASS. `.with_for_update()` 를 빼고 FAIL 확인 후 원복.

```bash
git add backend/routes/account_requests.py backend/test_account_requests.py
git commit -m "fix: 1회용 코드 이중 사용을 행 잠금으로 차단 (SYM-6)"
```

---

### Task 6: 로그인 잠금과 접수 제한을 DB 로, 클라이언트 IP 판정

**Files:**
- Create: `backend/services/rate_limit.py`, `backend/services/client_ip.py`
- Create: `backend/alembic/versions/0003_rate_limit_events.py`
- Modify: `backend/models.py` (`RateLimitEvent`)
- Modify: `backend/routes/auth.py:27-90`, `backend/routes/account_requests.py:40-80`
- Modify: `backend/test_account_requests.py:21-30, 500-520`, `backend/tests_unit/test_api_keys.py:98`, `backend/tests_unit/test_baseline_schema.py`
- Test: `backend/tests_unit/test_rate_limit.py`, `backend/tests_unit/test_client_ip.py`

**Interfaces:**
- Produces:
  - `rate_limit.count_recent(bucket: str, key: str, window_sec: int, engine=None) -> int`
  - `rate_limit.record(bucket: str, key: str, engine=None) -> None`
  - `rate_limit.clear(bucket: str, key: str, engine=None) -> None`
  - `rate_limit.clear_all(engine=None) -> None` (테스트용)
  - `rate_limit.purge_older_than(seconds: int, engine=None) -> int` (Cron 이 부름, 계획 2b)
  - `client_ip.client_ip(request) -> str`
  - 환경변수 `TRUSTED_PROXY_HEADER` (예 `x-real-ip`. 비우면 `request.client.host`)

- [ ] **Step 1: 실패하는 테스트**

`tests_unit/test_rate_limit.py`:

```python
"""실패 횟수는 DB 에 쌓여 여러 실행 환경이 같은 값을 본다."""
from services import rate_limit


def test_기록하면_다른_엔진에서도_보인다(pg_engine):
    from sqlalchemy import create_engine
    other = create_engine(pg_engine.url, connect_args={"options": f"-csearch_path={pg_engine._ymtc_schema}"})
    rate_limit.record("login", "1.2.3.4:u", engine=pg_engine)
    rate_limit.record("login", "1.2.3.4:u", engine=pg_engine)
    assert rate_limit.count_recent("login", "1.2.3.4:u", 300, engine=other) == 2
    other.dispose()


def test_창_밖의_기록은_세지_않는다(pg_engine):
    from sqlalchemy import text
    rate_limit.record("login", "k", engine=pg_engine)
    with pg_engine.begin() as c:
        c.execute(text("UPDATE rate_limit_events SET created_at = now() - interval '10 minutes'"))
    assert rate_limit.count_recent("login", "k", 300, engine=pg_engine) == 0


def test_clear_는_그_키만_지운다(pg_engine):
    rate_limit.record("login", "a", engine=pg_engine)
    rate_limit.record("login", "b", engine=pg_engine)
    rate_limit.clear("login", "a", engine=pg_engine)
    assert rate_limit.count_recent("login", "a", 300, engine=pg_engine) == 0
    assert rate_limit.count_recent("login", "b", 300, engine=pg_engine) == 1


def test_오래된_행을_지운다(pg_engine):
    from sqlalchemy import text
    rate_limit.record("submit", "x", engine=pg_engine)
    with pg_engine.begin() as c:
        c.execute(text("UPDATE rate_limit_events SET created_at = now() - interval '2 hours'"))
    rate_limit.record("submit", "y", engine=pg_engine)
    assert rate_limit.purge_older_than(3600, engine=pg_engine) == 1
```

`tests_unit/test_client_ip.py`:

```python
from starlette.requests import Request

from services.client_ip import client_ip


def _req(headers=None, host="10.0.0.1"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (host, 1234)})


def test_설정이_없으면_소켓_주소(monkeypatch):
    monkeypatch.delenv("TRUSTED_PROXY_HEADER", raising=False)
    assert client_ip(_req({"x-forwarded-for": "6.6.6.6"})) == "10.0.0.1"


def test_신뢰_헤더가_있으면_그_값의_첫_항목(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", "x-real-ip")
    assert client_ip(_req({"x-real-ip": "1.2.3.4, 5.6.7.8"})) == "1.2.3.4"


def test_신뢰_헤더가_비어_있으면_소켓_주소(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_HEADER", "x-real-ip")
    assert client_ip(_req()) == "10.0.0.1"
```

Run: `python -m pytest tests_unit/test_rate_limit.py tests_unit/test_client_ip.py -q`
Expected: FAIL, 모듈 없음

- [ ] **Step 2: 모델, 마이그레이션, 서비스**

`models.py` 끝에:

```python
class RateLimitEvent(Base):
    """로그인 실패, 계정 요청 접수 같은 횟수 제한의 기록. 시각은 DB 시계를 쓴다."""
    __tablename__ = "rate_limit_events"

    id = Column(Integer, primary_key=True)
    bucket = Column(String(32), nullable=False)
    key = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_rate_limit_events_bucket_key_created", "bucket", "key", "created_at"),
    )
```

`models.py` 상단에 `func` 임포트가 없으면 `from sqlalchemy import func` 를 더한다.

`0003_rate_limit_events.py` 는 위 테이블과 인덱스를 `op.create_table` / `op.create_index` 로 만들고 `down_revision = "0002_unique_run_round"` 로 둔다. `test_baseline_schema.py` 의 리비전 파일 기대 목록에 더한다.

`services/rate_limit.py`:

```python
"""횟수 제한 기록. 요청 세션과 따로 자체 트랜잭션으로 쓴다.

★요청 세션으로 쓰면 그 요청이 예외(401, 429)로 끝날 때 기록도 같이 롤백된다.
  실패를 세는 것이 목적이라 실패 응답과 함께 사라지면 안 된다.
★시각은 DB 의 now() 를 쓴다. 실행 환경마다 시계가 조금씩 달라도 같은 기준으로 센다.
"""
from sqlalchemy import text


def _engine(engine):
    if engine is not None:
        return engine
    from database import engine as default
    return default


def count_recent(bucket: str, key: str, window_sec: int, engine=None) -> int:
    with _engine(engine).connect() as c:
        return c.execute(text(
            "SELECT count(*) FROM rate_limit_events WHERE bucket = :b AND key = :k "
            "AND created_at > now() - make_interval(secs => :w)"
        ), {"b": bucket, "k": key, "w": window_sec}).scalar()


def record(bucket: str, key: str, engine=None) -> None:
    with _engine(engine).begin() as c:
        c.execute(text("INSERT INTO rate_limit_events (bucket, key) VALUES (:b, :k)"),
                  {"b": bucket, "k": key})


def clear(bucket: str, key: str, engine=None) -> None:
    with _engine(engine).begin() as c:
        c.execute(text("DELETE FROM rate_limit_events WHERE bucket = :b AND key = :k"),
                  {"b": bucket, "k": key})


def clear_all(engine=None) -> None:
    with _engine(engine).begin() as c:
        c.execute(text("DELETE FROM rate_limit_events"))


def purge_older_than(seconds: int, engine=None) -> int:
    with _engine(engine).begin() as c:
        return c.execute(text(
            "DELETE FROM rate_limit_events WHERE created_at < now() - make_interval(secs => :s)"
        ), {"s": seconds}).rowcount
```

`services/client_ip.py`:

```python
"""요청을 보낸 클라이언트의 IP.

★헤더를 아무거나 믿지 않는다. X-Forwarded-For 는 클라이언트가 마음대로 넣을 수 있다.
  배포 플랫폼이 덮어써서 위조할 수 없는 헤더 하나만 TRUSTED_PROXY_HEADER 로 지정한다.
  어떤 헤더가 그런지는 플랫폼마다 다르고, 스테이징에서 실측해 정한다(스펙 공유 상태 절).
"""
import os


def client_ip(request) -> str:
    header = os.getenv("TRUSTED_PROXY_HEADER", "").strip().lower()
    if header:
        value = request.headers.get(header, "")
        first = value.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"
```

- [ ] **Step 3: 두 제한기 교체**

`routes/auth.py` 의 `_login_failures`, `_purge_expired_keys`, `_MAX_RATE_LIMIT_KEYS`, `_last_purge_time` 를 지우고 세 함수를 바꾼다. 함수 이름과 인자는 그대로 둔다(`account_requests.py` 가 임포트한다).

```python
BUCKET_LOGIN = "login"


def _rate_limit_key(request: Request, username: str = "") -> str:
    """IP + username 조합 키"""
    ip = client_ip(request)
    return f"{ip}:{username}" if username else ip


def _check_rate_limit(request: Request, username: str = ""):
    """5분간 실패 10회 이상이면 차단"""
    key = _rate_limit_key(request, username)
    if rate_limit.count_recent(BUCKET_LOGIN, key, LOGIN_WINDOW_SEC) >= LOGIN_MAX_FAILURES:
        logger.warning("Rate limit exceeded: %s", key)
        raise HTTPException(status_code=429, detail="로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.")


def _record_failure(request: Request, username: str = ""):
    rate_limit.record(BUCKET_LOGIN, _rate_limit_key(request, username))


def _clear_failures(request: Request, username: str = ""):
    rate_limit.clear(BUCKET_LOGIN, _rate_limit_key(request, username))
```

`routes/account_requests.py` 의 `_submit_hits`, `_purge_submit_keys`, `_MAX_SUBMIT_KEYS`, `_last_submit_purge`, `_client_ip` 를 지우고:

```python
BUCKET_SUBMIT = "account_submit"


def _check_submit_limit(request: Request):
    """성공/실패 무관하게 접수 시도를 센다. 1시간 10회."""
    key = client_ip(request)
    if rate_limit.count_recent(BUCKET_SUBMIT, key, SUBMIT_WINDOW_SEC) >= SUBMIT_MAX_PER_WINDOW:
        logger.warning("Account request rate limit exceeded: %s", key)
        raise HTTPException(status_code=429, detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")
    rate_limit.record(BUCKET_SUBMIT, key)
```

- [ ] **Step 4: 테스트 픽스처 교체**

`test_account_requests.py` 의 `_reset_submit_limit` 픽스처 본문을 `from services import rate_limit; rate_limit.clear_all()` 로 바꾼다. 500-520 줄의 테스트(카운터에 직접 값을 넣어 한도를 흉내 내는 테스트)는 `_submit_hits` 대신 `rate_limit.record("account_submit", key)` 를 `SUBMIT_MAX_PER_WINDOW` 번 부르는 방식으로 바꾸고, 키는 `"127.0.0.1"` 로 둔다. `tests_unit/test_api_keys.py:98` 의 `auth_routes._login_failures.clear()` 는 `rate_limit.clear_all(engine=engine)` 로 바꾼다.

서버 테스트 세션은 conftest 가 만든 세션 DB 를 쓰므로 `rate_limit.clear_all()` (기본 엔진)이 같은 DB 를 지운다.

- [ ] **Step 5: 통과 확인과 커밋**

Run: `python -m pytest tests_unit/test_rate_limit.py tests_unit/test_client_ip.py test_account_requests.py tests_unit/test_api_keys.py test_security.py tests_unit/test_baseline_schema.py -q`
Expected: PASS

```bash
git add -A backend
git commit -m "fix: 로그인 잠금과 계정 요청 접수 제한을 DB 로, 신뢰 헤더 기반 IP (SYM-6)"
```

---

### Task 7: 리포트 시각을 KST 로 고정

**Files:**
- Modify: `backend/routes/reports.py:534`, `:770`
- Test: `backend/tests_unit/test_report_kst.py`

- [ ] **Step 1: 실패하는 테스트**

```python
"""리포트 파일명 날짜와 생성 시각은 서버 시간대와 무관하게 KST 다. Vercel 은 UTC 다."""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CODE = (
    "import datetime, routes.reports as r;"
    "from zoneinfo import ZoneInfo;"
    "t = datetime.datetime(2026, 10, 8, 16, 30, tzinfo=datetime.timezone.utc);"
    "print(r.report_now(t).strftime('%Y%m%d %H'))"
)


def test_UTC_서버에서도_KST_날짜():
    env = dict(os.environ, TZ="UTC", DATABASE_URL="postgresql+psycopg2://u:p@127.0.0.1:1/x")
    r = subprocess.run([sys.executable, "-c", CODE], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "20261009 01"
```

Run: `python -m pytest tests_unit/test_report_kst.py -q`
Expected: FAIL, `report_now` 없음

- [ ] **Step 2: 구현**

`routes/reports.py` 에 함수를 두고 두 자리의 `datetime.now()` 를 `report_now()` 로 바꾼다.

```python
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def report_now(now=None):
    """리포트에 찍는 현재 시각. 서버 시간대(Vercel 은 UTC)와 무관하게 KST 다."""
    base = now or datetime.now(tz=KST)
    return base.astimezone(KST).replace(tzinfo=None)
```

`:534` 의 `(when or datetime.now()).strftime("%Y%m%d")` 는 `(when or report_now()).strftime("%Y%m%d")` 로, `:770` 의 `datetime.now()` 는 `report_now()` 로 바꾼다. 줄 번호는 앞 Task 들로 밀렸을 수 있으니 `grep -n "datetime.now()" routes/reports.py` 로 찾는다.

- [ ] **Step 3: 통과 확인과 커밋**

Run: `python -m pytest tests_unit/test_report_kst.py tests_unit/test_report_content.py test_report_contract.py -q`
Expected: PASS

```bash
git add backend/routes/reports.py backend/tests_unit/test_report_kst.py
git commit -m "fix: 리포트 날짜와 생성 시각을 서버 시간대와 무관하게 KST 로 (SYM-6)"
```

---

## 계획 2a 완료 조건

- 전체 pytest 실패 0
- 동시성 테스트 다섯(복제, 일괄 복제, 최초 관리자, 결과 수정, 1회용 코드)이 잠금을 빼면 실패하고 넣으면 통과
- `grep -rn "_login_failures\|_submit_hits" backend` 결과 0
- QA 2인 검증 통과 후 계획 2b
