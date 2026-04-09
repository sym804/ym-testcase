import { useCallback, useEffect, useRef, useState } from "react";
import type { GridApi } from "ag-grid-community";

export function useTestTimer(gridApiRef: React.RefObject<GridApi | null>) {
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
          }
        });
      }
    }
    setTimerRowId(null);
    setTimerStart(null);
    setTimerDisplay("");
  }, [timerRowId, timerStart, gridApiRef]);

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
