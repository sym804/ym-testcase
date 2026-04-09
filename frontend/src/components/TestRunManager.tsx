import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type CellClassParams,
  type CellStyle,
  type GridApi,
  type GridReadyEvent,
  type CellKeyDownEvent,
  type CellClickedEvent,
  type CellValueChangedEvent,
} from "ag-grid-community";
import { useTranslation } from "react-i18next";
import { testRunsApi, testCasesApi } from "../api";
import type { TestRun, TestResult } from "../types";
import { TestRunStatus } from "../types";
import { AG_GRID_LOCALE_KO } from "../agGridLocaleKo";
import { AG_GRID_LOCALE_EN } from "../agGridLocaleEn";
import toast from "react-hot-toast";
import MarkdownCell from "./MarkdownCell";
import HighlightCell from "./HighlightCell";
import { useTestTimer } from "../hooks/useTestTimer";
import { useAttachments } from "../hooks/useAttachments";
import { useResultFilters } from "../hooks/useResultFilters";

ModuleRegistry.registerModules([AllCommunityModule]);

interface Props {
  projectId: number;
  project: import("../types").Project;
}

const RESULT_OPTIONS = ["", "PASS", "FAIL", "BLOCK", "N/A"];

const resultColors: Record<string, { bg: string; fg: string }> = {
  PASS: { bg: "rgba(26, 127, 55, 0.15)", fg: "var(--color-pass)" },
  FAIL: { bg: "rgba(207, 34, 46, 0.15)", fg: "var(--color-fail)" },
  BLOCK: { bg: "rgba(191, 135, 0, 0.15)", fg: "var(--color-block)" },
  "N/A": { bg: "rgba(107, 114, 128, 0.15)", fg: "var(--text-secondary)" },
};

