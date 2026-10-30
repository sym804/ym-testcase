import { describe, it, expect, afterEach } from "vitest";
import i18n from "../i18n";
import { splitItems, parseRef, hasRef, resolveItems, resolveRef } from "../utils/precondition";

// 가상의 쇼핑몰 사전조건 문구(실제 시트 문구는 공개 레포에 넣지 않는다, SYM-207)
const REC_API_01 = [
  "1. Store / Seller / Catalog(Type=API) 각 1개가 생성돼 있다.",
  "2. Catalog Checker 1개가 등록돼 있다 (활성 Item Type=text, 지원 pay_type 1개 이상).",
  "3. Active 상태의 API Key 1개가 발급돼 있다.",
  "4. Gateway Catalog Binding 구성 완료, Sale Lock 전 tier 해제.",
  "5. 주문 수신 상한값을 확인해 둔다. (제품확인: 실제 값)",
].join("\n");

const FS_01 = [
  "1. ORD-API-01 의 사전조건 1~4 참조",
  "2. Frontdoor 와 Gateway 사이에 지연 주입 도구가 연결돼 있다 (지연 3초 / 오류 500 / 빈 응답 중 고를 수 있다).",
  "3. Gateway Retry 를 설정하지 않은(default) Catalog 를 준비한다.",
].join("\n");

const FS_02 = ["1. PAY-01 의 사전조건 1~5 참조", "2. Gateway Retry = Off 로 설정한다."].join("\n");
const FS_04 = "PAY-02 의 사전조건 참조";
const MSK_01 = [
  "1. Checker 엔진을 Frontdoor 경유 없이 직접 호출할 수 있는 환경이 준비돼 있다.",
  "2. api.md §1 형식의 Checker 요청을 만들 수 있다.",
  "3. min_amount / max_amount 를 넓게, min_qty 를 1 이상으로 둔 COUPON 규칙을 준비한다.",
].join("\n");
const MSK_02 = "CPN-01 의 사전조건 1~2 참조";

const index = new Map<string, string>([
  ["ORD-API-01", REC_API_01],
  ["PAY-01", FS_01],
  ["PAY-02", FS_02],
  ["PAY-04", FS_04],
  ["CPN-01", MSK_01],
  ["CPN-02", MSK_02],
]);

describe("splitItems", () => {
  it("번호 항목 단위로 쪼갠다", () => {
    expect(splitItems(FS_02)).toEqual([
      "PAY-01 의 사전조건 1~5 참조",
      "Gateway Retry = Off 로 설정한다.",
    ]);
  });

  it("번호 없는 한 줄은 항목 1개로 본다", () => {
    expect(splitItems(FS_04)).toEqual(["PAY-02 의 사전조건 참조"]);
  });

  it("번호로 시작하지 않는 줄은 앞 항목에 이어 붙인다", () => {
    const raw = "1. 테스트 계정으로 로그인해\n   accessToken 을 확보한다.\n2. 대상 id 를 확보한다.";
    expect(splitItems(raw)).toEqual([
      "테스트 계정으로 로그인해\n   accessToken 을 확보한다.",
      "대상 id 를 확보한다.",
    ]);
  });

  it("빈 값은 빈 목록", () => {
    expect(splitItems("")).toEqual([]);
  });
});

describe("parseRef", () => {
  it("범위 있는 참조를 읽는다", () => {
    expect(parseRef("ORD-API-01 의 사전조건 1~4 참조")).toEqual({
      targetId: "ORD-API-01",
      upto: 4,
      text: "ORD-API-01 의 사전조건 1~4 참조",
    });
  });

  it("범위 없는 참조는 upto 가 undefined", () => {
    expect(parseRef("TRD-01 의 사전조건 참조")?.upto).toBeUndefined();
  });

  it("참조가 아닌 항목은 null", () => {
    expect(parseRef("Active 상태의 API Key 1개가 발급돼 있다.")).toBeNull();
  });

  it("hasRef 는 참조 포함 여부를 알려준다", () => {
    expect(hasRef(FS_02)).toBe(true);
    expect(hasRef(REC_API_01)).toBe(false);
  });
});

