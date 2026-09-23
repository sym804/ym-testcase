import { describe, it, expect } from "vitest";
import { PRIORITY_COLORS, PRIORITY_OPTIONS, priorityCellStyle } from "../utils/priority";

describe("우선순위", () => {
  it("4단계다", () => {
    expect(PRIORITY_OPTIONS).toEqual(["매우 높음", "높음", "보통", "낮음"]);
  });

  it("네 값 모두 색이 있고 서로 다르다", () => {
    const colors = PRIORITY_OPTIONS.map((p) => (priorityCellStyle({ value: p } as any) as any).color);
    expect(colors.every(Boolean)).toBe(true);
    expect(new Set(colors).size).toBe(4);
  });

  it("색은 테마 토큰(CSS 변수)이다", () => {
    // 고정 hex 로 되돌리면 다크 테마에서 대비가 무너진다(예전 다크 "보통" 3.22:1).
    // 토큰 값의 대비는 cssTokens.test.ts 가 본다. 여기서는 그 토큰을 실제로 쓰는지 본다.
    expect(Object.values(PRIORITY_COLORS)).toEqual([
      "var(--priority-critical)", "var(--priority-high)", "var(--priority-normal)", "var(--priority-low)",
    ]);
  });

  it("목록 밖의 값은 색을 입히지 않는다", () => {
    expect(priorityCellStyle({ value: "매우 낮음" } as any)).toEqual({});
    expect(priorityCellStyle({ value: "High" } as any)).toEqual({});
    expect(priorityCellStyle({ value: "" } as any)).toEqual({});
  });
});