function resultCellStyle(params: CellClassParams) {
  const val = params.value as string;
  const c = resultColors[val];
  const base: CellStyle = { textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center" };
  if (c) return { ...base, backgroundColor: c.bg, color: c.fg, fontWeight: 600 };
  return base;
}

export default function TestRunManager({ projectId, project }: Props) {
  const { t, i18n } = useTranslation("testrun");
  const gridLocale = i18n.language === "ko" ? AG_GRID_LOCALE_KO : AG_GRID_LOCALE_EN;
  const canManageRun = project.my_role === "admin" || project.my_role === "tester";
  const canDeleteRun = project.my_role === "admin";
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<TestRun | null>(null);
  const [results, setResults] = useState<TestResult[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", version: "", environment: "", round: 1 });
  const [creating, setCreating] = useState(false);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [showAllCompleted, setShowAllCompleted] = useState(false);
  const [countTick, setCountTick] = useState(0);
  const gridApiRef = useRef<GridApi | null>(null);

  // ── 시트 탭 ──
  const [sheets, setSheets] = useState<{ name: string; tc_count: number }[]>([]);
  const [activeSheet, setActiveSheet] = useState<string | null>(null);
  const sheetInitRef = useRef(false);

  // ── Undo 스택 ──
  const undoStackRef = useRef<{ rowId: number; field: string; oldValue: string }[]>([]);

  // ── 커스텀 훅 ──
  const {
    timerEnabled, timerRowId, timerDisplay,
    startTimer, stopTimer, toggleTimer,
  } = useTestTimer(gridApiRef);

  const {
    attachmentsMap, previewImage, setPreviewImage, fileInputRef,
    resetAttachments, loadAttachmentFor, handleFileUpload,
    handleDeleteAttachment, triggerUpload, handleDropUpload,
  } = useAttachments(gridApiRef, t);

  const {
    filterText, setFilterText,
    filterResult, setFilterResult,
    filterCategory, setFilterCategory,
    filterPriority, setFilterPriority,
    categoryOptions, priorityOptions,
    isExternalFilterPresent, doesExternalFilterPass,
    clearFilters,
  } = useResultFilters(gridApiRef, results, t);

  // ── 여러 행 일괄 저장 ──
  const saveManyResults = useCallback(async (rows: TestResult[]) => {
    if (!selectedRun || rows.length === 0) return;
    const payload = rows.map((r) => ({
      test_case_id: r.test_case_id,
      result: r.result === "" ? "NS" : r.result === "N/A" ? "NA" : r.result,
      actual_result: r.actual_result || undefined,
      issue_link: r.issue_link || undefined,
      remarks: r.remarks || undefined,
    }));
    try {
      await testRunsApi.submitResults(projectId, selectedRun.id, payload);
    } catch {
      toast.error(t("saveFailed"));
    }
  }, [projectId, selectedRun]);

  // ── Shift+Click 범위 채우기용 앵커 ──
  const fillAnchorRef = useRef<{ rowIndex: number; field: string; value: string } | null>(null);

  const onCellClicked = useCallback((event: CellClickedEvent) => {
    const field = event.column?.getColId();
    if (!field || field !== "result") return;

    const browserEvent = event.event as MouseEvent;
    const api = gridApiRef.current;
    if (!api || event.rowIndex == null) return;

    // 일반 클릭은 앵커만 저장하고 AG Grid singleClickEdit에 맡김
    if (!browserEvent?.shiftKey) {
      fillAnchorRef.current = {
        rowIndex: event.rowIndex,
        field,
        value: event.value as string,
      };
      return;
    }

    if (fillAnchorRef.current && fillAnchorRef.current.field === field) {
      // Shift+Click: 앵커부터 현재 행까지 같은 값으로 채우기
      const anchor = fillAnchorRef.current;
      const startIdx = Math.min(anchor.rowIndex, event.rowIndex);
      const endIdx = Math.max(anchor.rowIndex, event.rowIndex);
      const changed: TestResult[] = [];

      api.forEachNodeAfterFilterAndSort((node) => {
        if (node.rowIndex != null && node.rowIndex >= startIdx && node.rowIndex <= endIdx && node.data) {
          node.data[field] = anchor.value;
          changed.push(node.data);
        }
      });

      if (changed.length > 0) {
        api.refreshCells({ force: true });
        setCountTick((t) => t + 1);
        toast.success(t("fillResult", { count: changed.length, value: anchor.value }));
        saveManyResults(changed);
      }
      fillAnchorRef.current = null;
    }
  }, [saveManyResults]);

  const loadRuns = useCallback(async () => {
    setLoadingRuns(true);
    try {
      const data = await testRunsApi.list(projectId);
      setRuns(data);
    } catch {
      toast.error(t("loadFailed"));
    } finally {
      setLoadingRuns(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // ── 시트 목록 로드 ──
  useEffect(() => {
    testCasesApi.listSheets(projectId).then((s) => {
      setSheets(s);
      if (s.length > 1 && !sheetInitRef.current) {
        sheetInitRef.current = true;
        setActiveSheet(s[0].name);
      }
    }).catch(() => {});
  }, [projectId]);

  // 시트 변경 시 선택된 런 다시 로드
  useEffect(() => {
    if (selectedRun) loadRunDetail(selectedRun);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSheet]);

  const loadRunDetail = useCallback(
    async (run: TestRun) => {
      setSelectedRun(run);
      setLoadingResults(true);
      resetAttachments(); // 첨부파일 캐시 초기화
      try {
        const detail = await testRunsApi.getOne(projectId, run.id);
        // 백엔드 값 → 표시 값 변환 (NS→"", NA→"N/A")
        const mapped = (detail.results || []).map((r: TestResult) => ({
          ...r,
          result: r.result === "NS" ? "" : r.result === "NA" ? "N/A" : r.result,
        }));
        // 시트 필터 적용
        if (activeSheet) {
          setResults(mapped.filter((r) => r.test_case?.sheet_name === activeSheet));
        } else if (sheets.length > 1) {
          // 전체 보기: 시트 순서대로 정렬 + 연속 번호
          const sheetOrder = sheets.map((s) => s.name);
          const sorted = [...mapped].sort((a, b) => {
            const ai = sheetOrder.indexOf(a.test_case?.sheet_name || "기본");
            const bi = sheetOrder.indexOf(b.test_case?.sheet_name || "기본");
            if (ai !== bi) return ai - bi;
            return (a.test_case?.no || 0) - (b.test_case?.no || 0);
          });
          let seq = 1;
          for (const r of sorted) {
            if (r.test_case) r.test_case = { ...r.test_case, no: seq++ };
          }
          setResults(sorted);
        } else {
          setResults(mapped);
        }
      } catch {
        toast.error(t("resultLoadFailed"));
      } finally {
        setLoadingResults(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projectId, activeSheet]
  );

  // countTick을 의존성에 넣어 그리드 변경 시 재계산
  const getGridRows = useCallback(() => {
    const rows: TestResult[] = [];
    gridApiRef.current?.forEachNode((node) => { if (node.data) rows.push(node.data); });
    return rows.length > 0 ? rows : results;
  }, [results]);

  const completionRate = useMemo(() => {
    void countTick;
    const rows = getGridRows();
    if (rows.length === 0) return 0;
    const done = rows.filter((r) => r.result && r.result !== "").length;
    return Math.round((done / rows.length) * 100);
  }, [countTick, getGridRows]);

  // 행 포커스 변경 시 타이머 전환 + 첨부파일 lazy 로드
  const onRowFocused = useCallback((rowId: number | null) => {
    if (!rowId) return;
    loadAttachmentFor(rowId);
    if (!timerEnabled || rowId === timerRowId) return;
    startTimer(rowId);
  }, [timerEnabled, timerRowId, startTimer, loadAttachmentFor]);

  // ── 셀 편집 시 즉시 저장 ──
  const saveResultRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const saveOneResult = useCallback(async (row: TestResult) => {
    if (!selectedRun) return;
    const mapped = {
      test_case_id: row.test_case_id,
      result: row.result === "" ? "NS" : row.result === "N/A" ? "NA" : row.result,
      actual_result: row.actual_result || undefined,
      issue_link: row.issue_link || undefined,
      remarks: row.remarks || undefined,
    };
    try {
      await testRunsApi.submitResults(projectId, selectedRun.id, [mapped]);
    } catch {
      toast.error(t("saveFailed"));
    }
  }, [projectId, selectedRun]);

  // ── 키보드 숏컷: P/F/B/N = 결과 빠른 입력, Ctrl+D = 선택 행 채우기 ──
  const SHORTCUT_MAP: Record<string, string> = { p: "PASS", f: "FAIL", b: "BLOCK", n: "N/A" };

  const onCellKeyDown = useCallback((event: CellKeyDownEvent) => {
    const e = event.event as KeyboardEvent;
    if (!e) return;
    const api = gridApiRef.current;
    if (!api) return;

    // P/F/B/N 단축키 (편집 중이 아닐 때, Ctrl/Alt 미사용)
    const key = e.key.toLowerCase();
    if (!e.ctrlKey && !e.metaKey && !e.altKey && SHORTCUT_MAP[key]) {
      const col = event.column?.getColId();
      // 편집 가능한 텍스트 셀 편집중이면 무시
      if (col && col !== "result" && col !== "actual_result" && col !== "issue_link" && col !== "remarks") {
        // read-only 컬럼이면 결과 입력
      } else if (col && col !== "result") {
        return; // 텍스트 편집 컬럼에서는 무시
      }

      e.preventDefault();
      const value = SHORTCUT_MAP[key];
      const focusedCell = api.getFocusedCell();
      if (focusedCell) {
        const node = api.getDisplayedRowAtIndex(focusedCell.rowIndex);
        if (node?.data) {
          undoStackRef.current.push({ rowId: node.data.id, field: "result", oldValue: node.data.result ?? "" });
          node.data.result = value;
          api.refreshCells({ rowNodes: [node], force: true });
          setCountTick((t) => t + 1);
          saveOneResult(node.data);
          // 다음 행으로 포커스 이동
          const nextIdx = focusedCell.rowIndex + 1;
          if (nextIdx < (api.getDisplayedRowCount())) {
            api.setFocusedCell(nextIdx, "result");
          }
        }
      }
      return;
    }

    // Ctrl+D: 현재 셀 값을 선택된 행에 채우기
    if (e.key === "d" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!event.column) return;
      const field = event.column.getColId();
      const sourceValue = event.value;
      const selectedNodes = api.getSelectedNodes();
      if (selectedNodes.length === 0) return;

      const changed: TestResult[] = [];
      selectedNodes.forEach((node) => {
        if (node.data && node !== event.node) {
          node.data[field] = sourceValue;
          changed.push(node.data);
        }
      });
      if (changed.length > 0) {
        api.refreshCells({ force: true });
        setCountTick((t) => t + 1);
        toast.success(t("fillResult", { count: changed.length, value: sourceValue }));
        saveManyResults(changed);
      }
    }

    // Ctrl+Z: Undo
    if (e.key === "z" && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
      e.preventDefault();
      const entry = undoStackRef.current.pop();
      if (!entry) { toast(t("undoEmpty")); return; }
      api.forEachNode((node) => {
        if (node.data?.id === entry.rowId) {
          node.data[entry.field] = entry.oldValue;
          api.refreshCells({ rowNodes: [node], force: true });
          setCountTick((t) => t + 1);
          saveOneResult(node.data);
        }
      });
      toast.success(t("undoDone"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveManyResults, saveOneResult]);

  // ── 선택 행 결과 일괄 입력 ──
  const handleBulkResult = (value: string) => {
    const api = gridApiRef.current;
    if (!api) return;
    const selectedNodes = api.getSelectedNodes();
    if (selectedNodes.length === 0) {
      toast.error(t("selectRowsFirst"));
      return;
    }
    const changed: TestResult[] = [];
    selectedNodes.forEach((node) => {
      if (node.data) {
        node.data.result = value;
        changed.push(node.data);
      }
    });
    api.refreshCells({ force: true });
    setCountTick((t) => t + 1);
    toast.success(t("bulkResultApplied", { count: selectedNodes.length, value: value || t("bulkResultEmpty") }));
    saveManyResults(changed);
  };

  // ── 결과 일괄 드롭다운 ──
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false);
  const bulkMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (bulkMenuRef.current && !bulkMenuRef.current.contains(e.target as Node)) {
        setBulkMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ── 결과 카운트 ──
  const resultCounts = useMemo(() => {
    void countTick;
    const rows = getGridRows();
    const notEnteredLabel = t("notEntered");
    const counts: Record<string, number> = { PASS: 0, FAIL: 0, BLOCK: 0, "N/A": 0, [notEnteredLabel]: 0 };
    rows.forEach((r) => {
      const val = (r.result as string) || "";
      if (val === "PASS") counts["PASS"]++;
      else if (val === "FAIL") counts["FAIL"]++;
      else if (val === "BLOCK") counts["BLOCK"]++;
      else if (val === "N/A") counts["N/A"]++;
      else counts[notEnteredLabel]++;
    });
    return counts;
  }, [countTick, getGridRows]);

  const columnDefs = useMemo<ColDef[]>(
    () => [
      {
        field: "test_case.no",
        headerName: "No",
        width: 60,
        valueGetter: (params) => params.data?.test_case?.no ?? "",
      },
      {
        field: "test_case.tc_id",
        headerName: "TC ID",
        width: 100,
        valueGetter: (params) => params.data?.test_case?.tc_id || "",
        cellRenderer: HighlightCell,
      },
      {
        field: "test_case.category",
        headerName: "Category",
        width: 100,
        valueGetter: (params) => params.data?.test_case?.category || "",
        cellRenderer: HighlightCell,
      },
      {
        field: "test_case.depth1",
        headerName: "Depth 1",
        width: 120,
        valueGetter: (params) => params.data?.test_case?.depth1 || "",
        cellRenderer: HighlightCell,
      },
      {
        field: "test_case.depth2",
        headerName: "Depth 2",
        width: 120,
        valueGetter: (params) => params.data?.test_case?.depth2 || "",
        cellRenderer: HighlightCell,
      },
      {
        field: "test_case.priority",
        headerName: "Priority",
        width: 80,
        valueGetter: (params) => params.data?.test_case?.priority || "",
      },
      {
        field: "test_case.test_steps",
        headerName: "Test Steps",
        minWidth: 350, flex: 2,
        wrapText: true,
        autoHeight: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
        valueGetter: (params) => params.data?.test_case?.test_steps || "",
      },
      {
        field: "test_case.expected_result",
        headerName: "Expected",
        minWidth: 300, flex: 2,
        wrapText: true,
        autoHeight: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
        valueGetter: (params) => params.data?.test_case?.expected_result || "",
      },
      {
        field: "result",
        headerName: "Result",
        width: 100,
        editable: false,
        cellStyle: resultCellStyle,
        cellRenderer: (params: { data: TestResult; node: { rowIndex: number } }) => {
          const row = params.data;
          if (!row) return null;
          return (
            <select
              value={row.result || ""}
              onChange={(e) => {
                const newVal = e.target.value;
                row.result = newVal;
                gridApiRef.current?.refreshCells({ rowNodes: [gridApiRef.current.getRowNode(String(row.id))!], columns: ["result"], force: true });
                saveOneResult(row);
                setCountTick((t) => t + 1);
                // 앵커 저장 (Shift+클릭 채우기용)
                fillAnchorRef.current = {
                  rowIndex: params.node.rowIndex,
                  field: "result",
                  value: newVal,
                };
              }}
              style={{
                width: "100%",
                height: "100%",
                border: "none",
                background: "transparent",
                color: "inherit",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                textAlign: "center",
                outline: "none",
              }}
            >
              {RESULT_OPTIONS.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          );
        },
      },
      {
        field: "actual_result",
        headerName: "Actual Result",
        width: 200,
        wrapText: true,
        autoHeight: true,
        editable: true,
        cellEditor: "agLargeTextCellEditor",
        cellEditorPopup: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
      },
      {
        field: "issue_link",
        headerName: "Issue Link",
        width: 140,
        editable: true,
      },
      ...(timerEnabled ? [{
        field: "duration_sec",
        headerName: t("durationSec"),
        width: 80,
        valueFormatter: (params: { value: unknown }) => {
          const v = params.value as number;
          if (!v) return "";
          return v < 60 ? `${v.toFixed(0)}s` : `${(v / 60).toFixed(1)}m`;
        },
      }] : []),
      {
        field: "attachments",
        headerName: t("attachment"),
        width: 140,
        cellRenderer: (params: { data: TestResult }) => {
          const row = params.data;
          if (!row) return null;
          const atts = attachmentsMap[row.id] || [];
          return (
            <div style={{ display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap", padding: "2px 0" }}>
              {atts.map((att) => (
                <span key={att.id} style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                  <span
                    style={{
                      fontSize: 11,
                      color: "#2563EB",
                      cursor: "pointer",
                      textDecoration: "underline",
                      maxWidth: 70,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      display: "inline-block",
                    }}
                    title={att.filename}
                    onClick={(e) => {
                      e.stopPropagation();
                      fetch(`/api/attachments/download/${att.id}`, {
                        credentials: "include",
                      })
                        .then((res) => {
                          if (!res.ok) throw new Error("Failed");
                          return res.blob();
                        })
                        .then((blob) => {
                          setPreviewImage({ url: URL.createObjectURL(blob), filename: att.filename });
                        })
                        .catch(() => toast.error(t("imageLoadFailed")));
                    }}
                  >
                    {att.filename}
                  </span>
                  <span
                    style={{ fontSize: 11, color: "var(--color-fail)", cursor: "pointer", fontWeight: 700 }}
                    title={t("common:delete")}
                    onClick={(e) => { e.stopPropagation(); handleDeleteAttachment(att.id, row.id); }}
                  >×</span>
                </span>
              ))}
              <button
                style={{
                  fontSize: 14,
                  border: "1px solid var(--border-input)",
                  borderRadius: 4,
                  backgroundColor: "var(--bg-input)",
                  color: "#64748B",
                  cursor: "pointer",
                  padding: "0 5px",
                  lineHeight: "20px",
                }}
                title={t("imageAttach")}
                onClick={(e) => {
                  e.stopPropagation();
                  triggerUpload(row.id);
                }}
              >
                +
              </button>
            </div>
          );
        },
      },
      {
        field: "remarks",
        headerName: "Remarks",
        minWidth: 200,
        flex: 1,
        editable: true,
        wrapText: true,
        autoHeight: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [attachmentsMap, timerEnabled]
  );

  const defaultColDef = useMemo<ColDef>(
    () => ({ resizable: true, sortable: true, tooltipShowDelay: 300, wrapText: true, autoHeight: true }),
    []
  );

  const onCellValueChanged = useCallback((event: CellValueChangedEvent) => {
    if (!event.data) return;
    // Undo 스택에 기록
    if (event.column && event.oldValue !== event.newValue) {
      undoStackRef.current.push({
        rowId: event.data.id,
        field: event.column.getColId(),
        oldValue: event.oldValue ?? "",
      });
      if (undoStackRef.current.length > 50) undoStackRef.current.shift();
    }
    // 카운트 뱃지 갱신
    setCountTick((t) => t + 1);
    // debounce로 즉시 저장
    if (saveResultRef.current) clearTimeout(saveResultRef.current);
    saveResultRef.current = setTimeout(() => saveOneResult(event.data), 300);
  }, [saveOneResult]);

  const handleDelete = async () => {
    if (!selectedRun) return;
    if (!confirm(t("deleteConfirm", { name: selectedRun.name }))) return;
    try {
      await testRunsApi.delete(projectId, selectedRun.id);
      toast.success(t("deleteSuccess"));
      setSelectedRun(null);
      setResults([]);
      loadRuns();
    } catch {
      toast.error(t("deleteFailed"));
    }
  };

  const handleClone = async () => {
    if (!selectedRun) return;
    if (!confirm(t("cloneConfirm", { name: selectedRun.name }))) return;
    try {
      const cloned = await testRunsApi.clone(projectId, selectedRun.id);
      toast.success(t("cloneSuccess"));
      loadRuns();
      loadRunDetail(cloned);
    } catch {
      toast.error(t("cloneFailed"));
    }
  };

  const handleComplete = async () => {
    if (!selectedRun) return;
    // 전체 결과 조회 (모든 시트 포함 — 현재 화면은 시트 필터링된 상태일 수 있음)
    try {
      const fullDetail = await testRunsApi.getOne(projectId, selectedRun.id);
      const allResults = fullDetail.results || [];
      const nsCount = allResults.filter((r: TestResult) => !r.result || r.result === "NS").length;
      if (nsCount > 0) {
        const proceed = confirm(
          t("completeConfirmWithNS", { count: nsCount })
        );
        if (!proceed) return;
      } else {
        if (!confirm(t("completeConfirm"))) return;
      }
    } catch {
      if (!confirm(t("completeCheckFailed"))) return;
    }
    try {
      await testRunsApi.complete(projectId, selectedRun.id);
      toast.success(t("completeSuccess"));
      loadRuns();
      setSelectedRun((prev) =>
        prev ? { ...prev, status: TestRunStatus.COMPLETED } : null
      );
    } catch {
      toast.error(t("completeFailed"));
    }
  };

  const handleCreateRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      toast.error(t("nameRequired"));
      return;
    }
    setCreating(true);
    try {
      const newRun = await testRunsApi.create(projectId, form);
      toast.success(t("createSuccess"));
      setShowModal(false);
      setForm({ name: "", version: "", environment: "", round: 1 });
      loadRuns();
      loadRunDetail(newRun);
    } catch {
      toast.error(t("createFailed"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={styles.wrapper}>
      {/* Left panel: Run list */}
      {!panelCollapsed && (
        <div style={styles.leftPanel}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-color)" }}>
            <h3 style={{ ...styles.panelTitle, borderBottom: "none" }}>{t("runList")}</h3>
            <button
              style={styles.collapseBtn}
              onClick={() => setPanelCollapsed(true)}
              title={t("hidePanel")}
            >
              ◀
            </button>
          </div>
          <div style={styles.runList}>
            {loadingRuns ? (
              <div style={styles.loadingText}>{t("common:loadingData")}</div>
            ) : runs.length === 0 ? (
              <div style={styles.emptyText}>{t("noRuns")}</div>
            ) : (() => {
              const inProgress = runs.filter(r => r.status !== TestRunStatus.COMPLETED);
              const completed = runs.filter(r => r.status === TestRunStatus.COMPLETED);
              const INITIAL_SHOW = 5;
              const visibleCompleted = showAllCompleted ? completed : completed.slice(0, INITIAL_SHOW);
              const hiddenCount = completed.length - INITIAL_SHOW;
              const allVisible = [...inProgress, ...visibleCompleted];

              return <>
                {allVisible.map((run) => (
                  <div
                    key={run.id}
                    style={{
                      ...styles.runItem,
                      ...(selectedRun?.id === run.id ? styles.runItemActive : {}),
                    }}
                    onClick={() => loadRunDetail(run)}
                  >
                    <div style={styles.runName}>{run.name}</div>
                    <div style={styles.runMeta}>
                      R{run.round} | {run.version || "-"}
                    </div>
                    <span
                      style={{
                        ...styles.statusBadge,
                        backgroundColor:
                          run.status === TestRunStatus.COMPLETED ? "rgba(26, 127, 55, 0.15)" : "rgba(37, 99, 235, 0.15)",
                        color:
                          run.status === TestRunStatus.COMPLETED ? "var(--color-pass)" : "#60A5FA",
                      }}
                    >
                      {run.status === TestRunStatus.COMPLETED ? t("completed") : t("inProgress")}
                    </span>
                  </div>
                ))}
                {!showAllCompleted && hiddenCount > 0 && (
                  <div
                    style={{ padding: "8px 12px", textAlign: "center", cursor: "pointer", color: "var(--text-secondary)", fontSize: 12, borderBottom: "1px solid var(--border-color)" }}
                    onClick={() => setShowAllCompleted(true)}
                  >
                    {t("showOlderRuns", { count: hiddenCount })}
                  </div>
                )}
                {showAllCompleted && hiddenCount > 0 && (
                  <div
                    style={{ padding: "8px 12px", textAlign: "center", cursor: "pointer", color: "var(--text-secondary)", fontSize: 12, borderBottom: "1px solid var(--border-color)" }}
                    onClick={() => setShowAllCompleted(false)}
                  >
                    {t("collapseRuns")}
                  </div>
                )}
              </>;
            })()}
          </div>
          {canManageRun && (
            <button style={styles.newRunBtn} onClick={() => setShowModal(true)}>
              {t("newRun")}
            </button>
          )}
        </div>
      )}

      {/* Right panel: Run detail */}
      <div style={styles.rightPanel}>
        {!selectedRun ? (
          <div style={styles.placeholder}>
            {panelCollapsed && (
              <button
                style={{ ...styles.collapseBtn, marginRight: 12 }}
                onClick={() => setPanelCollapsed(false)}
                title={t("showPanel")}
              >
                ▶
              </button>
            )}
            {runs.length === 0 ? (
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 48, marginBottom: 16, opacity: 0.3 }}>📋</div>
                <div style={{ fontSize: 16, color: "var(--text-secondary)", marginBottom: 20 }}>
                  {t("noRuns")}
                </div>
                {canManageRun && (
                  <button
                    style={{
                      padding: "10px 24px",
                      fontSize: 15,
                      fontWeight: 600,
                      backgroundColor: "var(--accent)",
                      color: "#fff",
                      border: "none",
                      borderRadius: 6,
                      cursor: "pointer",
                    }}
                    onClick={() => setShowModal(true)}
                  >
                    {t("newRun")}
                  </button>
                )}
              </div>
            ) : (
              t("selectRun")
            )}
          </div>
        ) : (
          <>
            <div style={styles.runHeader}>
              {panelCollapsed && (
                <button
                  style={{ ...styles.collapseBtn, marginRight: 8 }}
                  onClick={() => setPanelCollapsed(false)}
                  title={t("showPanel")}
                >
                  ▶
                </button>
              )}
              <div>
                <h3 style={styles.runHeaderTitle}>{selectedRun.name}</h3>
                <div style={styles.runHeaderMeta}>
                  {t("version")}: {selectedRun.version || "-"} | {t("environment")}:{" "}
                  {selectedRun.environment || "-"} | {t("round")}: R{selectedRun.round}
                </div>
              </div>
              <div style={styles.runActions}>
                {canDeleteRun && (
                  <button style={styles.btnDanger} onClick={handleDelete}>
                    {t("deleteRun")}
                  </button>
                )}
                {canManageRun && (
                  <button style={styles.btnGhost} onClick={handleClone}>
                    {t("cloneRun")}
                  </button>
                )}
                <button style={styles.btnGhost} onClick={async () => {
                  if (!selectedRun) return;
                  try {
                    const blob = await testRunsApi.exportExcel(projectId, selectedRun.id);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `${selectedRun.name}_results.xlsx`;
                    a.click();
                    URL.revokeObjectURL(url);
                    toast.success(t("excelDownload"));
                  } catch { toast.error(t("excelExportFailed")); }
                }}>
                  Excel
                </button>
                {canManageRun && (selectedRun.status !== TestRunStatus.COMPLETED ? (
                  <button style={styles.btnComplete} onClick={handleComplete}>
                    {t("completeRun")}
                  </button>
                ) : (
                  <button style={{ ...styles.btnComplete, backgroundColor: "#D97706" }} onClick={async () => {
                    if (!confirm(t("reopenConfirm"))) return;
                    try {
                      await testRunsApi.reopen(projectId, selectedRun.id);
                      toast.success(t("reopenSuccess"));
                      loadRuns();
                      setSelectedRun((prev) => prev ? { ...prev, status: TestRunStatus.IN_PROGRESS, completed_at: undefined } : null);
                    } catch {
                      toast.error(t("reopenFailed"));
                    }
                  }}>
                    {t("reopenRun")}
                  </button>
                ))}
              </div>
            </div>

            {/* Toolbar: bulk result + progress + counts */}
            <div style={styles.toolbar}>
              <div style={styles.toolbarLeft}>
                <div style={{ position: "relative" }} ref={bulkMenuRef}>
                  <button
                    style={styles.btnGhost}
                    onClick={() => setBulkMenuOpen((v) => !v)}
                  >
                    {t("bulkResultInput")}
                  </button>
                  {bulkMenuOpen && (
                    <div style={styles.bulkMenu}>
                      {RESULT_OPTIONS.filter((v) => v !== "NS").map((val) => (
                        <button
                          key={val}
                          style={{
                            ...styles.bulkMenuBtn,
                            backgroundColor: resultColors[val]?.bg || "#F8FAFC",
                            color: resultColors[val]?.fg || "#334155",
                          }}
                          onClick={() => { handleBulkResult(val); setBulkMenuOpen(false); }}
                        >
                          {val}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <span style={styles.hintText}>{t("shortcutHint")}</span>
                <button
                  style={{
                    ...styles.timerToggleBtn,
                    ...(timerEnabled ? styles.timerToggleBtnActive : {}),
                  }}
                  onClick={toggleTimer}
                  title={timerEnabled ? t("timerOff") : t("timerOn")}
                >
                  ⏱
                </button>
                {timerEnabled && timerRowId && (
                  <span style={styles.timerBadge}>
                    {timerDisplay || "0:00"}
                    <button style={styles.timerStopBtn} onClick={stopTimer} title={t("timerStop")}>■</button>
                  </span>
                )}
              </div>
              <div style={styles.toolbarRight}>
                <div style={styles.countBadges}>
                  {Object.entries(resultCounts).map(([key, count]) => (
                    <span
                      key={key}
                      style={{
                        ...styles.countBadge,
                        backgroundColor: resultColors[key]?.bg || (key === t("notEntered") ? "rgba(220, 38, 38, 0.1)" : "var(--bg-input)"),
                        color: resultColors[key]?.fg || (key === t("notEntered") ? "var(--color-fail)" : "var(--text-secondary)"),
                      }}
                    >
                      {key} {count}
                    </span>
                  ))}
                </div>
                <span style={styles.progressText}>{t("progressRate", { rate: completionRate })}</span>
              </div>
            </div>

            {/* Progress bar */}
            <div style={styles.progressWrapper}>
              <div style={styles.progressBg}>
                <div
                  style={{
                    ...styles.progressBar,
                    width: `${completionRate}%`,
                  }}
                />
              </div>
            </div>

            {/* Filter bar */}
            <div style={styles.filterBar}>
              <input
                style={styles.filterInput}
                type="text"
                placeholder={t("searchPlaceholder")}
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
              />
              <select style={styles.filterSelect} value={filterResult} onChange={(e) => setFilterResult(e.target.value)}>
                <option value="">{t("resultFilter")}</option>
                {["PASS", "FAIL", "BLOCK", "N/A", t("notEntered")].map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              <select style={styles.filterSelect} value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)}>
                <option value="">{t("categoryFilter")}</option>
                {categoryOptions.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              <select style={styles.filterSelect} value={filterPriority} onChange={(e) => setFilterPriority(e.target.value)}>
                <option value="">{t("priorityFilter")}</option>
                {priorityOptions.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              {(filterText || filterResult || filterCategory || filterPriority) && (
                <button
                  style={styles.filterClearBtn}
                  onClick={clearFilters}
                >
                  {t("common:reset")}
                </button>
              )}
            </div>

            {/* Grid */}
            <div
              className="ag-theme-alpine"
              style={{ height: "calc(100vh - 320px)", width: "100%" }}
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }}
              onDrop={(e) => {
                e.preventDefault();
                const files = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/"));
                if (files.length === 0) { toast.error(t("imageDropOnly")); return; }
                const focused = gridApiRef.current?.getFocusedCell();
                if (!focused) { toast.error(t("selectGridRow")); return; }
                const node = gridApiRef.current?.getDisplayedRowAtIndex(focused.rowIndex);
                const resultId = node?.data?.id;
                if (!resultId) return;
                handleDropUpload(resultId, files);
              }}
            >
              {loadingResults ? (
                <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
                  {t("common:loadingData")}
                </div>
              ) : (
                <AgGridReact
                  rowData={results}
                  columnDefs={columnDefs}
                  defaultColDef={defaultColDef}
                  localeText={gridLocale}
                  rowSelection={{ mode: "multiRow", checkboxes: true, headerCheckbox: true }}
                  onGridReady={(params: GridReadyEvent) => {
                    gridApiRef.current = params.api;
                  }}
                  onCellValueChanged={onCellValueChanged}
                  onCellKeyDown={onCellKeyDown}
                  onCellClicked={onCellClicked}
                  onCellFocused={(e) => {
                    if (e.rowIndex != null) {
                      const node = gridApiRef.current?.getDisplayedRowAtIndex(e.rowIndex);
                      if (node?.data?.id) onRowFocused(node.data.id);
                    }
                  }}
                  context={{ searchKeyword: filterText }}
                  singleClickEdit={true}
                  stopEditingWhenCellsLoseFocus={true}
                  suppressRowClickSelection={true}
                  getRowId={(params) => String(params.data.id)}
                  isExternalFilterPresent={isExternalFilterPresent}
                  doesExternalFilterPass={doesExternalFilterPass}
                />
              )}
            </div>
          </>
        )}
        {/* ── 시트 탭 바 (그리드 하단) ── */}
        {sheets.length >= 1 && !(sheets.length === 1 && sheets[0].name === "기본") && selectedRun && results.length > 0 && (
          <div style={sheetTabStyles.bar}>
            {sheets.map((s) => (
              <div
                key={s.name}
                style={{
                  ...sheetTabStyles.tab,
                  ...(activeSheet === s.name ? sheetTabStyles.tabActive : {}),
                }}
                onClick={() => setActiveSheet(s.name)}
              >
                {s.name}
                <span style={sheetTabStyles.badge}>{s.tc_count}</span>
              </div>
            ))}
            {sheets.length > 1 && (
              <div
                style={{
                  ...sheetTabStyles.tab,
                  ...(activeSheet === null ? sheetTabStyles.tabActive : {}),
                }}
                onClick={() => setActiveSheet(null)}
              >
                {t("common:all")}
                <span style={sheetTabStyles.badge}>{sheets.reduce((a, s) => a + s.tc_count, 0)}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Hidden file input for image upload */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handleFileUpload}
      />

      {/* Image Preview Modal */}
      {previewImage && (
        <div
          style={styles.overlay}
          onClick={() => setPreviewImage(null)}
        >
          <div
            style={{
              backgroundColor: "var(--bg-card)",
              borderRadius: 12,
              padding: 16,
              maxWidth: "90vw",
              maxHeight: "90vh",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              width: "100%",
              marginBottom: 12,
            }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                {previewImage.filename}
              </span>
              <button
                style={{
                  border: "none",
                  background: "none",
                  fontSize: 20,
                  cursor: "pointer",
                  color: "var(--text-secondary)",
                  padding: "0 4px",
                }}
                onClick={() => setPreviewImage(null)}
              >
                ✕
              </button>
            </div>
            <img
              src={previewImage.url}
              alt={previewImage.filename}
              style={{
                maxWidth: "85vw",
                maxHeight: "80vh",
                objectFit: "contain",
                borderRadius: 8,
              }}
              onError={() => toast.error(t("imageDisplayFailed"))}
            />
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showModal && (
        <div style={styles.overlay} onClick={() => setShowModal(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 style={styles.modalTitle}>{t("createTitle")}</h2>
            <form onSubmit={handleCreateRun} style={styles.modalForm}>
              <label style={styles.label}>{t("runName")}</label>
              <input
                style={styles.input}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder={t("runNamePlaceholder")}
                autoFocus
              />
              <label style={styles.label}>{t("version")}</label>
              <input
                style={styles.input}
                value={form.version}
                onChange={(e) => setForm({ ...form, version: e.target.value })}
                placeholder={t("versionPlaceholder")}
              />
              <label style={styles.label}>{t("environment")}</label>
              <input
                style={styles.input}
                value={form.environment}
                onChange={(e) =>
                  setForm({ ...form, environment: e.target.value })
                }
                placeholder={t("environmentPlaceholder")}
              />
              <label style={styles.label}>{t("round")}</label>
              <select
                style={styles.input}
                value={form.round}
                onChange={(e) =>
                  setForm({ ...form, round: Number(e.target.value) })
                }
              >
                <option value={1}>R1</option>
                <option value={2}>R2</option>
                <option value={3}>R3</option>
              </select>
              <div style={styles.modalActions}>
                <button
                  type="button"
                  style={styles.cancelBtn}
                  onClick={() => setShowModal(false)}
                >
                  {t("common:cancel")}
                </button>
                <button
                  type="submit"
                  style={styles.submitBtn}
                  disabled={creating}
                >
                  {creating ? t("common:creating") : t("common:create")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}

const sheetTabStyles: Record<string, React.CSSProperties> = {
  bar: {
    display: "flex", alignItems: "center", gap: 2,
    padding: "6px 12px", backgroundColor: "var(--bg-card)",
    borderTop: "1px solid var(--border-color)", overflowX: "auto",
  },
  tab: {
    display: "inline-flex", alignItems: "center", gap: 6,
    padding: "5px 14px", fontSize: 12, fontWeight: 500,
    color: "var(--text-secondary)", backgroundColor: "transparent",
    border: "1px solid var(--border-color)", borderBottom: "none",
    borderRadius: "6px 6px 0 0", cursor: "pointer",
    whiteSpace: "nowrap", transition: "all 0.15s",
  },
  tabActive: {
    color: "#fff", backgroundColor: "var(--accent)",
    borderColor: "var(--accent)", fontWeight: 700,
  },
  badge: {
    fontSize: 10, fontWeight: 600, padding: "1px 6px",
    borderRadius: 8, backgroundColor: "rgba(255,255,255,0.2)",
  },
};

const styles: Record<string, React.CSSProperties> = {
  wrapper: { display: "flex", gap: 12, height: "calc(100vh - 160px)" },
  leftPanel: {
    width: 240,
    minWidth: 240,
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    border: "1px solid var(--border-color)",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  panelTitle: {
    padding: "12px 14px 10px",
    margin: 0,
    fontSize: 13,
    fontWeight: 700,
    color: "var(--text-primary)",
    borderBottom: "1px solid var(--border-color)",
  },
  runList: { flex: 1, overflow: "auto", padding: "8px" },
  loadingText: { textAlign: "center", color: "var(--text-secondary)", padding: 20, fontSize: 14 },
  emptyText: { textAlign: "center", color: "var(--text-secondary)", padding: 20, fontSize: 14 },
  runItem: {
    padding: "10px",
    borderRadius: 6,
    cursor: "pointer",
    marginBottom: 4,
    transition: "background-color 0.1s",
    position: "relative" as const,
  },
  runItemActive: {
    backgroundColor: "var(--bg-input)",
    border: "1px solid var(--accent)",
  },
  runName: {
    fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 2,
    paddingRight: 56, overflow: "hidden" as const, textOverflow: "ellipsis" as const, whiteSpace: "nowrap" as const,
  },
  runMeta: { fontSize: 11, color: "var(--text-secondary)", paddingRight: 56 },
  statusBadge: {
    position: "absolute" as const,
    top: 10,
    right: 10,
    fontSize: 11,
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: 4,
  },
  collapseBtn: {
    border: "1px solid var(--border-input)",
    borderRadius: 4,
    backgroundColor: "var(--bg-input)",
    color: "var(--text-secondary)",
    fontSize: 12,
    cursor: "pointer",
    padding: "2px 8px",
    lineHeight: "22px",
    flexShrink: 0,
  },
  newRunBtn: {
    margin: 8,
    padding: "8px 0",
    borderRadius: 6,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
  rightPanel: { flex: 1, minWidth: 0 },
  placeholder: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    height: "100%",
    color: "#94A3B8",
    fontSize: 14,
  },
  runHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  runHeaderTitle: { margin: "0 0 2px", fontSize: 15, fontWeight: 700, color: "var(--text-primary)" },
  runHeaderMeta: { fontSize: 12, color: "var(--text-secondary)" },
  runActions: { display: "flex", gap: 8 },
  btnDanger: {
    padding: "5px 14px",
    borderRadius: 5,
    border: "1px solid rgba(220, 38, 38, 0.3)",
    backgroundColor: "rgba(220, 38, 38, 0.1)",
    color: "var(--color-fail)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnComplete: {
    padding: "5px 14px",
    borderRadius: 5,
    border: "1px solid #3B82F6",
    backgroundColor: "#2563EB",
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 6,
    gap: 8,
  },
  toolbarLeft: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  toolbarRight: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  btnGhost: {
    padding: "4px 12px",
    borderRadius: 5,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
  },
  bulkMenu: {
    position: "absolute" as const,
    top: "100%",
    left: 0,
    marginTop: 4,
    backgroundColor: "var(--bg-card)",
    border: "1px solid var(--border-color)",
    borderRadius: 8,
    boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
    padding: 6,
    zIndex: 100,
    display: "flex",
    gap: 4,
  },
  bulkMenuBtn: {
    padding: "4px 14px",
    borderRadius: 4,
    border: "1px solid var(--border-color)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  hintText: {
    fontSize: 11,
    color: "#94A3B8",
  },
  timerToggleBtn: {
    padding: "2px 8px",
    borderRadius: 5,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-input)",
    fontSize: 14,
    cursor: "pointer",
    lineHeight: 1,
    opacity: 0.5,
  },
  timerToggleBtnActive: {
    opacity: 1,
    borderColor: "var(--color-block)",
    backgroundColor: "rgba(234, 179, 8, 0.15)",
  },
  timerBadge: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "2px 10px",
    borderRadius: 5,
    backgroundColor: "rgba(234, 179, 8, 0.15)",
    color: "var(--text-warning)",
    fontSize: 12,
    fontWeight: 700,
    fontVariantNumeric: "tabular-nums" as const,
  },
  timerStopBtn: {
    border: "none",
    background: "none",
    color: "#DC2626",
    fontSize: 10,
    cursor: "pointer",
    padding: "0 2px",
    lineHeight: 1,
  },
  countBadges: {
    display: "flex",
    gap: 4,
  },
  countBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
  },
  progressText: {
    fontSize: 12,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  filterBar: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    marginBottom: 12,
    paddingBottom: 4,
    flexWrap: "wrap" as const,
    overflow: "visible" as const,
  },
  filterInput: {
    padding: "5px 10px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 12,
    width: 220,
    outline: "none",
    fontFamily: "inherit",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  filterSelect: {
    padding: "5px 8px",
    borderRadius: 6,
    border: "1px solid var(--border-input)",
    fontSize: 12,
    height: 30,
    outline: "none",
    fontFamily: "inherit",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
    cursor: "pointer",
  },
  filterClearBtn: {
    padding: "4px 10px",
    borderRadius: 5,
    border: "1px solid rgba(220, 38, 38, 0.3)",
    backgroundColor: "rgba(220, 38, 38, 0.1)",
    color: "var(--color-fail)",
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
  },
  progressWrapper: { marginBottom: 6 },
  progressBg: {
    height: 8,
    backgroundColor: "var(--border-color)",
    borderRadius: 4,
    overflow: "hidden",
  },
  progressBar: {
    height: "100%",
    backgroundColor: "var(--accent)",
    borderRadius: 4,
    transition: "width 0.3s",
  },
  overlay: {
    position: "fixed" as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.5)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 200,
  },
  modal: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    padding: 32,
    width: 460,
    maxWidth: "90vw",
    boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
  },
  modalTitle: { margin: "0 0 24px", fontSize: 20, fontWeight: 700, color: "var(--text-primary)" },
  modalForm: { display: "flex", flexDirection: "column" as const, gap: 8 },
  label: { fontSize: 14, fontWeight: 600, color: "var(--text-secondary)", marginTop: 8 },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    fontSize: 14,
    outline: "none",
    fontFamily: "inherit",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
  modalActions: { display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 20 },
  cancelBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    fontSize: 14,
    cursor: "pointer",
  },
  submitBtn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
};
