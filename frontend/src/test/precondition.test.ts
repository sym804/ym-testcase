import { describe, it, expect } from "vitest";
import { splitItems, parseRef, hasRef, resolveItems, resolveRef } from "../utils/precondition";

// 실제 시트에서 가져온 사전조건 원문
const REC_API_01 = [
  "1. Company / Organization / Project(Type=API) 각 1개가 생성돼 있다.",
  "2. Project Guardian 1개가 등록돼 있다 (활성 Input Type=text, 지원 process_type 1개 이상).",
  "3. Active 상태의 API Key 1개가 발급돼 있다.",
  "4. Opticon Project Binding 구성 완료, Kill Switch 전 tier 해제.",
  "5. 플랫폼 수신 상한값을 확인해 둔다. (제품확인: 실제 값)",
].join("\n");

const FS_01 = [
  "1. REC-API-01 의 사전조건 1~4 참조",
  "2. Bastion 과 Opticon 사이에 장애 주입 프록시가 연결돼 있다 (hang / 부분실패 200 / 파싱불가 / 응답drop 전환 가능).",
  "3. Opticon Fail-Safe 를 설정하지 않은(default) Project 를 준비한다.",
].join("\n");

const FS_02 = ["1. FS-01 의 사전조건 1~5 참조", "2. Opticon Fail-Safe = Fail-Closed 로 설정한다."].join("\n");
const FS_04 = "FS-02 의 사전조건 참조";
const MSK_01 = [
  "1. Guardian 엔진을 Bastion 경유 없이 직접 호출할 수 있는 환경이 준비돼 있다.",
  "2. contracts.md §1 형식의 Guardian Input Format 요청을 만들 수 있다.",
  "3. keep_head / keep_tail 을 넓게, min_masked 를 1 이상으로 둔 MASKING 규칙을 준비한다.",
].join("\n");
const MSK_02 = "MSK-01 의 사전조건 1~2 참조";

const index = new Map<string, string>([
  ["REC-API-01", REC_API_01],
  ["FS-01", FS_01],
  ["FS-02", FS_02],
  ["FS-04", FS_04],
  ["MSK-01", MSK_01],
  ["MSK-02", MSK_02],
]);

describe("splitItems", () => {
  it("번호 항목 단위로 쪼갠다", () => {
    expect(splitItems(FS_02)).toEqual([
      "FS-01 의 사전조건 1~5 참조",
      "Opticon Fail-Safe = Fail-Closed 로 설정한다.",
    ]);
  });

  it("번호 없는 한 줄은 항목 1개로 본다", () => {
    expect(splitItems(FS_04)).toEqual(["FS-02 의 사전조건 참조"]);
  });

  it("번호로 시작하지 않는 줄은 앞 항목에 이어 붙인다", () => {
    const raw = "1. dog-fooding 계정으로 로그인해\n   accessToken 을 확보한다.\n2. 대상 id 를 확보한다.";
    expect(splitItems(raw)).toEqual([
      "dog-fooding 계정으로 로그인해\n   accessToken 을 확보한다.",
      "대상 id 를 확보한다.",
    ]);
  });

  it("빈 값은 빈 목록", () => {
    expect(splitItems("")).toEqual([]);
  });
});

describe("parseRef", () => {
  it("범위 있는 참조를 읽는다", () => {
    expect(parseRef("REC-API-01 의 사전조건 1~4 참조")).toEqual({
      targetId: "REC-API-01",
      upto: 4,
      text: "REC-API-01 의 사전조건 1~4 참조",
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
    expect(resolveItems("REC-API-01", index)).toHaveLength(5);
  });

  it("범위 참조는 앞 N개만 가져온다", () => {
    const items = resolveItems("FS-01", index);
    expect(items).toHaveLength(6); // 베이스 4 + 프록시 + Fail-Safe default
    expect(items[3]).toBe("Opticon Project Binding 구성 완료, Kill Switch 전 tier 해제.");
    expect(items[4]).toContain("장애 주입 프록시");
    // 5번(플랫폼 수신 상한)은 1~4 범위 밖이라 들어오면 안 된다
    expect(items.some((i) => i.includes("플랫폼 수신 상한값"))).toBe(false);
  });

  it("3단 체인(FS-04 -> FS-02 -> FS-01 -> REC-API-01)을 끝까지 펼친다", () => {
    const items = resolveItems("FS-04", index);
    expect(items).toEqual([
      "Company / Organization / Project(Type=API) 각 1개가 생성돼 있다.",
      "Project Guardian 1개가 등록돼 있다 (활성 Input Type=text, 지원 process_type 1개 이상).",
      "Active 상태의 API Key 1개가 발급돼 있다.",
      "Opticon Project Binding 구성 완료, Kill Switch 전 tier 해제.",
      "Bastion 과 Opticon 사이에 장애 주입 프록시가 연결돼 있다 (hang / 부분실패 200 / 파싱불가 / 응답drop 전환 가능).",
      "Opticon Fail-Safe = Fail-Closed 로 설정한다.",
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
    const ref = parseRef("MSK-01 의 사전조건 1~2 참조")!;
    const { title, items } = resolveRef(ref, index);
    expect(title).toBe("MSK-01 사전조건 1~2");
    expect(items).toHaveLength(2);
    expect(items.some((i) => i.includes("MASKING 규칙"))).toBe(false);
  });

  it("범위 없는 참조는 대상 전체를 준다", () => {
    const { title, items } = resolveRef(parseRef("MSK-01 의 사전조건 참조")!, index);
    expect(title).toBe("MSK-01 사전조건");
    expect(items).toHaveLength(3);
  });
});
