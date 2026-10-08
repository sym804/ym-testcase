"""배포·백업 워크플로. 공개 레포에서는 돌지 않고, 배포는 같은 커밋의 CI 성공 뒤에만 돈다."""
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _wf(name):
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _on(wf):
    return wf.get("on", wf.get(True))  # yaml 1.1 은 on 을 True 로 읽는다


def _steps(job):
    return [s.get("name", "") for s in job["steps"]]


def test_배포는_CI_가_끝난_뒤에만_시작한다():
    wf = _wf("deploy.yml")
    on = _on(wf)
    assert set(on) == {"workflow_run"}, "push 로 바로 돌면 CI(프론트·E2E) 결과를 기다리지 않는다"
    assert on["workflow_run"]["workflows"] == [_wf("ci.yml")["name"]]
    assert on["workflow_run"]["types"] == ["completed"]
    assert on["workflow_run"]["branches"] == ["main"]
    assert wf["concurrency"]["cancel-in-progress"] is False


def test_배포_조건은_켠_비공개_레포의_같은_레포_push_CI_성공():
    (job,) = _wf("deploy.yml")["jobs"].values()
    cond = job["if"]
    for part in ("vars.DEPLOY_ENABLED == 'true'",
                 "github.event.repository.private == true",
                 "github.event.workflow_run.conclusion == 'success'",
                 "github.event.workflow_run.event == 'push'",
                 "github.event.workflow_run.head_repository.full_name == github.repository"):
        assert part in cond, part
    assert " || " not in cond


def test_배포는_CI_가_검증한_커밋을_꺼낸다():
    (job,) = _wf("deploy.yml")["jobs"].values()
    checkout = next(s for s in job["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["ref"] == "${{ github.event.workflow_run.head_sha }}"


def test_배포_순서는_빌드_마이그레이션_배포():
    (job,) = _wf("deploy.yml")["jobs"].values()
    names = _steps(job)
    i_build = names.index("Vercel 빌드")
    i_mig = names.index("운영 DB 마이그레이션")
    i_dep = names.index("Vercel 배포")
    assert i_build < i_mig < i_dep, "빌드가 실패하면 DB 를 건드리기 전에 멈춰야 한다"
    dep = job["steps"][i_dep]["run"]
    assert "--prebuilt" in dep and "vercel build" not in dep


def test_마이그레이션은_직결_주소로():
    (job,) = _wf("deploy.yml")["jobs"].values()
    mig = next(s for s in job["steps"] if s.get("name") == "운영 DB 마이그레이션")
    assert "secrets.DATABASE_URL_DIRECT" in mig["env"]["DATABASE_URL_DIRECT"]
    assert "alembic upgrade head" in mig["run"]


def test_백업은_켠_비공개_레포에서만_매일():
    wf = _wf("backup.yml")
    assert "schedule" in _on(wf)
    (job,) = wf["jobs"].values()
    assert "vars.DEPLOY_ENABLED == 'true'" in job["if"]
    assert "github.event.repository.private == true" in job["if"]
    assert " || " not in job["if"]


def test_백업은_public_스키마만_덤프하고_Storage_가_실패해도_DB_덤프는_남긴다():
    (job,) = _wf("backup.yml")["jobs"].values()
    names = _steps(job)
    dump = job["steps"][names.index("DB 덤프")]["run"]
    assert "--schema=public" in dump
    i_db_art = names.index("DB 덤프 보관")
    assert names.index("DB 덤프") < i_db_art < names.index("Storage 객체 백업")
