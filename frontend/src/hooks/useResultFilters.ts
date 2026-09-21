import { useCallback, useEffect, useMemo, useState } from "react";
import type { GridApi } from "ag-grid-community";
import type { TestResult } from "../types";
import type { TFunction } from "i18next";

export function useResultFilters(
  gridApiRef: React.RefObject<GridApi | null>,
  results: TestResult[],
  t: TFunction,
) {
  const [filterText, setFilterText] = useState("");
  const [filterResult, setFilterResult] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  // 우선순위는 여러 개를 동시에 고른다. 빈 배열이 "전체"다.
  const [filterPriorities, setFilterPriorities] = useState<string[]>([]);

  const categoryOptions = useMemo(() => {
    const set = new Set<string>();
    results.forEach((r) => { if (r.test_case?.category) set.add(r.test_case.category); });
    return Array.from(set).sort();
  }, [results]);

  // 빈 문자열은 "우선순위 미지정" 을 뜻하는 정식 선택지다. 값이 없는 행을 골라낼 방법이
  // 없으면, 하나라도 고른 순간 그 행들이 이유 없이 사라진 것처럼 보인다.
  const priorityOptions = useMemo(() => {
    const set = new Set<string>();
    let hasUnset = false;
    results.forEach((r) => {
      if (!r.test_case) return;
      if (r.test_case.priority) set.add(r.test_case.priority);
      else hasUnset = true;
    });
    // 고른 값이 지금 결과 집합에 없어도 목록에 남긴다. 시트나 런을 옮기면 그 값이 사라지는데,
    // 목록에서 빠지면 체크를 풀 수단이 없어져 그리드가 빈 채로 잠긴다.
    filterPriorities.forEach((p) => {
      if (p) set.add(p);
      else hasUnset = true;
    });
    const sorted = Array.from(set).sort();
    return hasUnset ? [...sorted, ""] : sorted;
  }, [results, filterPriorities]);

  const togglePriority = useCallback((value: string) => {
    setFilterPriorities((prev) =>
      prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
    );
  }, []);

  const isExternalFilterPresent = useCallback(() => {
    return filterText !== "" || filterResult !== "" || filterCategory !== "" || filterPriorities.length > 0;
  }, [filterText, filterResult, filterCategory, filterPriorities]);

  const doesExternalFilterPass = useCallback((node: { data?: TestResult }) => {
    const row = node.data;
    if (!row) return true;

    // Result 필터
    if (filterResult) {
      const val = (row.result as string) || "";
      if (filterResult === t("notEntered")) {
        if (val !== "") return false;
      } else {
        if (val !== filterResult) return false;
      }
    }

    // Category 필터
    if (filterCategory && row.test_case?.category !== filterCategory) return false;

    // Priority 필터: 고른 것 중 하나라도 맞으면 통과. 아무것도 안 골랐으면 전체 통과.
    if (filterPriorities.length > 0 && !filterPriorities.includes(row.test_case?.priority || "")) {
      return false;
    }

    // 텍스트 검색
    if (filterText) {
      const q = filterText.toLowerCase();
      const fields = [
        row.test_case?.tc_id,
        row.test_case?.category,
        row.test_case?.depth1,
        row.test_case?.depth2,
        row.test_case?.test_steps,
        row.test_case?.expected_result,
        row.actual_result,
        row.remarks,
      ];
      const match = fields.some((f) => f && f.toLowerCase().includes(q));
      if (!match) return false;
    }

    return true;
  }, [filterText, filterResult, filterCategory, filterPriorities, t]);

  // 필터 변경 시 그리드 재필터링
  useEffect(() => {
    gridApiRef.current?.onFilterChanged();
  }, [filterText, filterResult, filterCategory, filterPriorities, gridApiRef]);

  const clearFilters = useCallback(() => {
    setFilterText("");
    setFilterResult("");
    setFilterCategory("");
    setFilterPriorities([]);
  }, []);

  return {
    filterText, setFilterText,
    filterResult, setFilterResult,
    filterCategory, setFilterCategory,
    filterPriorities, setFilterPriorities, togglePriority,
    categoryOptions,
    priorityOptions,
    isExternalFilterPresent,
    doesExternalFilterPass,
    clearFilters,
  };
}
