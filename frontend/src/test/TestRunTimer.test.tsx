import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTestTimer } from "../hooks/useTestTimer";

// 타이머가 잰 소요 시간이 화면에만 찍히고 저장되지 않았다.
// 결과 5,209건 중 duration_sec 이 들어간 것이 0건이었는데, 매뉴얼은
// "결과 입력 시 경과 시간이 기록됩니다" 라고 안내하고 수행 엑셀에도 칸이 있다.
// 경과가 확정되는 자리는 stopTimer 하나뿐이라 여기서 호출자에게 알려 줘야 한다.

function makeGrid(rowId: number, initial: number | null = null) {
  const node = { data: { id: rowId, test_case_id: rowId, duration_sec: initial } };
  const api = {
    forEachNode: (cb: (n: typeof node) => void) => cb(node),
    refreshCells: vi.fn(),
  };
  return { node, gridApiRef: { current: api } as any };
}

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("수행 타이머", () => {
  it("타이머를 멈추면 잰 시간을 호출자에게 넘긴다", () => {
    const { node, gridApiRef } = makeGrid(11);
    const onElapsed = vi.fn();
    const { result } = renderHook(() => useTestTimer(gridApiRef, onElapsed));

    act(() => {
      result.current.startTimer(11);
    });
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    act(() => {
      result.current.stopTimer();
    });

    expect(onElapsed).toHaveBeenCalledTimes(1);
    expect(onElapsed.mock.calls[0][0]).toMatchObject({ id: 11 });
    expect(onElapsed.mock.calls[0][0].duration_sec).toBeGreaterThanOrEqual(5);
    expect(node.data.duration_sec).toBeGreaterThanOrEqual(5);
  });

  it("이미 잰 시간이 있으면 더한다", () => {
    const { gridApiRef } = makeGrid(12, 30);
    const onElapsed = vi.fn();
    const { result } = renderHook(() => useTestTimer(gridApiRef, onElapsed));

    act(() => {
      result.current.startTimer(12);
    });
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    act(() => {
      result.current.stopTimer();
    });

    expect(onElapsed.mock.calls[0][0].duration_sec).toBeGreaterThanOrEqual(34);
  });

  it("시작한 적이 없으면 아무것도 넘기지 않는다", () => {
    const { gridApiRef } = makeGrid(13);
    const onElapsed = vi.fn();
    const { result } = renderHook(() => useTestTimer(gridApiRef, onElapsed));

    act(() => {
      result.current.stopTimer();
    });

    expect(onElapsed).not.toHaveBeenCalled();
  });
});
