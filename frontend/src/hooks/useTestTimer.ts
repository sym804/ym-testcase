import { useCallback, useEffect, useRef, useState } from "react";
import type { GridApi } from "ag-grid-community";

/**
 * 수행 화면의 행별 소요 시간 타이머.
 *
 * ★잰 시간을 화면에만 찍으면 저장되지 않는다. 경과가 확정되는 자리는 stopTimer
 *   하나뿐이라, 여기서 `onElapsed` 로 호출자에게 넘겨 저장을 맡긴다. 이 콜백이
 *   없던 동안 결과 5,209건 중 duration_sec 이 들어간 것이 0건이었다.
 */
export function useTestTimer(
  gridApiRef: React.RefObject<GridApi | null>,
  onElapsed?: (row: { id: number; duration_sec: number }) => void,
) {
  const [timerEnabled, setTimerEnabled] = useState<boolean>(() => {
    const saved = localStorage.getItem("tc_timer_enabled");
    return saved === null ? false : saved === "true";
  });
  const [timerRowId, setTimerRowId] = useState<number | null>(null);
  const [timerStart, setTimerStart] = useState<number | null>(null);
  const [timerDisplay, setTimerDisplay] = useState("");
  const timerIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopTimer = useCallback(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (timerRowId && timerStart) {
      const elapsed = Math.round((Date.now() - timerStart) / 1000);
      const api = gridApiRef.current;
      if (api) {
        api.forEachNode((node) => {
          if (node.data?.id === timerRowId) {
            node.data.duration_sec = (node.data.duration_sec || 0) + elapsed;
            api.refreshCells({ rowNodes: [node], columns: ["duration_sec"], force: true });
            onElapsed?.(node.data);
          }
        });
      }
    }
    setTimerRowId(null);
    setTimerStart(null);
    setTimerDisplay("");
  }, [timerRowId, timerStart, gridApiRef, onElapsed]);

  const startTimer = useCallback((rowId: number) => {
    stopTimer();
    setTimerRowId(rowId);
    setTimerStart(Date.now());
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    timerIntervalRef.current = setInterval(() => {
      setTimerStart((prev) => {
        if (!prev) return prev;
        const sec = Math.round((Date.now() - prev) / 1000);
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        setTimerDisplay(`${m}:${s.toString().padStart(2, "0")}`);
        return prev;
      });
    }, 1000);
  }, [stopTimer]);

  const toggleTimer = useCallback(() => {
    const next = !timerEnabled;
    setTimerEnabled(next);
    localStorage.setItem("tc_timer_enabled", String(next));
    if (!next) stopTimer();
  }, [timerEnabled, stopTimer]);

  // 컴포넌트 언마운트 시 타이머 정리
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, []);

  return {
    timerEnabled,
    timerRowId,
    timerDisplay,
    startTimer,
    stopTimer,
    toggleTimer,
  };
}
