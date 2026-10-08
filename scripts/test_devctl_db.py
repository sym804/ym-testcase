"""devctl up 은 로컬 PostgreSQL 을 먼저 띄운다. 못 띄우면 무엇을 켜야 하는지 알리고 멈춘다."""
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import devctl


def test_docker_가_없으면_안내하고_멈춘다(monkeypatch, capsys):
    def boom(*a, **k):
        raise FileNotFoundError("docker")
    monkeypatch.setattr(devctl.subprocess, "run", boom)
    with pytest.raises(SystemExit) as e:
        devctl.ensure_database()
    assert e.value.code == 2
    assert "Docker" in capsys.readouterr().err


def test_데몬이_꺼져_있으면_안내하고_멈춘다(monkeypatch, capsys):
    monkeypatch.setattr(devctl.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "Cannot connect to the Docker daemon"))
    with pytest.raises(SystemExit) as e:
        devctl.ensure_database()
    assert e.value.code == 2
    assert "Docker Desktop" in capsys.readouterr().err


def test_up_은_백엔드보다_DB_를_먼저_띄운다(monkeypatch):
    calls = []
    monkeypatch.setattr(devctl, "ensure_database", lambda: calls.append("db"))
    monkeypatch.setattr(devctl, "start_backend", lambda: calls.append("backend"))
    monkeypatch.setattr(devctl, "start_frontend", lambda: calls.append("frontend"))

    class A:
        backend = True
        frontend = False
    devctl.cmd_up(A())
    assert calls == ["db", "backend"]
