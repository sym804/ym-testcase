import { describe, it, expect } from "vitest";
import { planTcIdFill, resolveTcIdSeed, dominantTcIdPrefix, findTcIdCollisions } from "../utils/tcId";

const idsOf = (all: (string | null)[], plan: { index: number; tcId: string }[]) => {
  const out = [...all];
  for (const p of plan) out[p.index] = p.tcId;
  return out;
};

describe("resolveTcIdSeed", () => {
  it("선택 첫 행의 TC ID를 기준으로 삼고 다음 행부터 채운다", () => {
    expect(resolveTcIdSeed(["SFW-003", "TC-001", "TC-001"], 0)).toEqual({
      prefix: "SFW-", startNum: 3, numWidth: 3, fillFrom: 1,
    });
  });

  it("선택 첫 행에 TC ID가 없으면 위쪽에서 가장 가까운 것을 쓴다", () => {
    expect(resolveTcIdSeed(["SFW-007", "", ""], 1)).toEqual({
      prefix: "SFW-", startNum: 7, numWidth: 3, fillFrom: 0,
    });
  });

  it("위쪽에도 없으면 시트에서 가장 많이 쓰인 접두사와 최대 번호를 쓴다", () => {
    expect(resolveTcIdSeed(["", "", "API-012", "API-005", "ETC-1"], 0)).toEqual({
      prefix: "API-", startNum: 12, numWidth: 3, fillFrom: 0,
    });
  });

  it("접두사 자릿수를 그대로 따른다", () => {
    expect(resolveTcIdSeed(["TC-2026-0009"], 0)).toEqual({
      prefix: "TC-2026-", startNum: 9, numWidth: 4, fillFrom: 1,
    });
  });

  it("쓸 만한 TC ID가 하나도 없으면 null", () => {
    expect(resolveTcIdSeed(["", null, "메모"], 0)).toBeNull();
  });
});

describe("planTcIdFill", () => {
  it("중복된 TC ID를 이어서 다시 매긴다 (Starfort TC2 상황)", () => {
    const all = ["SFW-001", "SFW-002", "SFW-003", ...Array(4).fill("TC-001")];
    const plan = planTcIdFill(all, [2, 3, 4, 5, 6]);
    expect(idsOf(all, plan!)).toEqual([
      "SFW-001", "SFW-002", "SFW-003", "SFW-004", "SFW-005", "SFW-006", "SFW-007",
    ]);
  });

  it("빈 TC ID도 채운다", () => {
    const all = ["SFW-010", "", "", ""];
    const plan = planTcIdFill(all, [0, 1, 2, 3]);
    expect(idsOf(all, plan!)).toEqual(["SFW-010", "SFW-011", "SFW-012", "SFW-013"]);
  });

  it("떨어져 있는 선택도 선택 순서대로 이어 붙인다", () => {
    const all = ["SFW-001", "keep", "", "keep", ""];
    const plan = planTcIdFill(all, [0, 2, 4]);
    expect(idsOf(all, plan!)).toEqual(["SFW-001", "keep", "SFW-002", "keep", "SFW-003"]);
  });

  it("이미 순번이 맞으면 바꿀 것이 없다", () => {
    expect(planTcIdFill(["SFW-001", "SFW-002", "SFW-003"], [0, 1, 2])).toEqual([]);
  });

  it("기준으로 삼은 첫 행은 건드리지 않는다", () => {
    const plan = planTcIdFill(["SFW-100", "TC-001"], [0, 1]);
    expect(plan).toEqual([{ index: 1, tcId: "SFW-101" }]);
  });

  it("기준이 없으면 null", () => {
    expect(planTcIdFill(["", ""], [0, 1])).toBeNull();
  });

  it("선택이 없으면 빈 계획", () => {
    expect(planTcIdFill(["SFW-001"], [])).toEqual([]);
  });
});

describe("dominantTcIdPrefix", () => {
  it("가장 많이 쓰인 접두사와 최대 번호를 고른다", () => {
    expect(dominantTcIdPrefix(["SFW-001", "SFW-030", "API-999"])).toEqual({
      prefix: "SFW-", maxNum: 30, numWidth: 3,
    });
  });

  it("접두사가 없으면 null", () => {
    expect(dominantTcIdPrefix(["", null, "메모"])).toBeNull();
  });

  // 대량 행 추가는 여기서 나온 maxNum 뒤로 이어 붙인다.
  // 예전에는 await 루프 안에서 rowData 클로저가 안 바뀌어 전부 같은 번호를 받았다.
  it("대량 추가 시 번호가 겹치지 않고 이어진다", () => {
    const seed = dominantTcIdPrefix(["SFW-001", "SFW-002", "SFW-003"])!;
    const made = Array.from({ length: 4 }, (_, i) =>
      seed.prefix + String(seed.maxNum + i + 1).padStart(seed.numWidth, "0")
    );
    expect(made).toEqual(["SFW-004", "SFW-005", "SFW-006", "SFW-007"]);
    expect(new Set(made).size).toBe(4);
  });

  it("기존 TC ID가 없으면 호출부가 TC- 로 폴백한다", () => {
    const seed = dominantTcIdPrefix([]);
    const prefix = seed?.prefix ?? "TC-";
    const width = seed?.numWidth ?? 3;
    const base = seed?.maxNum ?? 0;
    expect([1, 2].map((i) => prefix + String(base + i).padStart(width, "0")))
      .toEqual(["TC-001", "TC-002"]);
  });
});

describe("필터가 걸린 상태", () => {
  it("3순위 폴백이 숨은 행의 번호까지 본다", () => {
    // 화면에는 빈 행만 보이고, SFW-020 은 필터로 숨어 있다
    const visible = ["", ""];
    const all = ["", "", "SFW-020", "SFW-007"];
    expect(resolveTcIdSeed(visible, 0, all)).toEqual({
      prefix: "SFW-", startNum: 20, numWidth: 3, fillFrom: 0,
    });
    // 전체를 안 넘기면 기준을 못 찾아 null 이 된다
    expect(resolveTcIdSeed(visible, 0)).toBeNull();
  });

  it("숨은 행 기준으로 이어 붙인다", () => {
    const plan = planTcIdFill(["", ""], [0, 1], ["", "", "SFW-020"]);
    expect(plan).toEqual([
      { index: 0, tcId: "SFW-021" },
      { index: 1, tcId: "SFW-022" },
    ]);
  });
});

describe("findTcIdCollisions", () => {
  it("숨은 행과 겹치면 잡아낸다", () => {
    const assigned = [{ key: "id:1", tcId: "SFW-008" }];
    const all = [
      { key: "id:1", tcId: "SFW-008" },
      { key: "id:9", tcId: "SFW-008" }, // 필터로 숨은 기존 행
    ];
    expect(findTcIdCollisions(assigned, all)).toEqual(["SFW-008"]);
  });

  it("자기 자신은 충돌로 세지 않는다", () => {
    const assigned = [{ key: "id:1", tcId: "SFW-008" }];
    expect(findTcIdCollisions(assigned, [{ key: "id:1", tcId: "SFW-008" }])).toEqual([]);
  });

  it("겹치는 게 없으면 빈 배열", () => {
    const assigned = [{ key: "id:1", tcId: "SFW-004" }];
    const all = [{ key: "id:1", tcId: "SFW-004" }, { key: "id:2", tcId: "SFW-005" }];
    expect(findTcIdCollisions(assigned, all)).toEqual([]);
  });
});
