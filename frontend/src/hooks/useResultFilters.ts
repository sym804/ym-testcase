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
  const [filterPriority, setFilterPriority] = useState("");

  const categoryOptions = useMemo(() => {
    const set = new Set<string>();
    results.forEach((r) => { if (r.test_case?.category) set.add(r.test_case.category); });
    return Array.from(set).sort();
  }, [results]);

  const priorityOptions = useMemo(() => {
    const set = new Set<string>();
    results.forEach((r) => { if (r.test_case?.priority) set.add(r.test_case.priority); });
    return Array.from(set).sort();
  }, [results]);

  const isExternalFilterPresent = useCallback(() => {
    return filterText !== "" || filterResult !== "" || filterCategory !== "" || filterPriority !== "";
  }, [filterText, filterResult, filterCategory, filterPriority]);

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

    // Priority 필터
    if (filterPriority && row.test_case?.priority !== filterPriority) return false;

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
  }, [filterText, filterResult, filterCategory, filterPriority, t]);

  // 필터 변경 시 그리드 재필터링
  useEffect(() => {
    gridApiRef.current?.onFilterChanged();
  }, [filterText, filterResult, filterCategory, filterPriority, gridApiRef]);

  const clearFilters = useCallback(() => {
    setFilterText("");
    setFilterResult("");
    setFilterCategory("");
    setFilterPriority("");
  }, []);

  return {
    filterText, setFilterText,
    filterResult, setFilterResult,
    filterCategory, setFilterCategory,
    filterPriority, setFilterPriority,
    categoryOptions,
    priorityOptions,
    isExternalFilterPresent,
    doesExternalFilterPass,
    clearFilters,
  };
}
