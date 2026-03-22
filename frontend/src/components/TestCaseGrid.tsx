import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  ModuleRegistry,
  type ColDef,
  type CellClassParams,
  type CellStyle,
  type GridReadyEvent,
  type GridApi,
  type CellValueChangedEvent,
  type CellKeyDownEvent,
} from "ag-grid-community";
import { testCasesApi, historyApi, customFieldsApi, filtersApi } from "../api";
import type { TestCase, TestCaseHistory, Project, SheetNode, CustomFieldDef, FilterCondition } from "../types";
import { AG_GRID_LOCALE_KO } from "../agGridLocaleKo";
import toast from "react-hot-toast";
import MarkdownCell from "./MarkdownCell";
import HighlightCell from "./HighlightCell";

ModuleRegistry.registerModules([AllCommunityModule]);

interface Props {
  projectId: number;
  project: Project;
  highlightTcId?: string;
}

const TYPE_OPTIONS = ["Func.", "UI/UX", "Perf.", "Security", "API", "Data"];
const PRIORITY_OPTIONS = ["매우 높음", "높음", "보통", "낮음", "매우 낮음"];
const PLATFORM_OPTIONS = ["Web", "Mobile Web", "Mobile App", "iOS", "Android", "PC", "API", "공통"];

const priorityColors: Record<string, string> = {
  "매우 높음": "#DC2626",
  "높음": "#EA580C",
  "보통": "#2563EB",
  "낮음": "#16A34A",
  "매우 낮음": "#6B7280",
};

function priorityCellStyle(params: CellClassParams): CellStyle {
  const val = params.value as string;
  const color = priorityColors[val];
  if (color) return { color, fontWeight: 600 };
  return {};
}

// ── Undo/Redo 타입 ──
interface UndoEntry {
  rowId: string;
  field: string;
  oldValue: unknown;
  newValue: unknown;
  dataId: number;
}
type UndoGroup = UndoEntry[];