describe("resolveItems", () => {
  it("앵커는 그대로 돌려준다", () => {
    expect(resolveItems("ORD-API-01", index)).toHaveLength(5);
  });

  it("범위 참조는 앞 N개만 가져온다", () => {
    const items = resolveItems("PAY-01", index);
    expect(items).toHaveLength(6); // 베이스 4 + 지연 도구 + Retry default
    expect(items[3]).toBe("Gateway Catalog Binding 구성 완료, Sale Lock 전 tier 해제.");
    expect(items[4]).toContain("지연 주입 도구");
    // 5번(주문 수신 상한)은 1~4 범위 밖이라 들어오면 안 된다
    expect(items.some((i) => i.includes("주문 수신 상한값"))).toBe(false);
  });

  it("3단 체인(PAY-04 -> PAY-02 -> PAY-01 -> ORD-API-01)을 끝까지 펼친다", () => {
    const items = resolveItems("PAY-04", index);
    expect(items).toEqual([
      "Store / Seller / Catalog(Type=API) 각 1개가 생성돼 있다.",
      "Catalog Checker 1개가 등록돼 있다 (활성 Item Type=text, 지원 pay_type 1개 이상).",
      "Active 상태의 API Key 1개가 발급돼 있다.",
      "Gateway Catalog Binding 구성 완료, Sale Lock 전 tier 해제.",
      "Frontdoor 와 Gateway 사이에 지연 주입 도구가 연결돼 있다 (지연 3초 / 오류 500 / 빈 응답 중 고를 수 있다).",
      "Gateway Retry = Off 로 설정한다.",
    ]);
  });

  it("없는 대상은 안내 문구를 돌려준다", () => {
    expect(resolveItems("없는TC", index)[0]).toContain("찾을 수 없음");
  });

  it("순환 참조에서 무한 재귀하지 않는다", () => {
    const loop = new Map<string, string>([
      ["A-1", "B-1 의 사전조건 참조"],
      ["B-1", "A-1 의 사전조건 참조"],
    ]);
    expect(resolveItems("A-1", loop)[0]).toContain("순환 참조");
  });
});

describe("resolveRef", () => {
  it("범위 참조는 제목에 범위를 적고 항목을 잘라 준다", () => {
    const ref = parseRef("CPN-01 의 사전조건 1~2 참조")!;
    const { title, items } = resolveRef(ref, index);
    expect(title).toBe("CPN-01 사전조건 1~2");
    expect(items).toHaveLength(2);
    expect(items.some((i) => i.includes("COUPON 규칙"))).toBe(false);
  });

  it("범위 없는 참조는 대상 전체를 준다", () => {
    const { title, items } = resolveRef(parseRef("CPN-01 의 사전조건 참조")!, index);
    expect(title).toBe("CPN-01 사전조건");
    expect(items).toHaveLength(3);
  });
});

describe("화면에 나가는 문구", () => {
  afterEach(async () => {
    await i18n.changeLanguage("ko");
  });

  it("영어로 변경하면 참조 안내도 영어로 나온다", async () => {
    // ★이 문구들은 그리드 셀과 호버 팝업에 그대로 찍힌다. 한글로 고정돼 있으면
    //   영어 화면에서만 한글이 섞인다.
    await i18n.changeLanguage("en");

    const loop = new Map([["A-1", "1. A-1 의 사전조건 참조"]]);
    expect(resolveItems("A-1", loop)[0]).not.toContain("순환 참조");

    const missing = new Map<string, string>();
    expect(resolveItems("없음", missing)[0]).not.toContain("찾을 수 없음");

    const { title } = resolveRef(parseRef("CPN-01 의 사전조건 1~2 참조")!, index);
    expect(title).not.toContain("사전조건");
  });
});
