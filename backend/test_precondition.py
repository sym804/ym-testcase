# -*- coding: utf-8 -*-
"""사전조건 참조 해석기 테스트. 실제 Starfort 시트 문구를 그대로 썼다."""

from services.precondition_service import (
    split_items, parse_ref, has_ref, resolve_items, expand_text,
)

REC_API_01 = "\n".join([
    "1. Company / Organization / Project(Type=API) 각 1개가 생성돼 있다.",
    "2. Project Guardian 1개가 등록돼 있다 (활성 Input Type=text, 지원 process_type 1개 이상).",
    "3. Active 상태의 API Key 1개가 발급돼 있다.",
    "4. Opticon Project Binding 구성 완료, Kill Switch 전 tier 해제.",
    "5. 플랫폼 수신 상한값을 확인해 둔다. (제품확인: 실제 값)",
])
FS_01 = "\n".join([
    "1. REC-API-01 의 사전조건 1~4 참조",
    "2. Bastion 과 Opticon 사이에 장애 주입 프록시가 연결돼 있다 (hang / 부분실패 200 / 파싱불가 / 응답drop 전환 가능).",
    "3. Opticon Fail-Safe 를 설정하지 않은(default) Project 를 준비한다.",
])
FS_02 = "1. FS-01 의 사전조건 1~5 참조\n2. Opticon Fail-Safe = Fail-Closed 로 설정한다."
FS_04 = "FS-02 의 사전조건 참조"

INDEX = {"REC-API-01": REC_API_01, "FS-01": FS_01, "FS-02": FS_02, "FS-04": FS_04}


def test_split_items_번호_단위로_쪼갠다():
    assert split_items(FS_02) == [
        "FS-01 의 사전조건 1~5 참조",
        "Opticon Fail-Safe = Fail-Closed 로 설정한다.",
    ]


def test_split_items_번호_없는_한줄은_항목_하나():
    assert split_items(FS_04) == ["FS-02 의 사전조건 참조"]


def test_split_items_이어지는_줄은_앞_항목에_붙는다():
    raw = "1. dog-fooding 계정으로 로그인해\n   accessToken 을 확보한다.\n2. 대상 id 를 확보한다."
    assert split_items(raw) == [
        "dog-fooding 계정으로 로그인해\n   accessToken 을 확보한다.",
        "대상 id 를 확보한다.",
    ]


def test_split_items_빈값():
    assert split_items("") == []
    assert split_items(None) == []


def test_parse_ref():
    assert parse_ref("REC-API-01 의 사전조건 1~4 참조") == ("REC-API-01", 4)
    assert parse_ref("TRD-01 의 사전조건 참조") == ("TRD-01", None)
    assert parse_ref("Active 상태의 API Key 1개가 발급돼 있다.") is None


def test_has_ref():
    assert has_ref(FS_02) is True
    assert has_ref(REC_API_01) is False


def test_범위_참조는_앞_N개만_가져온다():
    items = resolve_items("FS-01", INDEX)
    assert len(items) == 6
    assert items[3] == "Opticon Project Binding 구성 완료, Kill Switch 전 tier 해제."
    # 5번(플랫폼 수신 상한)은 1~4 범위 밖이라 들어오면 안 된다
    assert not any("플랫폼 수신 상한값" in i for i in items)


def test_3단_체인을_끝까지_펼친다():
    assert resolve_items("FS-04", INDEX) == [
        "Company / Organization / Project(Type=API) 각 1개가 생성돼 있다.",
        "Project Guardian 1개가 등록돼 있다 (활성 Input Type=text, 지원 process_type 1개 이상).",
        "Active 상태의 API Key 1개가 발급돼 있다.",
        "Opticon Project Binding 구성 완료, Kill Switch 전 tier 해제.",
        "Bastion 과 Opticon 사이에 장애 주입 프록시가 연결돼 있다 (hang / 부분실패 200 / 파싱불가 / 응답drop 전환 가능).",
        "Opticon Fail-Safe = Fail-Closed 로 설정한다.",
    ]


def test_없는_대상():
    assert "찾을 수 없음" in resolve_items("없는TC", INDEX)[0]


def test_순환_참조에서_멈춘다():
    loop = {"A-1": "B-1 의 사전조건 참조", "B-1": "A-1 의 사전조건 참조"}
    assert "순환 참조" in resolve_items("A-1", loop)[0]


def test_expand_text_는_번호를_다시_매긴다():
    out = expand_text("FS-04", INDEX)
    assert out.startswith("1. Company / Organization")
    assert out.endswith("6. Opticon Fail-Safe = Fail-Closed 로 설정한다.")


def test_참조가_없는_앵커는_원문_그대로():
    assert expand_text("REC-API-01", INDEX) == REC_API_01
