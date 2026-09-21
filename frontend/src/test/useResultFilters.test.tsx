import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useResultFilters } from "../hooks/useResultFilters";

const t = ((k: string) => k) as any;
const gridApiRef = { current: { onFilterChanged: vi.fn() } } as any;

function row(id: number, priority: string) {
  return {
    id,
    test_case: { tc_id: `TC-${id}`, priority, category: "기능" },
  } as any;
}

const results = [row(1, "핵심"), row(2, "중요"), row(3, "보통"), row(4, "낮음")];

function node(r: any) {
  return { data: r } as any;
}

describe("useResultFilters 우선순위 멀티 선택", () => {
  it("선택이 없으면 모든 우선순위가 통과한다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    expect(result.current.filterPriorities).toEqual([]);
    expect(result.current.isExternalFilterPresent()).toBe(false);
    results.forEach((r) => {
      expect(result.current.doesExternalFilterPass(node(r))).toBe(true);
    });
  });

  it("하나를 고르면 그 우선순위만 통과한다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    act(() => result.current.togglePriority("핵심"));

    expect(result.current.filterPriorities).toEqual(["핵심"]);
    expect(result.current.isExternalFilterPresent()).toBe(true);
    expect(result.current.doesExternalFilterPass(node(results[0]))).toBe(true);
    expect(result.current.doesExternalFilterPass(node(results[1]))).toBe(false);
  });

  it("둘을 고르면 둘 다 통과하고 나머지는 걸러진다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    act(() => result.current.togglePriority("핵심"));
    act(() => result.current.togglePriority("중요"));

    expect(result.current.filterPriorities).toEqual(["핵심", "중요"]);
    expect(result.current.doesExternalFilterPass(node(results[0]))).toBe(true);
    expect(result.current.doesExternalFilterPass(node(results[1]))).toBe(true);
    expect(result.current.doesExternalFilterPass(node(results[2]))).toBe(false);
    expect(result.current.doesExternalFilterPass(node(results[3]))).toBe(false);
  });

  it("고른 것을 다시 누르면 해제된다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    act(() => result.current.togglePriority("핵심"));
    act(() => result.current.togglePriority("중요"));
    act(() => result.current.togglePriority("핵심"));

    expect(result.current.filterPriorities).toEqual(["중요"]);
    expect(result.current.doesExternalFilterPass(node(results[0]))).toBe(false);
    expect(result.current.doesExternalFilterPass(node(results[1]))).toBe(true);
  });

  it("우선순위가 비어 있는 행은 선택이 있으면 걸러진다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    act(() => result.current.togglePriority("핵심"));

    const noPriority = { id: 9, test_case: { tc_id: "TC-9", priority: "" } } as any;
    expect(result.current.doesExternalFilterPass(node(noPriority))).toBe(false);
  });

  it("값이 빈 행이 있으면 미지정 선택지가 목록에 생기고 그 행만 골라낼 수 있다", () => {
    const withUnset = [...results, { id: 9, test_case: { tc_id: "TC-9", priority: "" } } as any];
    const { result } = renderHook(() => useResultFilters(gridApiRef, withUnset, t));

    expect(result.current.priorityOptions).toContain("");

    act(() => result.current.togglePriority(""));

    expect(result.current.doesExternalFilterPass(node(withUnset[4]))).toBe(true);
    expect(result.current.doesExternalFilterPass(node(results[0]))).toBe(false);
  });

  it("값이 빈 행이 없으면 미지정 선택지는 나오지 않는다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    expect(result.current.priorityOptions).not.toContain("");
  });

  it("고른 값이 결과 집합에서 사라져도 목록에 남아 체크를 풀 수 있다", () => {
    // 시트를 옮기면 그 시트에 없는 우선순위가 목록에서 빠진다. 빠지면 체크를 풀 수단이
    // 없어져 그리드가 빈 채로 잠긴다.
    const { result, rerender } = renderHook(
      ({ rows }) => useResultFilters(gridApiRef, rows, t),
      { initialProps: { rows: results } }
    );

    act(() => result.current.togglePriority("핵심"));
    expect(result.current.priorityOptions).toContain("핵심");

    // "핵심" 이 없는 시트로 옮긴 상황
    const onlyImportant = [row(10, "중요"), row(11, "중요")];
    rerender({ rows: onlyImportant });

    expect(result.current.filterPriorities).toEqual(["핵심"]);
    expect(result.current.priorityOptions).toContain("핵심");

    act(() => result.current.togglePriority("핵심"));
    expect(result.current.filterPriorities).toEqual([]);
    expect(result.current.doesExternalFilterPass(node(onlyImportant[0]))).toBe(true);
  });

  it("텍스트 검색과 우선순위는 둘 다 만족해야 통과한다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    act(() => result.current.togglePriority("핵심"));
    act(() => result.current.setFilterText("TC-1"));

    expect(result.current.doesExternalFilterPass(node(results[0]))).toBe(true);
    act(() => result.current.setFilterText("TC-2"));
    expect(result.current.doesExternalFilterPass(node(results[0]))).toBe(false);
  });

  it("결과(Result) 필터와 우선순위는 둘 다 만족해야 통과한다", () => {
    const rows = [
      { id: 1, test_case: { tc_id: "TC-1", priority: "핵심" }, result: "PASS" },
      { id: 2, test_case: { tc_id: "TC-2", priority: "핵심" }, result: "FAIL" },
    ] as any[];
    const { result } = renderHook(() => useResultFilters(gridApiRef, rows, t));

    act(() => result.current.togglePriority("핵심"));
    act(() => result.current.setFilterResult("PASS"));

    expect(result.current.doesExternalFilterPass(node(rows[0]))).toBe(true);
    expect(result.current.doesExternalFilterPass(node(rows[1]))).toBe(false);
  });

  it("초기화하면 선택이 모두 풀린다", () => {
    const { result } = renderHook(() => useResultFilters(gridApiRef, results, t));

    act(() => result.current.togglePriority("핵심"));
    act(() => result.current.togglePriority("중요"));
    act(() => result.current.clearFilters());

    expect(result.current.filterPriorities).toEqual([]);
    expect(result.current.isExternalFilterPresent()).toBe(false);
  });

  it("다른 필터와 함께 걸리면 둘 다 만족해야 통과한다", () => {
    const withCategory = [
      { id: 1, test_case: { tc_id: "TC-1", priority: "핵심", category: "기능" } },
      { id: 2, test_case: { tc_id: "TC-2", priority: "핵심", category: "보안" } },
    ] as any[];
    const { result } = renderHook(() => useResultFilters(gridApiRef, withCategory, t));

    act(() => result.current.togglePriority("핵심"));
    act(() => result.current.setFilterCategory("기능"));

    expect(result.current.doesExternalFilterPass(node(withCategory[0]))).toBe(true);
    expect(result.current.doesExternalFilterPass(node(withCategory[1]))).toBe(false);
  });
});
