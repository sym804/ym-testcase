# -*- coding: utf-8 -*-
"""사전조건 참조 해석기 테스트. 문구는 가상의 쇼핑몰 TC 다(실제 시트 문구는 공개 레포에 넣지 않는다, SYM-207)."""

from services.precondition_service import (
    split_items, parse_ref, has_ref, resolve_items, expand_text,
)

REC_API_01 = "\n".join([
    "1. Store / Seller / Catalog(Type=API) 각 1개가 생성돼 있다.",
    "2. Catalog Checker 1개가 등록돼 있다 (활성 Item Type=text, 지원 pay_type 1개 이상).",
    "3. Active 상태의 API Key 1개가 발급돼 있다.",
    "4. Gateway Catalog Binding 구성 완료, Sale Lock 전 tier 해제.",
    "5. 주문 수신 상한값을 확인해 둔다. (제품확인: 실제 값)",
])
FS_01 = "\n".join([
    "1. ORD-API-01 의 사전조건 1~4 참조",
    "2. Frontdoor 와 Gateway 사이에 지연 주입 도구가 연결돼 있다 (지연 3초 / 오류 500 / 빈 응답 중 고를 수 있다).",
    "3. Gateway Retry 를 설정하지 않은(default) Catalog 를 준비한다.",
])
FS_02 = "1. PAY-01 의 사전조건 1~5 참조\n2. Gateway Retry = Off 로 설정한다."
FS_04 = "PAY-02 의 사전조건 참조"

INDEX = {"ORD-API-01": REC_API_01, "PAY-01": FS_01, "PAY-02": FS_02, "PAY-04": FS_04}


def test_split_items_번호_단위로_쪼갠다():
    assert split_items(FS_02) == [
        "PAY-01 의 사전조건 1~5 참조",
        "Gateway Retry = Off 로 설정한다.",
    ]


def test_split_items_번호_없는_한줄은_항목_하나():
    assert split_items(FS_04) == ["PAY-02 의 사전조건 참조"]


def test_split_items_이어지는_줄은_앞_항목에_붙는다():
    raw = "1. 테스트 계정으로 로그인해\n   accessToken 을 확보한다.\n2. 대상 id 를 확보한다."
    assert split_items(raw) == [
        "테스트 계정으로 로그인해\n   accessToken 을 확보한다.",
        "대상 id 를 확보한다.",
    ]


def test_split_items_빈값():
    assert split_items("") == []
    assert split_items(None) == []


def test_parse_ref():
    assert parse_ref("ORD-API-01 의 사전조건 1~4 참조") == ("ORD-API-01", 4)
    assert parse_ref("TRD-01 의 사전조건 참조") == ("TRD-01", None)
    assert parse_ref("Active 상태의 API Key 1개가 발급돼 있다.") is None


def test_has_ref():
    assert has_ref(FS_02) is True
    assert has_ref(REC_API_01) is False


def test_범위_참조는_앞_N개만_가져온다():
    items = resolve_items("PAY-01", INDEX)
    assert len(items) == 6
    assert items[3] == "Gateway Catalog Binding 구성 완료, Sale Lock 전 tier 해제."
    # 5번(주문 수신 상한)은 1~4 범위 밖이라 들어오면 안 된다
    assert not any("주문 수신 상한값" in i for i in items)


def test_3단_체인을_끝까지_펼친다():
    assert resolve_items("PAY-04", INDEX) == [
        "Store / Seller / Catalog(Type=API) 각 1개가 생성돼 있다.",
        "Catalog Checker 1개가 등록돼 있다 (활성 Item Type=text, 지원 pay_type 1개 이상).",
        "Active 상태의 API Key 1개가 발급돼 있다.",
        "Gateway Catalog Binding 구성 완료, Sale Lock 전 tier 해제.",
        "Frontdoor 와 Gateway 사이에 지연 주입 도구가 연결돼 있다 (지연 3초 / 오류 500 / 빈 응답 중 고를 수 있다).",
        "Gateway Retry = Off 로 설정한다.",
    ]


def test_없는_대상():
    assert "찾을 수 없음" in resolve_items("없는TC", INDEX)[0]


def test_순환_참조에서_멈춘다():
    loop = {"A-1": "B-1 의 사전조건 참조", "B-1": "A-1 의 사전조건 참조"}
    assert "순환 참조" in resolve_items("A-1", loop)[0]


def test_expand_text_는_번호를_다시_매긴다():
    out = expand_text("PAY-04", INDEX)
    assert out.startswith("1. Store / Seller")
    assert out.endswith("6. Gateway Retry = Off 로 설정한다.")


def test_참조가_없는_앵커는_원문_그대로():
    assert expand_text("ORD-API-01", INDEX) == REC_API_01
