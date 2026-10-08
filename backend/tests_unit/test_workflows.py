"""배포·백업 워크플로. 공개 레포에서는 돌지 않고(DEPLOY_ENABLED), 순서가 강제된다."""
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _wf(name):
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _steps(job):
    return [s.get("name", "") for s in job["steps"]]


def test_배포는_켠_레포에서만_한_번에_하나씩():
    wf = _wf("deploy.yml")
    (job,) = wf["jobs"].values()
    assert job["if"] == "vars.DEPLOY_ENABLED == 'true'"
    assert wf["concurrency"]["cancel-in-progress"] is False


def test_배포_순서는_테스트_마이그레이션_배포():
    (job,) = _wf("deploy.yml")["jobs"].values()
    names = _steps(job)
    i_test = names.index("백엔드 테스트")
    i_mig = names.index("운영 DB 마이그레이션")
    i_dep = names.index("Vercel 배포")
    assert i_test < i_mig < i_dep


def test_마이그레이션은_직결_주소로():
    (job,) = _wf("deploy.yml")["jobs"].values()
    mig = next(s for s in job["steps"] if s.get("name") == "운영 DB 마이그레이션")
    assert "secrets.DATABASE_URL_DIRECT" in mig["env"]["DATABASE_URL_DIRECT"]
    assert "alembic upgrade head" in mig["run"]


def test_백업은_켠_레포에서만_매일():
    wf = _wf("backup.yml")
    on = wf.get("on", wf.get(True))
    assert "schedule" in on
    (job,) = wf["jobs"].values()
    assert job["if"] == "vars.DEPLOY_ENABLED == 'true'"
    names = _steps(job)
    assert "DB 덤프" in names and "Storage 객체 백업" in names
