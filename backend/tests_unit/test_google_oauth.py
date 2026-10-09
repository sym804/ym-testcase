"""Google 흐름 도구: PKCE, 인가 URL, 서명 쿠키, 토큰 교환과 검증."""
import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest

from services import google_oauth as g
from services.auth_config import load_auth_config

CFG = load_auth_config({"GOOGLE_CLIENT_ID": "cid", "GOOGLE_CLIENT_SECRET": "sec",
                        "GOOGLE_REDIRECT_URI": "http://localhost:5173/api/auth/google/callback"})


def test_인가_URL_에_state_nonce_S256_이_실린다():
    flow = g.new_flow("login", "/projects")
    q = parse_qs(urlsplit(g.authorize_url(CFG, flow)).query)
    expected = base64.urlsafe_b64encode(hashlib.sha256(flow.verifier.encode()).digest()).rstrip(b"=").decode()
    assert q["state"] == [flow.state] and q["nonce"] == [flow.nonce]
    assert q["code_challenge"] == [expected] and q["code_challenge_method"] == ["S256"]
    assert q["scope"] == ["openid email profile"] and q["redirect_uri"] == [CFG.google_redirect_uri]


def test_서명_쿠키는_왕복되고_로그인_JWT_와_섞이지_않는다():
    flow = g.new_flow("link", "/projects", uid=7)
    back = g.decode_flow(g.encode_flow(flow))
    assert back == flow
    from auth import create_access_token
    with pytest.raises(g.FlowError):
        g.decode_flow(create_access_token({"sub": "1", "ver": 0}))
    with pytest.raises(g.FlowError):
        g.decode_flow("garbage")


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_교환과_검증(monkeypatch):
    seen = {}

    def fake_post(url, data, timeout):
        seen.update(url=url, data=data, timeout=timeout)
        return _Resp(200, {"id_token": "IDT"})

    def fake_verify(token, request, audience, clock_skew_in_seconds):
        seen.update(token=token, audience=audience, skew=clock_skew_in_seconds)
        return {"sub": "123", "email": "A@Corp.com", "email_verified": True, "hd": "corp.com", "name": "A", "nonce": "N"}

    monkeypatch.setattr(g.requests, "post", fake_post)
    import google.oauth2.id_token as idt
    monkeypatch.setattr(idt, "verify_oauth2_token", fake_verify)
    ident = g.exchange_and_verify(CFG, "CODE", "VERIFIER", "N")
    assert ident == g.GoogleIdentity(sub="123", email="a@corp.com", email_verified=True, hd="corp.com", name="A")
    assert seen["data"]["code_verifier"] == "VERIFIER" and seen["timeout"] == g.HTTP_TIMEOUT_SEC
    assert seen["audience"] == "cid" and seen["skew"] == g.CLOCK_SKEW_SEC
    with pytest.raises(g.GoogleAuthError):
        g.exchange_and_verify(CFG, "CODE", "VERIFIER", "OTHER-NONCE")


def test_토큰_주소가_실패하면_GoogleAuthError(monkeypatch):
    monkeypatch.setattr(g.requests, "post", lambda url, data, timeout: _Resp(400, {}))
    with pytest.raises(g.GoogleAuthError):
        g.exchange_and_verify(CFG, "CODE", "V", "N")