// TODO: 접근성(#13) — 주요 버튼에 aria-label 추가, 키보드 네비게이션 개선 필요
export default function TestCaseGrid({ projectId, project, highlightTcId }: Props) {
  const canEditTC = project.my_role === "admin";
  const gridRef = useRef<AgGridReact>(null);
  const [rowData, setRowData] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const emptyFileInputRef = useRef<HTMLInputElement>(null);
  const gridApiRef = useRef<GridApi | null>(null);

  // ── 시트 탭 (트리 구조) ──
  const [sheets, setSheets] = useState<SheetNode[]>([]);
  const [activeSheet, setActiveSheet] = useState<string | null>(null);
  const sheetInitialized = useRef(false);
  const [expandedSheets, setExpandedSheets] = useState<Set<number>>(new Set());

  // ── 커스텀 필드 ──
  const [customFields, setCustomFields] = useState<CustomFieldDef[]>([]);

  // ── 사이드바 접기/펼치기 ──
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // ── 고급 필터 ──
  const [filterConditions, setFilterConditions] = useState<FilterCondition[]>([]);
  const [filterLogic, setFilterLogic] = useState<"AND" | "OR">("AND");
  const [showFilterPanel, setShowFilterPanel] = useState(false);
  const [activeFilterName, setActiveFilterName] = useState<string | null>(null);

  // 트리를 flat 리스트로 펼치기 (시트 순서, tc_count 합산 등에 사용)
  const flatSheets = useMemo(() => {
    const result: { name: string; tc_count: number; id: number; depth: number; parent_id: number | null; hasChildren: boolean; is_folder: boolean }[] = [];
    const walk = (nodes: SheetNode[], depth: number) => {
      for (const n of nodes) {
        const kids = n.children || [];
        result.push({ name: n.name, tc_count: n.tc_count, id: n.id, depth, parent_id: n.parent_id, hasChildren: kids.length > 0, is_folder: n.is_folder });
        if (kids.length > 0) walk(kids, depth + 1);
      }
    };
    walk(sheets, 0);
    return result;
  }, [sheets]);

  // ── Undo/Redo 스택 ──
  const undoStackRef = useRef<UndoGroup[]>([]);
  const redoStackRef = useRef<UndoGroup[]>([]);
  const isUndoRedoRef = useRef(false);
  const [undoCount, setUndoCount] = useState(0);
  const [redoCount, setRedoCount] = useState(0);
  const autoSaveRowRef = useRef<(data: TestCase) => void>(() => {});

  const pushUndo = useCallback((group: UndoGroup) => {
    if (group.length === 0) return;
    undoStackRef.current.push(group);
    if (undoStackRef.current.length > 200) undoStackRef.current.shift();
    redoStackRef.current = [];
    setUndoCount(undoStackRef.current.length);
    setRedoCount(0);
  }, []);

  const applyUndoRedo = useCallback((entries: UndoGroup, direction: "undo" | "redo") => {
    const api = gridApiRef.current;
    if (!api) return;
    isUndoRedoRef.current = true;

    const reverseGroup: UndoGroup = [];
    const updatedNodes: Set<string> = new Set();

    for (const entry of entries) {
      const value = direction === "undo" ? entry.oldValue : entry.newValue;
      const reverseValue = direction === "undo" ? entry.newValue : entry.oldValue;
      api.forEachNode((node) => {
        const nodeRowId = node.data?.id ? String(node.data.id) : `new_${node.data?.no}`;
        if (nodeRowId === entry.rowId && node.data) {
          node.data[entry.field] = value;
          updatedNodes.add(nodeRowId);
          if (node.data.id) {

          }
        }
      });
      reverseGroup.push({ ...entry, oldValue: reverseValue, newValue: value });
    }

    if (direction === "undo") {
      redoStackRef.current.push(reverseGroup.map(e => ({
        ...e, oldValue: e.newValue, newValue: e.oldValue,
      })));
    } else {
      undoStackRef.current.push(reverseGroup.map(e => ({
        ...e, oldValue: e.newValue, newValue: e.oldValue,
      })));
    }

    // 변경된 행 자동 저장
    api.forEachNode((node) => {
      const nodeRowId = node.data?.id ? String(node.data.id) : `new_${node.data?.no}`;
      if (updatedNodes.has(nodeRowId) && node.data) {
        autoSaveRowRef.current(node.data);
      }
    });

    api.refreshCells({ force: true });
    isUndoRedoRef.current = false;
    setUndoCount(undoStackRef.current.length);
    setRedoCount(redoStackRef.current.length);
  }, []);

  const handleUndo = useCallback(() => {
    const group = undoStackRef.current.pop();
    if (!group) return;
    applyUndoRedo(group, "undo");
  }, [applyUndoRedo]);

  const handleRedo = useCallback(() => {
    const group = redoStackRef.current.pop();
    if (!group) return;
    applyUndoRedo(group, "redo");
  }, [applyUndoRedo]);

  // ── 찾기/바꾸기 ──
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [replaceText, setReplaceText] = useState("");

  const handleReplaceAll = () => {
    if (!searchText) return;
    const api = gridApiRef.current;
    if (!api) return;

    const textFields = ["tc_id", "type", "category", "depth1", "depth2", "precondition", "test_steps", "expected_result", "remarks", "assignee", "issue_link"];
    let count = 0;
    const re = new RegExp(searchText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
    const undoGroup: UndoGroup = [];
    const changedRows: TestCase[] = [];

    api.forEachNode((node) => {
      if (!node.data) return;
      const rowId = node.data.id ? String(node.data.id) : `new_${node.data.no}`;
      let changed = false;
      for (const field of textFields) {
        const val = node.data[field];
        if (typeof val === "string" && re.test(val)) {
          const newVal = val.replace(re, replaceText);
          undoGroup.push({ rowId, field, oldValue: val, newValue: newVal, dataId: node.data.id || 0 });
          node.data[field] = newVal;
          count++;
          changed = true;
        }
        re.lastIndex = 0;
      }
      if (changed) changedRows.push(node.data);
    });

    if (count > 0) {
      pushUndo(undoGroup);
      api.refreshCells({ force: true });
      changedRows.forEach((r) => autoSaveRow(r));
      toast.success(`${count}건 치환 완료`);
    } else {
      toast("일치하는 항목이 없습니다.");
    }
  };

  // ── 일괄 변경 ──
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkField, setBulkField] = useState("priority");
  const [bulkValue, setBulkValue] = useState("");

  const BULK_FIELDS: { field: string; label: string; options?: string[] }[] = [
    { field: "type", label: "Type", options: TYPE_OPTIONS },
    { field: "category", label: "Category" },
    { field: "depth1", label: "Depth 1" },
    { field: "depth2", label: "Depth 2" },
    { field: "priority", label: "Priority", options: PRIORITY_OPTIONS },
    { field: "test_type", label: "Platform", options: PLATFORM_OPTIONS },
    { field: "assignee", label: "Assignee" },
    { field: "remarks", label: "Remarks" },
  ];

  const handleBulkApply = () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows() as TestCase[];
    if (selected.length === 0) return;

    const undoGroup: UndoGroup = [];
    selected.forEach((row) => {
      const rowId = row.id ? String(row.id) : `new_${row.no}`;
      const oldVal = (row as unknown as Record<string, unknown>)[bulkField];
      undoGroup.push({ rowId, field: bulkField, oldValue: oldVal, newValue: bulkValue, dataId: row.id || 0 });
      (row as unknown as Record<string, unknown>)[bulkField] = bulkValue;
    });
    pushUndo(undoGroup);
    api.applyTransaction({ update: selected });
    api.refreshCells({ force: true });
    selected.forEach((r) => autoSaveRow(r));
    setBulkOpen(false);
    toast.success(`${selected.length}개 행의 ${BULK_FIELDS.find(f => f.field === bulkField)?.label} 변경 완료`);
  };

  // ── 히스토리 패널 ──
  const [historyTc, setHistoryTc] = useState<TestCase | null>(null);
  const [historyMode, setHistoryMode] = useState<"tc" | "project">("tc");
  const [historyData, setHistoryData] = useState<TestCaseHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const openHistory = useCallback(async (tc: TestCase) => {
    if (!tc.id) return;
    setHistoryTc(tc);
    setHistoryMode("tc");
    setHistoryLoading(true);
    try {
      const data = await historyApi.getTestCaseHistory(tc.id);
      setHistoryData(data);
    } catch (err) {
      console.error(err);
      toast.error("변경 이력을 불러오지 못했습니다.");
      setHistoryData([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const openProjectHistory = useCallback(async () => {
    setHistoryTc({ id: -1 } as TestCase); // sentinel to open modal
    setHistoryMode("project");
    setHistoryLoading(true);
    try {
      const data = await historyApi.getProjectHistory(projectId);
      setHistoryData(data);
    } catch (err) {
      console.error(err);
      toast.error("변경 이력을 불러오지 못했습니다.");
      setHistoryData([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [projectId]);

  const loadSheets = useCallback(async () => {
    try {
      const s = await testCasesApi.listSheets(projectId);
      setSheets(s);
      // 최초 로딩 시에만 첫 시트 자동 선택
      const flatAll: SheetNode[] = [];
      const collectFlat = (nodes: SheetNode[]) => { for (const n of nodes) { flatAll.push(n); collectFlat(n.children); } };
      collectFlat(s);
      if (flatAll.length > 1 && !sheetInitialized.current) {
        sheetInitialized.current = true;
        setActiveSheet(s[0].name);
      }
    } catch {
      // 시트 API 실패 시 무시 (기존 호환)
    }
  }, [projectId]);

  const loadCustomFields = useCallback(async () => {
    try {
      const fields = await customFieldsApi.list(projectId);
      setCustomFields(fields);
    } catch {
      // 커스텀 필드 API 실패 시 무시
    }
  }, [projectId]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (activeSheet) params.sheet_name = activeSheet;
      const data = await testCasesApi.list(projectId, params);

      // 전체 보기: 시트 순서대로 연속 번호 부여
      if (!activeSheet && flatSheets.length > 1) {
        const sheetOrder = flatSheets.map((s) => s.name);
        const grouped = new Map<string, typeof data>();
        for (const tc of data) {
          const sn = tc.sheet_name || "기본";
          if (!grouped.has(sn)) grouped.set(sn, []);
          grouped.get(sn)!.push(tc);
        }
        const sorted: typeof data = [];
        for (const name of sheetOrder) {
          const tcs = grouped.get(name);
          if (tcs) sorted.push(...tcs.sort((a, b) => a.no - b.no));
        }
        // 시트 순서에 없는 나머지
        for (const [name, tcs] of grouped) {
          if (!sheetOrder.includes(name)) sorted.push(...tcs.sort((a, b) => a.no - b.no));
        }
        let seq = 1;
        for (const tc of sorted) {
          tc.no = seq++;
        }
        setRowData(sorted);
      } else {
        setRowData(data);
      }
      undoStackRef.current = [];
      redoStackRef.current = [];
      setUndoCount(0);
      setRedoCount(0);
    } catch (err) {
      console.error(err);
      toast.error("테스트 케이스를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [projectId, activeSheet, flatSheets]);

  useEffect(() => {
    loadSheets();
    loadCustomFields();
  }, [loadSheets, loadCustomFields]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // ── Ctrl+Z / Ctrl+Y 글로벌 키보드 단축키 ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      // 셀 편집 중이면 브라우저 기본 undo/redo 사용
      const active = document.activeElement;
      if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) return;

      if (e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        handleUndo();
      } else if (e.key === "y" || (e.key === "z" && e.shiftKey)) {
        e.preventDefault();
        handleRedo();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [handleUndo, handleRedo]);

  const columnDefs = useMemo<ColDef[]>(
    () => [
      { field: "no", headerName: "No", width: 55, editable: canEditTC, type: "numericColumn", wrapText: false, autoHeight: false },
      { field: "tc_id", headerName: "TC ID", width: 110, editable: canEditTC, cellRenderer: HighlightCell },
      {
        field: "type",
        headerName: "Type",
        width: 80,
        editable: canEditTC,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: TYPE_OPTIONS },
        cellRenderer: HighlightCell,
      },
      { field: "category", headerName: "Category", width: 140, editable: canEditTC, wrapText: true, autoHeight: true, cellRenderer: HighlightCell },
      { field: "depth1", headerName: "Depth 1", width: 150, editable: canEditTC, wrapText: true, autoHeight: true, cellRenderer: HighlightCell },
      { field: "depth2", headerName: "Depth 2", width: 150, editable: canEditTC, wrapText: true, autoHeight: true, cellRenderer: HighlightCell },
      {
        field: "priority",
        headerName: "Priority",
        width: 90,
        editable: canEditTC,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: PRIORITY_OPTIONS },
        cellStyle: priorityCellStyle,
      },
      {
        field: "test_type",
        headerName: "Platform",
        width: 85,
        editable: canEditTC,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: PLATFORM_OPTIONS },
      },
      {
        field: "precondition",
        headerName: "Precondition",
        width: 200,
        editable: canEditTC,
        wrapText: true,
        autoHeight: true,
        cellEditor: "agLargeTextCellEditor",
        cellEditorPopup: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
      },
      {
        field: "test_steps",
        headerName: "Test Steps",
        width: 300,
        editable: canEditTC,
        wrapText: true,
        autoHeight: true,
        cellEditor: "agLargeTextCellEditor",
        cellEditorPopup: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
      },
      {
        field: "expected_result",
        headerName: "Expected Result",
        width: 260,
        editable: canEditTC,
        wrapText: true,
        autoHeight: true,
        cellEditor: "agLargeTextCellEditor",
        cellEditorPopup: true,
        cellClass: "ag-cell-left",
        cellRenderer: MarkdownCell,
      },
      { field: "remarks", headerName: "Remarks", minWidth: 180, flex: 1, editable: canEditTC, wrapText: true, autoHeight: true, cellClass: "ag-cell-left", cellRenderer: MarkdownCell },
      // 커스텀 필드 동적 컬럼
      ...customFields.map((cf): ColDef => {
        const base: ColDef = {
          field: `cf_${cf.field_name}`,
          headerName: cf.field_name,
          width: 120,
          editable: canEditTC,
          valueGetter: (params) => {
            return params.data?.custom_fields?.[cf.field_name] ?? "";
          },
          valueSetter: (params) => {
            if (!params.data.custom_fields) params.data.custom_fields = {};
            params.data.custom_fields[cf.field_name] = params.newValue;
            return true;
          },
        };
        if (cf.field_type === "select" && cf.options) {
          base.cellEditor = "agSelectCellEditor";
          base.cellEditorParams = { values: cf.options };
        } else if (cf.field_type === "number") {
          base.type = "numericColumn";
        } else if (cf.field_type === "checkbox") {
          base.cellRenderer = "agCheckboxCellRenderer";
          base.cellEditor = "agCheckboxCellEditor";
        }
        return base;
      }),
    ],
    [canEditTC, customFields]
  );

  const defaultColDef = useMemo<ColDef>(
    () => ({
      resizable: true,
      sortable: true,
      filter: true,
      wrapText: true,
      autoHeight: true,
    }),
    []
  );

  const onGridReady = useCallback((params: GridReadyEvent) => {
    gridApiRef.current = params.api;
    if (highlightTcId) {
      setTimeout(() => {
        params.api.forEachNode((node) => {
          if (node.data?.tc_id === highlightTcId) {
            node.setSelected(true);
            params.api.ensureNodeVisible(node, "middle");
          }
        });
      }, 300);
    }
  }, [highlightTcId]);

  // ── 자동 저장 (디바운스) ──
  const autoSaveTimerRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const autoSaveRow = useCallback(async (data: TestCase) => {
    if (!data.id || data.id === 0) return; // 미저장 행은 무시
    const key = String(data.id);
    if (autoSaveTimerRef.current[key]) clearTimeout(autoSaveTimerRef.current[key]);
    autoSaveTimerRef.current[key] = setTimeout(async () => {
      try {
        await testCasesApi.update(projectId, data.id, data);
      } catch {
        toast.error("자동 저장 실패");
      }
      delete autoSaveTimerRef.current[key];
    }, 300);
  }, [projectId]);
  autoSaveRowRef.current = autoSaveRow;

  const onCellValueChanged = useCallback(
    (event: CellValueChangedEvent) => {
      const data = event.data as TestCase;

      // undo/redo 적용 중이면 스택에 추가하지 않음
      if (!isUndoRedoRef.current) {
        const field = event.column?.getColId();
        if (field) {
          const rowId = data.id ? String(data.id) : `new_${data.no}`;
          pushUndo([{
            rowId,
            field,
            oldValue: event.oldValue,
            newValue: event.newValue,
            dataId: data.id || 0,
          }]);
        }
      }

      // 자동 저장
      autoSaveRow(data);
    },
    [pushUndo, autoSaveRow]
  );

  const handleAddRow = async () => {
    const nextNo = rowData.length > 0 ? Math.max(...rowData.map((r) => r.no || 0)) + 1 : 1;
    const newRow: Partial<TestCase> = {
      no: nextNo,
      tc_id: `TC-${String(nextNo).padStart(3, "0")}`,
      type: "",
      category: "",
      depth1: "",
      depth2: "",
      priority: "보통",
      test_type: "Web",
      precondition: "",
      test_steps: "",
      expected_result: "",
      remarks: "",
      sheet_name: activeSheet || "기본",
    };
    try {
      const created = await testCasesApi.create(projectId, newRow as TestCase);
      setRowData((prev) => [...prev, created]);
      // 생성된 행으로 스크롤
      setTimeout(() => {
        const api = gridApiRef.current;
        if (api) {
          api.forEachNode((node) => {
            if (node.data?.id === created.id) {
              node.setSelected(true);
              api.ensureNodeVisible(node, "bottom");
            }
          });
        }
      }, 100);
    } catch {
      toast.error("행 추가에 실패했습니다.");
    }
  };

  const handleAutoFillTcId = () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows() as TestCase[];
    if (selected.length === 0) {
      toast.error("TC ID를 채울 행을 선택해 주세요.");
      return;
    }

    // Get all rows in display order
    const allRows: TestCase[] = [];
    api.forEachNodeAfterFilterAndSort((node) => {
      if (node.data) allRows.push(node.data);
    });

    const selectedSet = new Set(selected.map((r) => r.id || r.no));

    // Find selected rows' indices
    const selectedIndices = allRows
      .map((r, i) => (selectedSet.has(r.id || r.no) ? i : -1))
      .filter((i) => i >= 0)
      .sort((a, b) => a - b);

    if (selectedIndices.length === 0) return;

    // Collect all existing TC IDs to find max number per prefix
    const prefixMax = new Map<string, number>();
    for (const row of allRows) {
      if (!row.tc_id) continue;
      const match = row.tc_id.match(/^(.+-)(\d+)$/);
      if (match) {
        const prefix = match[1];
        const num = parseInt(match[2], 10);
        prefixMax.set(prefix, Math.max(prefixMax.get(prefix) || 0, num));
      }
    }

    // For each selected row: if it has a tc_id with pattern "PREFIX-NNN",
    // use that as starting point. Then fill subsequent selected rows.
    let currentPrefix = "";
    let currentNum = 0;
    let numWidth = 3;
    const changedRows: TestCase[] = [];

    for (const idx of selectedIndices) {
      const row = allRows[idx];
      if (row.tc_id) {
        const match = row.tc_id.match(/^(.+-)(\d+)$/);
        if (match) {
          currentPrefix = match[1];
          currentNum = parseInt(match[2], 10);
          numWidth = match[2].length;
          prefixMax.set(currentPrefix, Math.max(prefixMax.get(currentPrefix) || 0, currentNum));
          continue;
        }
      }
      if (!currentPrefix) continue;
      currentNum++;
      prefixMax.set(currentPrefix, currentNum);
      row.tc_id = currentPrefix + String(currentNum).padStart(numWidth, "0");
      changedRows.push(row);
    }

    api.applyTransaction({ update: allRows.filter((_, i) => selectedIndices.includes(i)) });
    api.refreshCells({ force: true });
    changedRows.forEach((r) => autoSaveRow(r));
    toast.success("TC ID 자동 채우기 완료");
  };

  const handleDeleteSelected = async () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows() as TestCase[];
    if (selected.length === 0) {
      toast.error("삭제할 행을 선택해 주세요.");
      return;
    }

    // 저장되지 않은 신규 행은 그냥 제거
    const unsaved = selected.filter((r) => !r.id || r.id === 0);
    const saved = selected.filter((r) => r.id && r.id !== 0);

    if (unsaved.length > 0) {
      setRowData((prev) => prev.filter((r) => !unsaved.includes(r)));
    }

    if (saved.length === 0) {
      toast.success(`${unsaved.length}개 행이 제거되었습니다.`);
      return;
    }

    try {
      const deletedIds = saved.map((r) => r.id);
      await testCasesApi.bulkDelete(projectId, deletedIds);
      // 그리드에서 즉시 제거
      setRowData((prev) => prev.filter((r) => !saved.some((s) => s.id === r.id)));
      toast(
        (t) => (
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {saved.length}개 TC 삭제됨
            <button
              onClick={async () => {
                toast.dismiss(t.id);
                try {
                  for (const id of deletedIds) {
                    await testCasesApi.restore(projectId, id);
                  }
                  toast.success("삭제가 취소되었습니다.");
                  loadData();
                } catch (err) {
                  console.error(err);
                  toast.error("되돌리기에 실패했습니다.");
                }
              }}
              style={{
                padding: "4px 12px",
                borderRadius: 4,
                border: "none",
                backgroundColor: "var(--accent)",
                color: "#fff",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              되돌리기
            </button>
          </span>
        ),
        { duration: 7000 }
      );
    } catch (err) {
      console.error(err);
      toast.error("삭제에 실패했습니다.");
      loadData();
    }
  };


  // ── Excel Import: 시트 선택 ──
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importSheets, setImportSheets] = useState<{ name: string; tc_count: number; existing: number }[]>([]);
  const [selectedSheets, setSelectedSheets] = useState<Set<string>>(new Set());
  const [importLoading, setImportLoading] = useState(false);

  // ── 시트/폴더 추가 ──
  const [showAddSheet, setShowAddSheet] = useState(false);
  const [newSheetName, setNewSheetName] = useState("");
  const [addSheetParentId, setAddSheetParentId] = useState<number | null>(null);
  const [addingFolder, setAddingFolder] = useState(false);

  const handleAddSheet = async () => {
    const name = newSheetName.trim();
    const label = addingFolder ? "폴더" : "시트";
    if (!name) { toast.error(`${label} 이름을 입력해 주세요.`); return; }
    try {
      await testCasesApi.createSheet(projectId, name, addSheetParentId, addingFolder);
      setShowAddSheet(false);
      setNewSheetName("");
      setAddSheetParentId(null);
      setAddingFolder(false);
      if (!addingFolder) setActiveSheet(name);
      // 부모가 있으면 자동 펼침
      if (addSheetParentId) {
        setExpandedSheets(prev => new Set([...prev, addSheetParentId!]));
      }
      loadSheets();
      toast.success(`"${name}" ${label}가 추가되었습니다.`);
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || `${label} 추가에 실패했습니다.`;
      toast.error(msg);
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (emptyFileInputRef.current) emptyFileInputRef.current.value = "";

    try {
      toast("파일 분석 중...", { duration: 1500 });
      const preview = await testCasesApi.previewImport(projectId, file);
      if (preview.sheets.length === 0) {
        toast.error("유효한 시트를 찾을 수 없습니다.");
        return;
      }
      if (preview.sheets.length === 1) {
        const sheet = preview.sheets[0];
        // 기존 TC가 있으면 덮어쓰기 확인
        if (sheet.existing > 0) {
          if (!confirm(`"${sheet.name}" 시트에 이미 ${sheet.existing}개의 TC가 있습니다.\n동일한 TC ID는 덮어쓰기됩니다. 계속하시겠습니까?`)) return;
        }
        toast("가져오는 중...", { duration: 2000 });
        const result = await testCasesApi.importExcel(projectId, file, [sheet.name]);
        const created = result.created ?? 0;
        const updated = result.updated ?? 0;
        const imported = result.imported ?? created + updated;
        const msg = updated > 0
          ? `신규 ${created}개, 업데이트 ${updated}개`
          : `${imported}개 가져옴`;
        toast.success(msg);
        setActiveSheet(sheet.name);
        // 시트 목록 + 데이터 갱신 (빈 프로젝트에서 import 시 화면 전환 보장)
        const newSheets = await testCasesApi.listSheets(projectId);
        setSheets(newSheets);
        loadData();
        return;
      }
      // 시트가 2개 이상이면 선택 모달 표시
      setImportFile(file);
      setImportSheets(preview.sheets);
      setSelectedSheets(new Set(preview.sheets.map((s) => s.name)));
    } catch (err) {
      console.error("Import error:", err);
      const errMsg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Excel/CSV 파일을 읽을 수 없습니다.";
      toast.error(errMsg);
    }
  };

  const handleImportConfirm = async () => {
    if (!importFile || selectedSheets.size === 0) return;
    // 중복 시트 확인
    const overlapping = importSheets.filter((s) => selectedSheets.has(s.name) && s.existing > 0);
    if (overlapping.length > 0) {
      const msg = overlapping.map((s) => `${s.name}: 기존 ${s.existing}개`).join("\n");
      if (!confirm(`다음 시트에 이미 TC가 있습니다.\n\n${msg}\n\n동일한 TC ID는 덮어쓰기됩니다. 계속하시겠습니까?`)) return;
    }
    setImportLoading(true);
    try {
      const result = await testCasesApi.importExcel(projectId, importFile, Array.from(selectedSheets));
      const details = result.sheets.map((s: { sheet: string; created: number; updated: number }) => {
        if (s.updated > 0) return `${s.sheet}: 신규 ${s.created}, 업데이트 ${s.updated}`;
        return `${s.sheet}: ${s.created}개`;
      }).join(", ");
      toast.success(details);
      const firstImported = result.sheets.find((s: { created: number; updated: number }) => s.created + s.updated > 0);
      if (firstImported) setActiveSheet((firstImported as { sheet: string }).sheet);
      loadSheets();
      setImportFile(null);
      setImportSheets([]);
    } catch (err) {
      console.error(err);
      toast.error("Excel 가져오기에 실패했습니다.");
    } finally {
      setImportLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await testCasesApi.exportExcel(projectId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `testcases_${projectId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Excel 파일이 다운로드됩니다.");
    } catch (err) {
      console.error(err);
      toast.error("Excel 내보내기에 실패했습니다.");
    }
  };

  const onSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchText(e.target.value);
    gridApiRef.current?.setGridOption("quickFilterText", e.target.value);
  }, []);

  // ── Ctrl+D: 현재 셀 값을 아래 선택된 행에 채우기 ──
  const onCellKeyDown = useCallback((event: CellKeyDownEvent) => {
    const e = event.event as KeyboardEvent;
    if (!e) return;
    if (e.key === "d" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      const api = gridApiRef.current;
      if (!api || !event.column) return;
      const field = event.column.getColId();
      const sourceValue = event.value;
      const selectedNodes = api.getSelectedNodes();
      if (selectedNodes.length === 0) return;

      let filled = 0;
      const undoGroup: UndoGroup = [];
      selectedNodes.forEach((node) => {
        if (node.data && node !== event.node) {
          const rowId = node.data.id ? String(node.data.id) : `new_${node.data.no}`;
          undoGroup.push({ rowId, field, oldValue: node.data[field], newValue: sourceValue, dataId: node.data.id || 0 });
          node.data[field] = sourceValue;
          filled++;
          if (node.data.id) {

          }
        }
      });
      if (filled > 0) {
        pushUndo(undoGroup);
        api.refreshCells({ force: true });
        selectedNodes.forEach((node) => {
          if (node.data && node !== event.node) autoSaveRow(node.data);
        });
        toast.success(`${filled}개 행에 "${sourceValue}" 채움`);
      }
    }
  }, [pushUndo, autoSaveRow]);

  // ── TC 복사 ──
  const handleCopySelected = () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows() as TestCase[];
    if (selected.length === 0) {
      toast.error("복사할 행을 선택해 주세요.");
      return;
    }
    const maxNo = Math.max(...rowData.map((r) => r.no || 0), 0);
    const copies = selected.map((row, idx) => ({
      ...row,
      id: 0,
      no: maxNo + idx + 1,
      tc_id: `${row.tc_id}-copy`,
    }));
    setRowData((prev) => [...prev, ...copies as TestCase[]]);
    toast.success(`${copies.length}개 TC 복사됨 (하단에 추가)`);
  };

  // 시트가 없고 "기본"도 없으면 시트 추가 화면 표시
  const hasSheet = sheets.length > 0;

  if (!hasSheet && !loading) {
    return (
      <div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "calc(100vh - 220px)", gap: 20 }}>
          <div style={{ fontSize: 48, opacity: 0.3 }}>📋</div>
          <div style={{ fontSize: 16, color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.8 }}>
            폴더나 시트를 추가하여 테스트 케이스를 관리하세요.
          </div>
          {canEditTC && (
            showAddSheet ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid var(--border-input)", fontSize: 14, outline: "none", width: 200, backgroundColor: "var(--bg-input)", color: "var(--text-primary)" }}
                  placeholder={addingFolder ? "폴더 이름" : "시트 이름"}
                  value={newSheetName}
                  onChange={(e) => setNewSheetName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddSheet()}
                  autoFocus
                />
                <button style={{ padding: "8px 18px", borderRadius: 8, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer" }} onClick={handleAddSheet}>
                  추가
                </button>
                <button style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid var(--border-input)", backgroundColor: "transparent", color: "var(--text-secondary)", fontSize: 14, cursor: "pointer" }} onClick={() => { setShowAddSheet(false); setNewSheetName(""); setAddingFolder(false); }}>
                  취소
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 8 }}>
                <button style={{ padding: "10px 24px", borderRadius: 8, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer" }} onClick={() => { setAddingFolder(true); setShowAddSheet(true); }}>
                  + 폴더 추가
                </button>
                <button style={{ padding: "10px 24px", borderRadius: 8, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", opacity: 0.85 }} onClick={() => { setAddingFolder(false); setShowAddSheet(true); }}>
                  + 시트 추가
                </button>
                <button style={{ padding: "10px 24px", borderRadius: 8, border: "1px solid var(--border-input)", backgroundColor: "transparent", color: "var(--text-primary)", fontSize: 14, cursor: "pointer" }} onClick={() => emptyFileInputRef.current?.click()}>
                  Excel Import
                </button>
                <input ref={emptyFileInputRef} type="file" accept=".xlsx,.xls,.csv" style={{ display: "none" }} onChange={handleImport} />
              </div>
            )
          )}
        </div>
        {/* 시트 선택 모달 (빈 프로젝트에서도 표시) */}
        {importFile && importSheets.length > 1 && (
          <div style={sheetModalStyles.overlay} onClick={() => { setImportFile(null); setImportSheets([]); }}>
            <div style={sheetModalStyles.panel} onClick={(e) => e.stopPropagation()}>
              <div style={sheetModalStyles.header}>
                <h3 style={sheetModalStyles.title}>가져올 시트 선택</h3>
                <span style={sheetModalStyles.subtitle}>{importFile.name}</span>
              </div>
              <div style={sheetModalStyles.body}>
                <div style={sheetModalStyles.actions}>
                  <button style={sheetModalStyles.linkBtn} onClick={() => setSelectedSheets(new Set(importSheets.map((sh) => sh.name)))}>전체 선택</button>
                  <button style={sheetModalStyles.linkBtn} onClick={() => setSelectedSheets(new Set())}>전체 해제</button>
                </div>
                {importSheets.map((sheet) => (
                  <label key={sheet.name} style={sheetModalStyles.sheetRow}>
                    <input type="checkbox" checked={selectedSheets.has(sheet.name)} onChange={(e) => { const next = new Set(selectedSheets); e.target.checked ? next.add(sheet.name) : next.delete(sheet.name); setSelectedSheets(next); }} style={{ width: 16, height: 16 }} />
                    <span style={sheetModalStyles.sheetName}>{sheet.name}</span>
                    <span style={sheetModalStyles.sheetCount}>{sheet.tc_count}개 TC</span>
                  </label>
                ))}
              </div>
              <div style={sheetModalStyles.footer}>
                <span style={sheetModalStyles.summary}>{selectedSheets.size}개 시트 선택 ({importSheets.filter((sh) => selectedSheets.has(sh.name)).reduce((a, sh) => a + sh.tc_count, 0)}개 TC)</span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={sheetModalStyles.cancelBtn} onClick={() => { setImportFile(null); setImportSheets([]); }}>취소</button>
                  <button style={{ ...sheetModalStyles.importBtn, opacity: selectedSheets.size === 0 || importLoading ? 0.5 : 1 }} disabled={selectedSheets.size === 0 || importLoading} onClick={handleImportConfirm}>
                    {importLoading ? "가져오는 중..." : "가져오기"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── 시트 트리 사이드바 렌더링 (VS Code 스타일) ──
  const renderSheetTree = () => {
    if (flatSheets.length <= 1 && flatSheets[0]?.name === "기본") return null;

    const renderNode = (node: SheetNode, depth: number): React.ReactNode => {
      const isExpanded = expandedSheets.has(node.id);
      const hasChildren = (node.children || []).length > 0;
      const isActive = activeSheet === node.name;

      return (
        <div key={node.id || node.name}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "4px 8px",
              paddingLeft: 8 + depth * 16,
              cursor: "pointer",
              backgroundColor: isActive ? "rgba(45,74,122,0.15)" : "transparent",
              borderLeft: isActive ? "3px solid var(--accent)" : "3px solid transparent",
              fontSize: 13,
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              fontWeight: isActive ? 600 : 400,
              gap: 4,
              userSelect: "none",
            }}
            onClick={() => {
              if (node.is_folder) {
                // 폴더: 펼침/접기 토글
                setExpandedSheets(prev => {
                  const next = new Set(prev);
                  next.has(node.id) ? next.delete(node.id) : next.add(node.id);
                  return next;
                });
              } else {
                // 시트: TC 표시
                setActiveSheet(node.name);
              }
            }}
            onContextMenu={(e) => {
              e.preventDefault();
              // 컨텍스트 메뉴 대신 인라인으로
            }}
          >
            {/* 펼침/접기 */}
            {(node.is_folder || hasChildren) ? (
              <span
                style={{ fontSize: 10, width: 16, textAlign: "center", flexShrink: 0, color: "var(--text-secondary)" }}
                onClick={(e) => {
                  e.stopPropagation();
                  setExpandedSheets(prev => {
                    const next = new Set(prev);
                    next.has(node.id) ? next.delete(node.id) : next.add(node.id);
                    return next;
                  });
                }}
              >
                {isExpanded ? "▼" : "▶"}
              </span>
            ) : (
              <span style={{ width: 16, flexShrink: 0 }} />
            )}
            {/* 아이콘 */}
            <span style={{ fontSize: 14, flexShrink: 0 }}>{node.is_folder ? (isExpanded ? "📂" : "📁") : "📄"}</span>
            {/* 이름 */}
            <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {node.name}
            </span>
            {/* TC 수 (시트만) */}
            {!node.is_folder && (
              <span style={{ fontSize: 10, color: "var(--text-secondary)", flexShrink: 0 }}>
                {node.tc_count}
              </span>
            )}
            {/* 액션 버튼 */}
            {canEditTC && (
              <span style={{ display: "flex", gap: 2, marginLeft: 4, flexShrink: 0 }}>
                {/* 폴더: 하위 폴더/시트 추가 가능 */}
                {node.is_folder && (
                  <>
                    <span
                      title="하위 폴더 추가"
                      style={{ cursor: "pointer", fontSize: 10, opacity: 0.4, padding: "0 1px" }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setAddSheetParentId(node.id);
                        setAddingFolder(true);
                        setShowAddSheet(true);
                        setNewSheetName("");
                      }}
                    >📁+</span>
                    <span
                      title="하위 시트 추가"
                      style={{ cursor: "pointer", fontSize: 10, opacity: 0.4, padding: "0 1px" }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setAddSheetParentId(node.id);
                        setAddingFolder(false);
                        setShowAddSheet(true);
                        setNewSheetName("");
                      }}
                    >📄+</span>
                  </>
                )}
                <span
                  title={node.is_folder ? "폴더 삭제" : "시트 삭제"}
                  style={{ cursor: "pointer", fontSize: 12, opacity: 0.4, padding: "0 2px" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    const label = node.is_folder ? "폴더" : "시트";
                    const childInfo = hasChildren ? ` (하위 ${(node.children || []).length}개 항목 포함)` : "";
                    if (!confirm(`"${node.name}" ${label}를 삭제하시겠습니까?${childInfo}`)) return;
                    testCasesApi.deleteSheet(projectId, node.name).then(() => {
                      toast.success(`${node.name} ${label} 삭제됨`);
                      if (activeSheet === node.name) setActiveSheet(null);
                      loadSheets();
                      loadData();
                    }).catch(() => toast.error(`${label} 삭제 실패`));
                  }}
                >×</span>
              </span>
            )}
          </div>
          {/* 하위 노드 */}
          {(node.is_folder || hasChildren) && isExpanded && (node.children || []).map(child => renderNode(child, depth + 1))}
        </div>
      );
    };

    return (
      <div style={{
        width: sidebarOpen ? 220 : 36,
        minWidth: sidebarOpen ? 220 : 36,
        borderRight: "1px solid var(--border-color)",
        backgroundColor: "var(--bg-card)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        transition: "width 0.15s, min-width 0.15s",
      }}>
        {/* 헤더 */}
        <div style={{
          padding: sidebarOpen ? "10px 12px" : "10px 8px",
          fontSize: 11,
          fontWeight: 700,
          color: "var(--text-secondary)",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          borderBottom: "1px solid var(--border-color)",
          display: "flex",
          justifyContent: sidebarOpen ? "space-between" : "center",
          alignItems: "center",
        }}>
          {sidebarOpen && <span>시트</span>}
          <span
            style={{ cursor: "pointer", fontSize: 14, opacity: 0.6, padding: "0 2px" }}
            title={sidebarOpen ? "사이드바 접기" : "사이드바 펼치기"}
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >{sidebarOpen ? "◀" : "▶"}</span>
          {canEditTC && sidebarOpen && (
            <span style={{ display: "flex", gap: 2 }}>
              <span
                style={{ cursor: "pointer", fontSize: 12, opacity: 0.6, padding: "0 3px" }}
                title="폴더 추가"
                onClick={() => { setAddSheetParentId(null); setAddingFolder(true); setShowAddSheet(true); setNewSheetName(""); }}
              >📁+</span>
              <span
                style={{ cursor: "pointer", fontSize: 12, opacity: 0.6, padding: "0 3px" }}
                title="시트 추가"
                onClick={() => { setAddSheetParentId(null); setAddingFolder(false); setShowAddSheet(true); setNewSheetName(""); }}
              >📄+</span>
            </span>
          )}
        </div>

        {!sidebarOpen ? null : <>
        {/* 시트 추가 입력 */}
        {showAddSheet && (
          <div style={{ padding: "6px 8px", borderBottom: "1px solid var(--border-color)" }}>
            {addSheetParentId && (
              <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 2 }}>
                {flatSheets.find(s => s.id === addSheetParentId)?.name} 하위
              </div>
            )}
            <div style={{ fontSize: 10, color: "var(--accent)", marginBottom: 2, fontWeight: 600 }}>
              {addingFolder ? "📁 폴더" : "📄 시트"} 추가
            </div>
            <div style={{ display: "flex", gap: 4 }}>
              <input
                style={{ flex: 1, padding: "4px 6px", fontSize: 12, borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)", outline: "none" }}
                placeholder={addingFolder ? "폴더 이름" : "시트 이름"}
                value={newSheetName}
                onChange={(e) => setNewSheetName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleAddSheet(); if (e.key === "Escape") { setShowAddSheet(false); setNewSheetName(""); setAddSheetParentId(null); setAddingFolder(false); } }}
                autoFocus
              />
              <button
                style={{ padding: "4px 8px", fontSize: 11, borderRadius: 4, border: "none", backgroundColor: "var(--accent)", color: "#fff", cursor: "pointer" }}
                onClick={handleAddSheet}
              >추가</button>
            </div>
          </div>
        )}

        {/* 트리 */}
        <div style={{ flex: 1, overflowY: "auto", padding: "4px 0" }}>
          {/* 전체 보기 */}
          {flatSheets.length > 1 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                padding: "4px 8px",
                cursor: "pointer",
                backgroundColor: activeSheet === null ? "rgba(45,74,122,0.15)" : "transparent",
                borderLeft: activeSheet === null ? "3px solid var(--accent)" : "3px solid transparent",
                fontSize: 13,
                color: activeSheet === null ? "var(--text-primary)" : "var(--text-secondary)",
                fontWeight: activeSheet === null ? 600 : 400,
                gap: 4,
              }}
              onClick={() => setActiveSheet(null)}
            >
              <span style={{ width: 16 }} />
              <span style={{ fontSize: 14 }}>📋</span>
              <span style={{ flex: 1 }}>전체</span>
              <span style={{ fontSize: 10, color: "var(--text-secondary)" }}>
                {flatSheets.reduce((a, s) => a + s.tc_count, 0)}
              </span>
            </div>
          )}
          {sheets.map(node => renderNode(node, 0))}
        </div>
        </>}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", height: "calc(100vh - 160px)" }}>
      {/* 왼쪽: 시트 트리 사이드바 */}
      {renderSheetTree()}

      {/* 오른쪽: 툴바 + 그리드 */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Toolbar */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          {canEditTC && (
            <>
              <button style={styles.btnPrimary} onClick={handleAddRow}>
                + 행 추가
              </button>
              <select
                style={styles.btnGhost}
                defaultValue="5"
                onChange={async (e) => {
                  const count = parseInt(e.target.value);
                  if (!count) return;
                  for (let i = 0; i < count; i++) await handleAddRow();
                  toast.success(`${count}개 행 추가됨`);
                }}
              >
                <option value="1">1행</option>
                <option value="3">3행</option>
                <option value="5">5행</option>
                <option value="10">10행</option>
                <option value="20">20행</option>
                <option value="30">30행</option>
              </select>
              <button style={styles.btnGhost} onClick={handleCopySelected}>
                선택 복사
              </button>
              <button style={styles.btnDanger} onClick={handleDeleteSelected}>
                선택 삭제
              </button>
              <div style={styles.separator} />
              <button style={{ ...styles.btnGhost, opacity: undoCount === 0 ? 0.4 : 1 }} onClick={handleUndo} title="Ctrl+Z" disabled={undoCount === 0}>
                Undo
              </button>
              <button style={{ ...styles.btnGhost, opacity: redoCount === 0 ? 0.4 : 1 }} onClick={handleRedo} title="Ctrl+Y" disabled={redoCount === 0}>
                Redo
              </button>
              <button style={styles.btnGhost} onClick={handleAutoFillTcId}>
                TC ID 자동채우기
              </button>
              <button
                style={styles.btnGhost}
                onClick={() => {
                  const api = gridApiRef.current;
                  if (!api) return;
                  const selected = api.getSelectedRows() as TestCase[];
                  if (selected.length === 0) {
                    toast.error("변경할 행을 선택해 주세요.");
                    return;
                  }
                  setBulkOpen(true);
                }}
              >
                일괄 변경
              </button>
              <div style={styles.separator} />
              <button style={styles.btnGhost} onClick={() => fileInputRef.current?.click()}>
                Excel Import
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                style={{ display: "none" }}
                onChange={handleImport}
              />
            </>
          )}
          <button style={styles.btnGhost} onClick={handleExport}>
            Excel Export
          </button>
          <div style={styles.separator} />
          <button
            style={styles.btnGhost}
            onClick={() => {
              const api = gridApiRef.current;
              if (!api) return;
              const selected = api.getSelectedRows() as TestCase[];
              if (selected.length === 1) {
                if (!selected[0].id) {
                  toast.error("저장된 TC만 이력 조회가 가능합니다.");
                  return;
                }
                openHistory(selected[0]);
              } else {
                openProjectHistory();
              }
            }}
          >
            변경이력
          </button>
        </div>
        <div style={styles.toolbarRight}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <input
              style={styles.searchInput}
              type="text"
              placeholder="검색..."
              value={searchText}
              onChange={onSearchChange}
            />
            <button
              style={{
                ...styles.btnGhost,
                fontSize: 11,
                padding: "4px 8px",
                opacity: replaceOpen ? 1 : 0.6,
              }}
              onClick={() => setReplaceOpen(!replaceOpen)}
              title="찾기/바꾸기"
            >
              바꾸기
            </button>
          </div>
          {canEditTC && replaceOpen && (
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <input
                style={{ ...styles.searchInput, width: 140 }}
                type="text"
                placeholder="바꿀 내용..."
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
              />
              <button
                style={{ ...styles.btnPrimary, fontSize: 11, padding: "4px 10px", whiteSpace: "nowrap" }}
                onClick={handleReplaceAll}
                disabled={!searchText}
              >
                모두 바꾸기
              </button>
            </div>
          )}
          <button
            style={{
              ...styles.btnGhost,
              fontSize: 11,
              padding: "4px 10px",
              backgroundColor: filterConditions.length > 0 ? "var(--accent)" : undefined,
              color: filterConditions.length > 0 ? "#fff" : undefined,
            }}
            onClick={() => setShowFilterPanel(!showFilterPanel)}
            title="고급 필터"
          >
            필터{filterConditions.length > 0 ? ` (${filterConditions.length})` : ""}
          </button>
        </div>
      </div>

      {/* ── 고급 필터 패널 ── */}
      {showFilterPanel && (
        <div style={{ padding: "8px 12px", backgroundColor: "var(--bg-card)", borderBottom: "1px solid var(--border-color)", fontSize: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>필터 조건</span>
            <select
              style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)" }}
              value={filterLogic}
              onChange={(e) => setFilterLogic(e.target.value as "AND" | "OR")}
            >
              <option value="AND">AND (모두 일치)</option>
              <option value="OR">OR (하나라도 일치)</option>
            </select>
            <button
              style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
              onClick={() => {
                setFilterConditions([...filterConditions, { field: "tc_id", operator: "contains", value: "" }]);
              }}
            >
              + 조건 추가
            </button>
            {filterConditions.length > 0 && (
              <>
                <button
                  style={{ ...styles.btnPrimary, fontSize: 11, padding: "3px 10px" }}
                  onClick={async () => {
                    try {
                      const data = await filtersApi.apply(projectId, filterConditions, filterLogic, activeSheet || undefined);
                      setRowData(data);
                      toast.success(`필터 적용: ${data.length}건`);
                    } catch {
                      toast.error("필터 적용 실패");
                    }
                  }}
                >
                  적용
                </button>
                <button
                  style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
                  onClick={() => {
                    setFilterConditions([]);
                    setActiveFilterName(null);
                    loadData();
                  }}
                >
                  초기화
                </button>
                {canEditTC && (
                  <button
                    style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
                    onClick={async () => {
                      const name = prompt("필터 이름을 입력하세요:", activeFilterName || "");
                      if (!name) return;
                      try {
                        await filtersApi.create(projectId, { name, conditions: filterConditions, logic: filterLogic });
                        toast.success(`"${name}" 필터 저장됨`);
                        setActiveFilterName(name);
                      } catch {
                        toast.error("필터 저장 실패");
                      }
                    }}
                  >
                    저장
                  </button>
                )}
                <button
                  style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
                  onClick={async () => {
                    try {
                      const saved = await filtersApi.list(projectId);
                      if (saved.length === 0) { toast("저장된 필터가 없습니다."); return; }
                      const names = saved.map(f => f.name).join("\n");
                      const chosen = prompt(`불러올 필터:\n${names}\n\n이름 입력:`);
                      if (!chosen) return;
                      const found = saved.find(f => f.name === chosen);
                      if (!found) { toast.error("필터를 찾을 수 없습니다."); return; }
                      setFilterConditions(found.conditions);
                      setFilterLogic(found.logic as "AND" | "OR");
                      setActiveFilterName(found.name);
                      toast.success(`"${found.name}" 필터 불러옴`);
                    } catch {
                      toast.error("필터 목록 로드 실패");
                    }
                  }}
                >
                  불러오기
                </button>
              </>
            )}
          </div>
          {filterConditions.map((cond, idx) => (
            <div key={idx} style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
              <select
                style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)", minWidth: 100 }}
                value={cond.field}
                onChange={(e) => {
                  const next = [...filterConditions];
                  next[idx] = { ...next[idx], field: e.target.value };
                  setFilterConditions(next);
                }}
              >
                {[
                  { v: "tc_id", l: "TC ID" }, { v: "type", l: "Type" }, { v: "category", l: "Category" },
                  { v: "depth1", l: "Depth 1" }, { v: "depth2", l: "Depth 2" }, { v: "priority", l: "Priority" },
                  { v: "test_type", l: "Platform" }, { v: "assignee", l: "Assignee" }, { v: "test_steps", l: "Steps" },
                  { v: "expected_result", l: "Expected" }, { v: "remarks", l: "Remarks" }, { v: "precondition", l: "Precondition" },
                  { v: "issue_link", l: "Issue Link" }, { v: "sheet_name", l: "Sheet" },
                ].map(o => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
              <select
                style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)", minWidth: 90 }}
                value={cond.operator}
                onChange={(e) => {
                  const next = [...filterConditions];
                  next[idx] = { ...next[idx], operator: e.target.value };
                  setFilterConditions(next);
                }}
              >
                <option value="contains">포함</option>
                <option value="not_contains">미포함</option>
                <option value="eq">일치</option>
                <option value="neq">불일치</option>
                <option value="empty">비어있음</option>
                <option value="not_empty">비어있지 않음</option>
              </select>
              {!["empty", "not_empty"].includes(cond.operator) && (
                <input
                  style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)", width: 150 }}
                  placeholder="값..."
                  value={(cond.value as string) || ""}
                  onChange={(e) => {
                    const next = [...filterConditions];
                    next[idx] = { ...next[idx], value: e.target.value };
                    setFilterConditions(next);
                  }}
                />
              )}
              <span
                style={{ cursor: "pointer", color: "var(--text-secondary)", padding: "0 4px", fontSize: 14 }}
                onClick={() => {
                  const next = filterConditions.filter((_, i) => i !== idx);
                  setFilterConditions(next);
                }}
              >
                ×
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Grid */}
      <div
        className="ag-theme-alpine"
        style={{ flex: 1, width: "100%" }}
      >
        {loading ? (
          <div style={{ textAlign: "center", padding: 60, color: "var(--text-secondary)" }}>
            불러오는 중...
          </div>
        ) : (
          <AgGridReact
            ref={gridRef}
            rowData={rowData}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            localeText={AG_GRID_LOCALE_KO}
            rowSelection={{ mode: "multiRow", checkboxes: true, headerCheckbox: true, selectAll: "filtered" }}
            onGridReady={onGridReady}
            onCellValueChanged={onCellValueChanged}
            onCellKeyDown={onCellKeyDown}
            context={{ jiraBaseUrl: project.jira_base_url, searchKeyword: searchText }}
            animateRows={true}
            singleClickEdit={true}
            stopEditingWhenCellsLoseFocus={true}
            getRowId={(params) =>
              params.data.id ? String(params.data.id) : `new_${params.data.no}`
            }
          />
        )}
      </div>
      {/* Bulk Edit Modal */}
      {bulkOpen && (
        <div style={historyStyles.overlay} onClick={() => setBulkOpen(false)}>
          <div
            style={{ ...historyStyles.panel, width: 400, maxHeight: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={historyStyles.header}>
              <h3 style={historyStyles.title}>
                일괄 변경 ({gridApiRef.current?.getSelectedRows().length || 0}개 행)
              </h3>
              <button style={historyStyles.closeBtn} onClick={() => setBulkOpen(false)}>✕</button>
            </div>
            <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4, display: "block" }}>
                  변경할 컬럼
                </label>
                <select
                  value={bulkField}
                  onChange={(e) => { setBulkField(e.target.value); setBulkValue(""); }}
                  style={{
                    width: "100%", padding: "8px 10px", borderRadius: 6,
                    border: "1px solid var(--border-color)", backgroundColor: "var(--bg-input)",
                    color: "var(--text-primary)", fontSize: 13,
                  }}
                >
                  {BULK_FIELDS.map((f) => (
                    <option key={f.field} value={f.field}>{f.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4, display: "block" }}>
                  변경할 값
                </label>
                {BULK_FIELDS.find((f) => f.field === bulkField)?.options ? (
                  <select
                    value={bulkValue}
                    onChange={(e) => setBulkValue(e.target.value)}
                    style={{
                      width: "100%", padding: "8px 10px", borderRadius: 6,
                      border: "1px solid var(--border-color)", backgroundColor: "var(--bg-input)",
                      color: "var(--text-primary)", fontSize: 13,
                    }}
                  >
                    <option value="">-- 선택 --</option>
                    {BULK_FIELDS.find((f) => f.field === bulkField)!.options!.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={bulkValue}
                    onChange={(e) => setBulkValue(e.target.value)}
                    placeholder="값을 입력하세요"
                    style={{
                      width: "100%", padding: "8px 10px", borderRadius: 6,
                      border: "1px solid var(--border-color)", backgroundColor: "var(--bg-input)",
                      color: "var(--text-primary)", fontSize: 13, boxSizing: "border-box",
                    }}
                  />
                )}
              </div>
              <button
                onClick={handleBulkApply}
                style={{
                  ...styles.btnPrimary,
                  width: "100%", padding: "10px 0", fontSize: 14, marginTop: 4,
                }}
              >
                적용
              </button>
            </div>
          </div>
        </div>
      )}
      {/* History Modal */}
      {historyTc && (
        <div style={historyStyles.overlay} onClick={() => setHistoryTc(null)}>
          <div style={{...historyStyles.panel, ...(historyMode === "project" ? { width: 800 } : {})}} onClick={(e) => e.stopPropagation()}>
            <div style={historyStyles.header}>
              <h3 style={historyStyles.title}>
                {historyMode === "project"
                  ? "프로젝트 변경 이력"
                  : `변경 이력 - ${historyTc.tc_id || `No.${historyTc.no}`}`}
              </h3>
              <button style={historyStyles.closeBtn} onClick={() => setHistoryTc(null)}>
                ✕
              </button>
            </div>
            <div style={historyStyles.body}>
              {historyLoading ? (
                <div style={historyStyles.empty}>불러오는 중...</div>
              ) : historyData.length === 0 ? (
                <div style={historyStyles.empty}>변경 이력이 없습니다.</div>
              ) : historyMode === "project" ? (
                (() => {
                  // Group by tc_id → changer → date
                  const grouped = new Map<number, {
                    test_case_id: number;
                    tc_id: string;
                    changers: Set<string>;
                    lastDate: string;
                    fieldCount: number;
                  }>();
                  for (const h of historyData) {
                    const key = h.test_case_id;
                    if (!grouped.has(key)) {
                      grouped.set(key, {
                        test_case_id: key,
                        tc_id: h.tc_id || `#${h.test_case_id}`,
                        changers: new Set(),
                        lastDate: h.changed_at,
                        fieldCount: 0,
                      });
                    }
                    const g = grouped.get(key)!;
                    if (h.changer_name) g.changers.add(h.changer_name);
                    g.fieldCount++;
                    if (h.changed_at > g.lastDate) g.lastDate = h.changed_at;
                  }
                  const entries = [...grouped.values()].sort(
                    (a, b) => b.lastDate.localeCompare(a.lastDate)
                  );
                  return (
                    <table style={historyStyles.table}>
                      <thead>
                        <tr>
                          <th style={historyStyles.th}>TC ID</th>
                          <th style={historyStyles.th}>최근 수정일</th>
                          <th style={historyStyles.th}>수정자</th>
                          <th style={historyStyles.th}>변경 수</th>
                        </tr>
                      </thead>
                      <tbody>
                        {entries.map((e, i) => (
                          <tr key={i} style={{ cursor: "pointer" }}
                            onClick={() => {
                              const tc = rowData.find(r => r.id === e.test_case_id);
                              if (tc) openHistory(tc);
                            }}
                          >
                            <td style={{...historyStyles.td, fontWeight: 600, color: "var(--color-primary)" }}>{e.tc_id}</td>
                            <td style={historyStyles.td}>
                              {new Date(e.lastDate).toLocaleString("ko-KR", {
                                year: "numeric",
                                month: "2-digit",
                                day: "2-digit",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </td>
                            <td style={historyStyles.td}>{[...e.changers].join(", ") || "-"}</td>
                            <td style={{...historyStyles.td, textAlign: "center" }}>{e.fieldCount}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  );
                })()
              ) : (
                <table style={historyStyles.table}>
                  <thead>
                    <tr>
                      <th style={historyStyles.th}>일시</th>
                      <th style={historyStyles.th}>변경자</th>
                      <th style={historyStyles.th}>필드</th>
                      <th style={historyStyles.th}>이전 값</th>
                      <th style={historyStyles.th}>변경 값</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyData.map((h) => (
                      <tr key={h.id}>
                        <td style={historyStyles.td}>
                          {new Date(h.changed_at).toLocaleString("ko-KR", {
                            month: "2-digit",
                            day: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </td>
                        <td style={historyStyles.td}>{h.changer_name || "-"}</td>
                        <td style={historyStyles.tdField}>{h.field_name}</td>
                        <td style={historyStyles.tdOld}>{h.old_value || "-"}</td>
                        <td style={historyStyles.tdNew}>{h.new_value || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── 시트 선택 모달 ── */}
      {importFile && importSheets.length > 1 && (
        <div style={sheetModalStyles.overlay} onClick={() => { setImportFile(null); setImportSheets([]); }}>
          <div style={sheetModalStyles.panel} onClick={(e) => e.stopPropagation()}>
            <div style={sheetModalStyles.header}>
              <h3 style={sheetModalStyles.title}>가져올 시트 선택</h3>
              <span style={sheetModalStyles.subtitle}>{importFile.name}</span>
            </div>
            <div style={sheetModalStyles.body}>
              <div style={sheetModalStyles.actions}>
                <button
                  style={sheetModalStyles.linkBtn}
                  onClick={() => setSelectedSheets(new Set(importSheets.map((s) => s.name)))}
                >
                  전체 선택
                </button>
                <button
                  style={sheetModalStyles.linkBtn}
                  onClick={() => setSelectedSheets(new Set())}
                >
                  전체 해제
                </button>
              </div>
              {importSheets.map((sheet) => (
                <label key={sheet.name} style={sheetModalStyles.sheetRow}>
                  <input
                    type="checkbox"
                    checked={selectedSheets.has(sheet.name)}
                    onChange={(e) => {
                      const next = new Set(selectedSheets);
                      e.target.checked ? next.add(sheet.name) : next.delete(sheet.name);
                      setSelectedSheets(next);
                    }}
                    style={{ width: 16, height: 16 }}
                  />
                  <span style={sheetModalStyles.sheetName}>{sheet.name}</span>
                  <span style={sheetModalStyles.sheetCount}>{sheet.tc_count}개 TC</span>
                  {sheet.existing > 0 && (
                    <span style={{ fontSize: 11, color: "#DC2626", fontWeight: 600 }}>
                      (기존 {sheet.existing}개 덮어쓰기)
                    </span>
                  )}
                </label>
              ))}
            </div>
            <div style={sheetModalStyles.footer}>
              <span style={sheetModalStyles.summary}>
                {selectedSheets.size}개 시트 선택 ({importSheets.filter((s) => selectedSheets.has(s.name)).reduce((a, s) => a + s.tc_count, 0)}개 TC)
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  style={sheetModalStyles.cancelBtn}
                  onClick={() => { setImportFile(null); setImportSheets([]); }}
                >
                  취소
                </button>
                <button
                  style={{ ...sheetModalStyles.importBtn, opacity: selectedSheets.size === 0 || importLoading ? 0.5 : 1 }}
                  disabled={selectedSheets.size === 0 || importLoading}
                  onClick={handleImportConfirm}
                >
                  {importLoading ? "가져오는 중..." : "가져오기"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
    </div>
  );
}

const sheetModalStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.5)", display: "flex",
    justifyContent: "center", alignItems: "center", zIndex: 200,
  },
  panel: {
    backgroundColor: "var(--bg-card)", borderRadius: 12,
    width: 440, maxWidth: "90vw", boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
    overflow: "hidden",
  },
  header: {
    padding: "20px 24px 12px", borderBottom: "1px solid var(--border-color)",
  },
  title: { margin: 0, fontSize: 17, fontWeight: 700, color: "var(--text-primary)" },
  subtitle: { fontSize: 12, color: "var(--text-secondary)", marginTop: 4, display: "block" },
  body: { padding: "16px 24px", maxHeight: 320, overflow: "auto" },
  actions: { display: "flex", gap: 12, marginBottom: 12 },
  linkBtn: {
    background: "none", border: "none", color: "var(--color-link)",
    fontSize: 12, fontWeight: 600, cursor: "pointer", padding: 0,
  },
  sheetRow: {
    display: "flex", alignItems: "center", gap: 12,
    padding: "10px 12px", borderRadius: 8,
    border: "1px solid var(--border-color)", marginBottom: 8, cursor: "pointer",
  },
  sheetName: { flex: 1, fontSize: 14, fontWeight: 600, color: "var(--text-primary)" },
  sheetCount: {
    fontSize: 12, color: "var(--text-secondary)", backgroundColor: "var(--bg-page)",
    padding: "2px 10px", borderRadius: 12, fontWeight: 600,
  },
  footer: {
    padding: "12px 24px 20px", borderTop: "1px solid var(--border-color)",
    display: "flex", justifyContent: "space-between", alignItems: "center",
  },
  summary: { fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 },
  cancelBtn: {
    padding: "8px 16px", borderRadius: 6, border: "1px solid var(--border-input)",
    backgroundColor: "transparent", color: "var(--text-secondary)", fontSize: 13, cursor: "pointer",
  },
  importBtn: {
    padding: "8px 20px", borderRadius: 6, border: "none",
    backgroundColor: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
  },
};

const historyStyles: Record<string, React.CSSProperties> = {
  overlay: {
    position: "fixed",
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
  panel: {
    backgroundColor: "var(--bg-card)",
    borderRadius: 12,
    width: 720,
    maxWidth: "90vw",
    maxHeight: "80vh",
    display: "flex",
    flexDirection: "column",
    boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 20px",
    borderBottom: "1px solid var(--border-color)",
  },
  title: {
    margin: 0,
    fontSize: 16,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  closeBtn: {
    border: "none",
    background: "none",
    fontSize: 18,
    cursor: "pointer",
    color: "var(--text-secondary)",
    padding: "0 4px",
  },
  body: {
    padding: "12px 20px 20px",
    overflow: "auto",
    flex: 1,
  },
  empty: {
    textAlign: "center",
    color: "var(--text-secondary)",
    padding: 40,
    fontSize: 14,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 12,
  },
  th: {
    textAlign: "left",
    padding: "8px 10px",
    borderBottom: "2px solid var(--border-color)",
    color: "var(--text-secondary)",
    fontWeight: 600,
    whiteSpace: "nowrap",
  },
  td: {
    padding: "7px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--text-primary)",
    verticalAlign: "top",
  },
  tdField: {
    padding: "7px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--color-link)",
    fontWeight: 600,
    whiteSpace: "nowrap",
    verticalAlign: "top",
  },
  tdOld: {
    padding: "7px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--color-fail)",
    maxWidth: 180,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "pre-wrap",
    verticalAlign: "top",
  },
  tdNew: {
    padding: "7px 10px",
    borderBottom: "1px solid var(--border-color)",
    color: "var(--color-pass)",
    maxWidth: 180,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "pre-wrap",
    verticalAlign: "top",
  },
};

const styles: Record<string, React.CSSProperties> = {
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
    padding: "0 12px",
    flexWrap: "wrap",
    gap: 8,
  },
  toolbarLeft: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  toolbarRight: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  btnPrimary: {
    padding: "5px 12px",
    borderRadius: 5,
    border: "none",
    backgroundColor: "var(--accent)",
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnDanger: {
    padding: "5px 12px",
    borderRadius: 5,
    border: "none",
    backgroundColor: "#DC2626",
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  btnGhost: {
    padding: "5px 12px",
    borderRadius: 5,
    border: "1px solid var(--border-input)",
    backgroundColor: "var(--bg-card)",
    color: "var(--text-primary)",
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
  },
  btnSave: {
    padding: "5px 18px",
    borderRadius: 5,
    border: "none",
    backgroundColor: "var(--color-pass)",
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  separator: {
    width: 1,
    height: 20,
    backgroundColor: "var(--border-color)",
    margin: "0 4px",
  },
  searchInput: {
    padding: "5px 10px",
    borderRadius: 5,
    border: "1px solid var(--border-input)",
    fontSize: 12,
    width: 180,
    outline: "none",
    backgroundColor: "var(--bg-input)",
    color: "var(--text-primary)",
  },
};
