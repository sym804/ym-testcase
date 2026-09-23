import { describe, it, expect } from "vitest";
import { PRIORITY_OPTIONS, priorityCellStyle } from "../utils/priority";

describe("우선순위", () => {
  it("4단계다", () => {
    expect(PRIORITY_OPTIONS).toEqual(["매우 높음", "높음", "보통", "낮음"]);
  });

  it("네 값 모두 색이 있고 서로 다르다", () => {
    const colors = PRIORITY_OPTIONS.map((p) => (priorityCellStyle({ value: p } as any) as any).color);
    expect(colors.every(Boolean)).toBe(true);
    expect(new Set(colors).size).toBe(4);
  });

  it("목록 밖의 값은 색을 입히지 않는다", () => {
    expect(priorityCellStyle({ value: "매우 낮음" } as any)).toEqual({});
    expect(priorityCellStyle({ value: "High" } as any)).toEqual({});
    expect(priorityCellStyle({ value: "" } as any)).toEqual({});
  });
});
