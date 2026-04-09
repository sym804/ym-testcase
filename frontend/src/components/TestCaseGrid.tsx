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
import { useTranslation } from "react-i18next";
import { testCasesApi, historyApi, customFieldsApi, filtersApi } from "../api";
import type { TestCase, TestCaseHistory, Project, SheetNode, CustomFieldDef, FilterCondition, TCResultHistory } from "../types";
import { AG_GRID_LOCALE_KO } from "../agGridLocaleKo";
import { AG_GRID_LOCALE_EN } from "../agGridLocaleEn";
import toast from "react-hot-toast";
import { translateError } from "../utils/errorMessage";
import MarkdownCell from "./MarkdownCell";
import HighlightCell from "./HighlightCell";
import { useUndoRedo } from "../hooks/useUndoRedo";
import type { UndoGroup } from "../hooks/useUndoRedo";
import SheetTreeSidebar from "./SheetTreeSidebar";

ModuleRegistry.registerModules([AllCommunityModule]);

interface Props {
  projectId: number;
  project: Project;
  highlightTcId?: string;
}

const TYPE_OPTIONS = ["Func.", "UI/UX", "Perf.", "Security", "API", "Data"];
// DB values (Korean) — display names are translated via priorityDisplay / platformDisplay in locale files
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

export default function TestCaseGrid({ projectId, project, highlightTcId }: Props) {
  const { t, i18n } = useTranslation("testcase");
  const gridLocale = i18n.language === "ko" ? AG_GRID_LOCALE_KO : AG_GRID_LOCALE_EN;
  const canEditTC = project.my_role === "admin";
  const gridRef = useRef<AgGridReact>(null);
  const [rowData, setRowData] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [selectedCount, setSelectedCount] = useState(0);
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

  // ── Undo/Redo (커스텀 훅) ──
  const {
    undoStackRef, redoStackRef, isUndoRedoRef,
    undoCount, redoCount, setUndoCount, setRedoCount,
    autoSaveRowRef,
    pushUndo, handleUndo, handleRedo,
  } = useUndoRedo(gridApiRef);

  // ── 찾기/바꾸기 ──
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [replaceText, setReplaceText] = useState("");

  const handleReplaceAll = () => {
    if (!searchText) return;
    const api = gridApiRef.current;
    if (!api) return;

    const textFields = ["tc_id", "type", "category", "depth1", "depth2", "precondition", "test_steps", "expected_result", "remarks"];
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
      toast.success(t("replaceCount", { count }));
    } else {
      toast(t("replaceNoMatch"));
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
    toast.success(t("bulkEditApplied", { count: selected.length, field: BULK_FIELDS.find(f => f.field === bulkField)?.label }));
  };

  // ── 히스토리 패널 ──
  const [historyTc, setHistoryTc] = useState<TestCase | null>(null);
  const [historyMode, setHistoryMode] = useState<"tc" | "project">("tc");
  const [historyData, setHistoryData] = useState<TestCaseHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // ── 결과 히스토리 패널 ──
  const [resultHistory, setResultHistory] = useState<TCResultHistory[]>([]);
  const [resultHistoryTcId, setResultHistoryTcId] = useState<string>("");
  const [resultHistoryOpen, setResultHistoryOpen] = useState(false);

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
      toast.error(t("historyLoadFailed"));
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
      toast.error(t("historyLoadFailed"));
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
        const withSeq = sorted.map((tc) => ({ ...tc, _originalNo: tc.no, no: seq++ }));
        setRowData(withSeq);
      } else {
        setRowData(data);
      }
      undoStackRef.current = [];
      redoStackRef.current = [];
      setUndoCount(0);
      setRedoCount(0);
    } catch (err) {
      console.error(err);
      toast.error(t("loadFailed"));
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

  // 기본 필드 설정 헬퍼
  const fc = project.field_config;
  const fieldDisplay = (key: string, defaultName: string) => ({
    name: fc?.[key]?.display_name || defaultName,
    visible: fc?.[key]?.visible !== false,
  });

  // ── i18n display maps for DB enum values ──
  const priorityRefData: Record<string, string> = useMemo(() => ({
    "매우 높음": t("priorityDisplay.매우 높음", "매우 높음"),
    "높음": t("priorityDisplay.높음", "높음"),
    "보통": t("priorityDisplay.보통", "보통"),
    "낮음": t("priorityDisplay.낮음", "낮음"),
    "매우 낮음": t("priorityDisplay.매우 낮음", "매우 낮음"),
  }), [t]);

  const platformRefData: Record<string, string> = useMemo(() => ({
    "공통": t("platformDisplay.공통", "공통"),
  }), [t]);

  const columnDefs = useMemo<ColDef[]>(
    () => {
      const builtIn: (ColDef & { _key?: string })[] = [
        { _key: "no", field: "no", headerName: "No", width: 70, rowDrag: canEditTC, editable: canEditTC, type: "numericColumn", wrapText: false, autoHeight: false },
        { _key: "tc_id", field: "tc_id", headerName: fieldDisplay("tc_id", "TC ID").name, width: 110, editable: canEditTC, cellRenderer: HighlightCell },
        {
          _key: "type", field: "type",
          headerName: fieldDisplay("type", "Type").name,
          width: 80, editable: canEditTC,
          cellEditor: "agSelectCellEditor", cellEditorParams: { values: TYPE_OPTIONS }, cellRenderer: HighlightCell,
        },
        { _key: "category", field: "category", headerName: fieldDisplay("category", "Category").name, width: 140, editable: canEditTC, wrapText: true, autoHeight: true, cellRenderer: HighlightCell },
        { _key: "depth1", field: "depth1", headerName: fieldDisplay("depth1", "Depth 1").name, width: 150, editable: canEditTC, wrapText: true, autoHeight: true, cellRenderer: HighlightCell },
        { _key: "depth2", field: "depth2", headerName: fieldDisplay("depth2", "Depth 2").name, width: 150, editable: canEditTC, wrapText: true, autoHeight: true, cellRenderer: HighlightCell },
        {
          _key: "priority", field: "priority",
          headerName: fieldDisplay("priority", "Priority").name,
          width: 90, editable: canEditTC,
          cellEditor: "agSelectCellEditor", cellEditorParams: { values: PRIORITY_OPTIONS },
          cellStyle: priorityCellStyle,
          refData: priorityRefData,
          valueFormatter: (params) => priorityRefData[params.value] ?? params.value,
        },
        {
          _key: "test_type", field: "test_type",
          headerName: fieldDisplay("test_type", "Platform").name,
          width: 85, editable: canEditTC,
          cellEditor: "agSelectCellEditor", cellEditorParams: { values: PLATFORM_OPTIONS },
          refData: platformRefData,
          valueFormatter: (params) => platformRefData[params.value] ?? params.value,
        },
        {
          _key: "precondition", field: "precondition",
          headerName: fieldDisplay("precondition", "Precondition").name,
          width: 200, editable: canEditTC, wrapText: true, autoHeight: true,
          cellEditor: "agLargeTextCellEditor", cellEditorPopup: true, cellClass: "ag-cell-left", cellRenderer: MarkdownCell,
        },
        {
          _key: "test_steps", field: "test_steps",
          headerName: fieldDisplay("test_steps", "Test Steps").name,
          minWidth: 400, flex: 2, editable: canEditTC, wrapText: true, autoHeight: true,
          cellEditor: "agLargeTextCellEditor", cellEditorPopup: true, cellClass: "ag-cell-left", cellRenderer: MarkdownCell,
        },
        {
          _key: "expected_result", field: "expected_result",
          headerName: fieldDisplay("expected_result", "Expected Result").name,
          minWidth: 350, flex: 2, editable: canEditTC, wrapText: true, autoHeight: true,
          cellEditor: "agLargeTextCellEditor", cellEditorPopup: true, cellClass: "ag-cell-left", cellRenderer: MarkdownCell,
        },
        { _key: "remarks", field: "remarks", headerName: fieldDisplay("remarks", "Remarks").name, width: 120, editable: canEditTC, wrapText: true, autoHeight: true, cellClass: "ag-cell-left", cellRenderer: MarkdownCell },
      ];
      // No는 항상 표시, 나머지는 visible 체크
      const filtered = builtIn.filter(col => col._key === "no" || fieldDisplay(col._key!, "").visible);
      // _key 제거 (AG Grid에 불필요)
      return [
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        ...filtered.map(({ _key, ...rest }) => rest),
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
    ];
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [canEditTC, customFields, project.field_config, priorityRefData, platformRefData]
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
        // 전체 보기에서 화면용 연속 번호가 DB에 저장되지 않도록 원본 no 복원
        const saveData = { ...data };
        if ("_originalNo" in saveData) {
          saveData.no = (saveData as Record<string, unknown>)._originalNo as number;
          delete (saveData as Record<string, unknown>)._originalNo;
        }
        await testCasesApi.update(projectId, data.id, saveData);
      } catch {
        toast.error(t("autoSaveFailed"));
      }
      delete autoSaveTimerRef.current[key];
    }, 300);
  }, [projectId]);
  autoSaveRowRef.current = autoSaveRow;

  const handleRowDragEnd = useCallback(async () => {
    const gridApi = gridApiRef.current;
    if (!gridApi) return;

    const items: { id: number; no: number }[] = [];
    let index = 0;
    gridApi.forEachNodeAfterFilterAndSort((node) => {
      index++;
      const data = node.data as TestCase;
      if (data && data.id > 0) {
        items.push({ id: data.id, no: index });
      }
      if (data) {
        data.no = index;
      }
    });

    gridApi.refreshCells({ columns: ["no"] });

    if (items.length > 0) {
      try {
        await testCasesApi.reorder(projectId, items);
      } catch {
        toast.error(t("orderSaveFailed"));
      }
    }
  }, [projectId]);

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
      priority: t("priority.normal"),
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
      toast.error(t("addRowFailed"));
    }
  };

  const handleAutoFillTcId = () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows() as TestCase[];
    if (selected.length === 0) {
      toast.error(t("tcIdSelectFirst"));
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
    toast.success(t("tcIdAutoFillDone"));
  };

  const handleDeleteSelected = async () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows() as TestCase[];
    if (selected.length === 0) {
      toast.error(t("deleteSelectFirst"));
      return;
    }

    // 저장되지 않은 신규 행은 그냥 제거
    const unsaved = selected.filter((r) => !r.id || r.id === 0);
    const saved = selected.filter((r) => r.id && r.id !== 0);

    if (unsaved.length > 0) {
      setRowData((prev) => prev.filter((r) => !unsaved.includes(r)));
    }

    if (saved.length === 0) {
      toast.success(t("deleteSuccess", { count: unsaved.length }));
      return;
    }

    try {
      const deletedIds = saved.map((r) => r.id);
      await testCasesApi.bulkDelete(projectId, deletedIds);
      // 그리드에서 즉시 제거
      setRowData((prev) => prev.filter((r) => !saved.some((s) => s.id === r.id)));
      toast(
        (toastInstance) => (
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {t("tcDeleted", { count: saved.length })}
            <button
              onClick={async () => {
                toast.dismiss(toastInstance.id);
                try {
                  for (const id of deletedIds) {
                    await testCasesApi.restore(projectId, id);
                  }
                  toast.success(t("restoreSuccess"));
                  loadData();
                } catch (err) {
                  console.error(err);
                  toast.error(t("restoreFailed"));
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
              {t("restoreAction")}
            </button>
          </span>
        ),
        { duration: 7000 }
      );
    } catch (err) {
      console.error(err);
      toast.error(t("deleteFailed"));
      loadData();
    }
  };


  // ── Excel Import: 시트 선택 ──
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importSheets, setImportSheets] = useState<{ name: string; tc_count: number; existing: number }[]>([]);
  const [selectedSheets, setSelectedSheets] = useState<Set<string>>(new Set());
  const [importLoading, setImportLoading] = useState(false);

  const handleSheetChange = useCallback(() => {
    loadSheets();
    loadData();
  }, [loadSheets, loadData]);

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (emptyFileInputRef.current) emptyFileInputRef.current.value = "";

    try {
      toast(t("analyzingFile"), { duration: 1500 });
      const preview = await testCasesApi.previewImport(projectId, file);
      if (preview.sheets.length === 0) {
        toast.error(t("noValidSheets"));
        return;
      }
      if (preview.sheets.length === 1) {
        const sheet = preview.sheets[0];
        // 기존 TC가 있으면 덮어쓰기 확인
        if (sheet.existing > 0) {
          if (!confirm(t("importOverwriteConfirm", { name: sheet.name, count: sheet.existing }))) return;
        }
        toast(t("importing"), { duration: 2000 });
        const result = await testCasesApi.importExcel(projectId, file, [sheet.name]);
        const created = result.created ?? 0;
        const updated = result.updated ?? 0;
        const imported = result.imported ?? created + updated;
        const msg = updated > 0
          ? t("importCreatedUpdated", { created, updated })
          : t("importCreated", { count: imported });
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
      const errDetail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(errDetail ? translateError(errDetail) : t("importReadFailed"));
    }
  };

  const handleImportConfirm = async () => {
    if (!importFile || selectedSheets.size === 0) return;
    // 중복 시트 확인
    const overlapping = importSheets.filter((s) => selectedSheets.has(s.name) && s.existing > 0);
    if (overlapping.length > 0) {
      const msg = overlapping.map((s) => t("importSheetExisting", { name: s.name, count: s.existing })).join("\n");
      if (!confirm(t("importMultiOverwrite", { details: msg }))) return;
    }
    setImportLoading(true);
    try {
      const result = await testCasesApi.importExcel(projectId, importFile, Array.from(selectedSheets));
      const details = result.sheets.map((s: { sheet: string; created: number; updated: number }) => {
        if (s.updated > 0) return `${s.sheet}: ${t("importCreatedUpdated", { created: s.created, updated: s.updated })}`;
        return `${s.sheet}: ${t("importCreated", { count: s.created })}`;
      }).join(", ");
      toast.success(details);
      const firstImported = result.sheets.find((s: { created: number; updated: number }) => s.created + s.updated > 0);
      if (firstImported) setActiveSheet((firstImported as { sheet: string }).sheet);
      loadSheets();
      setImportFile(null);
      setImportSheets([]);
    } catch (err) {
      console.error(err);
      toast.error(t("importFailed"));
    } finally {
      setImportLoading(false);
    }
  };

  const [showExportModal, setShowExportModal] = useState(false);
  const [exportSplit, setExportSplit] = useState(false);

  const handleExport = async () => {
    try {
      const blob = await testCasesApi.exportExcel(projectId, exportSplit);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `testcases_${projectId}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t("exportSuccess"));
      setShowExportModal(false);
    } catch (err) {
      console.error(err);
      toast.error(t("exportFailed"));
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
        }
      });
      if (filled > 0) {
        pushUndo(undoGroup);
        api.refreshCells({ force: true });
        selectedNodes.forEach((node) => {
          if (node.data && node !== event.node) autoSaveRow(node.data);
        });
        toast.success(t("fillCount", { count: filled, value: sourceValue }));
      }
    }
  }, [pushUndo, autoSaveRow]);

  // ── TC 복제 (서버) ──
  const handleCloneSelected = useCallback(async () => {
    const selected = gridApiRef.current?.getSelectedRows() as TestCase[];
    if (!selected?.length) {
      toast.error(t("cloneSelectFirst"));
      return;
    }
    const savedIds = selected.filter(r => r.id > 0).map(r => r.id);
    if (savedIds.length === 0) {
      toast.error(t("cloneUnsavedError"));
      return;
    }
    try {
      const cloned = await testCasesApi.bulkClone(projectId, savedIds);
      setRowData(prev => [...prev, ...cloned]);
      toast.success(t("cloneSuccess", { count: cloned.length }));
      setTimeout(() => {
        gridApiRef.current?.ensureIndexVisible(rowData.length + cloned.length - 1);
      }, 100);
    } catch {
      toast.error(t("cloneFailed"));
    }
  }, [projectId, rowData.length]);

  // ── 결과 히스토리 조회 ──
  const handleResultHistory = useCallback(async () => {
    const selected = gridApiRef.current?.getSelectedRows() as TestCase[];
    if (!selected?.length || selected.length !== 1) {
      toast.error(t("resultHistorySelectOne"));
      return;
    }
    const tc = selected[0];
    if (tc.id === 0) {
      toast.error(t("resultHistoryUnsaved"));
      return;
    }
    try {
      const data = await testCasesApi.resultHistory(projectId, tc.id);
      setResultHistory(data);
      setResultHistoryTcId(tc.tc_id);
      setResultHistoryOpen(true);
    } catch {
      toast.error(t("resultHistoryFailed"));
    }
  }, [projectId]);

  // ── 빈 프로젝트: 시트/폴더 추가용 로컬 상태 ──
  const [emptyShowAdd, setEmptyShowAdd] = useState(false);
  const [emptyName, setEmptyName] = useState("");
  const [emptyIsFolder, setEmptyIsFolder] = useState(false);

  const handleEmptyAddSheet = async () => {
    const name = emptyName.trim();
    const label = emptyIsFolder ? t("folder") : t("sheet");
    if (!name) { toast.error(t("nameRequired", { label })); return; }
    try {
      await testCasesApi.createSheet(projectId, name, null, emptyIsFolder);
      setEmptyShowAdd(false);
      setEmptyName("");
      if (!emptyIsFolder) setActiveSheet(name);
      loadSheets();
      toast.success(t(emptyIsFolder ? "folderAdded" : "sheetAdded", { name }));
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(detail ? translateError(detail) : t(emptyIsFolder ? "folderAddFailed" : "sheetAddFailed"));
    }
  };

  // 시트가 없고 "기본"도 없으면 시트 추가 화면 표시
  const hasSheet = sheets.length > 0;

  if (!hasSheet && !loading) {
    return (
      <div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "calc(100vh - 220px)", gap: 20 }}>
          <div style={{ fontSize: 48, opacity: 0.3 }}>📋</div>
          <div style={{ fontSize: 16, color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.8 }}>
            {t("emptyProject")}
          </div>
          {canEditTC && (
            emptyShowAdd ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid var(--border-input)", fontSize: 14, outline: "none", width: 200, backgroundColor: "var(--bg-input)", color: "var(--text-primary)" }}
                  placeholder={emptyIsFolder ? t("folderName") : t("sheetName")}
                  value={emptyName}
                  onChange={(e) => setEmptyName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleEmptyAddSheet()}
                  autoFocus
                />
                <button style={{ padding: "8px 18px", borderRadius: 8, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer" }} onClick={handleEmptyAddSheet}>
                  {t("common:add")}
                </button>
                <button style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid var(--border-input)", backgroundColor: "transparent", color: "var(--text-secondary)", fontSize: 14, cursor: "pointer" }} onClick={() => { setEmptyShowAdd(false); setEmptyName(""); setEmptyIsFolder(false); }}>
                  {t("common:cancel")}
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 8 }}>
                <button style={{ padding: "10px 24px", borderRadius: 8, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer" }} onClick={() => { setEmptyIsFolder(true); setEmptyShowAdd(true); }}>
                  {t("addFolder")}
                </button>
                <button style={{ padding: "10px 24px", borderRadius: 8, border: "none", backgroundColor: "var(--accent)", color: "#fff", fontSize: 14, fontWeight: 600, cursor: "pointer", opacity: 0.85 }} onClick={() => { setEmptyIsFolder(false); setEmptyShowAdd(true); }}>
                  {t("addSheet")}
                </button>
                <button style={{ padding: "10px 24px", borderRadius: 8, border: "1px solid var(--border-input)", backgroundColor: "transparent", color: "var(--text-primary)", fontSize: 14, cursor: "pointer" }} onClick={() => emptyFileInputRef.current?.click()}>
                  Import
                </button>
                <input ref={emptyFileInputRef} type="file" accept=".xlsx,.xls,.csv,.md" style={{ display: "none" }} onChange={handleImport} />
              </div>
            )
          )}
        </div>
        {/* 시트 선택 모달 (빈 프로젝트에서도 표시) */}
        {importFile && importSheets.length > 1 && (
          <div style={sheetModalStyles.overlay} onClick={() => { setImportFile(null); setImportSheets([]); }}>
            <div style={sheetModalStyles.panel} onClick={(e) => e.stopPropagation()}>
              <div style={sheetModalStyles.header}>
                <h3 style={sheetModalStyles.title}>{t("importSelectSheets")}</h3>
                <span style={sheetModalStyles.subtitle}>{importFile.name}</span>
              </div>
              <div style={sheetModalStyles.body}>
                <div style={sheetModalStyles.actions}>
                  <button style={sheetModalStyles.linkBtn} onClick={() => setSelectedSheets(new Set(importSheets.map((sh) => sh.name)))}>{t("common:selectAll")}</button>
                  <button style={sheetModalStyles.linkBtn} onClick={() => setSelectedSheets(new Set())}>{t("common:deselectAll")}</button>
                </div>
                {importSheets.map((sheet) => (
                  <label key={sheet.name} style={sheetModalStyles.sheetRow}>
                    <input type="checkbox" checked={selectedSheets.has(sheet.name)} onChange={(e) => { const next = new Set(selectedSheets); if (e.target.checked) { next.add(sheet.name); } else { next.delete(sheet.name); } setSelectedSheets(next); }} style={{ width: 16, height: 16 }} />
                    <span style={sheetModalStyles.sheetName}>{sheet.name}</span>
                    <span style={sheetModalStyles.sheetCount}>{t("tcCount", { count: sheet.tc_count })}</span>
                  </label>
                ))}
              </div>
              <div style={sheetModalStyles.footer}>
                <span style={sheetModalStyles.summary}>{t("sheetsSelected", { count: selectedSheets.size, tcCount: importSheets.filter((sh) => selectedSheets.has(sh.name)).reduce((a, sh) => a + sh.tc_count, 0) })}</span>
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={sheetModalStyles.cancelBtn} onClick={() => { setImportFile(null); setImportSheets([]); }}>{t("common:cancel")}</button>
                  <button style={{ ...sheetModalStyles.importBtn, opacity: selectedSheets.size === 0 || importLoading ? 0.5 : 1 }} disabled={selectedSheets.size === 0 || importLoading} onClick={handleImportConfirm}>
                    {importLoading ? t("importing") : t("importAction")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "calc(100vh - 160px)" }}>
      {/* 왼쪽: 시트 트리 사이드바 */}
      <SheetTreeSidebar
        sheets={sheets}
        flatSheets={flatSheets}
        activeSheet={activeSheet}
        setActiveSheet={setActiveSheet}
        expandedSheets={expandedSheets}
        setExpandedSheets={setExpandedSheets}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        canEditTC={canEditTC}
        projectId={projectId}
        onSheetChange={handleSheetChange}
      />

      {/* 오른쪽: 툴바 + 그리드 */}
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Toolbar */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          {canEditTC && (
            <>
              <button style={styles.btnPrimary} onClick={handleAddRow}>
                {t("addRow")}
              </button>
              <select
                style={styles.btnGhost}
                defaultValue="5"
                onChange={async (e) => {
                  const count = parseInt(e.target.value);
                  if (!count) return;
                  for (let i = 0; i < count; i++) await handleAddRow();
                  toast.success(t("rowsAdded", { count }));
                }}
              >
                <option value="1">{t("rowCount", { count: 1 })}</option>
                <option value="3">{t("rowCount", { count: 3 })}</option>
                <option value="5">{t("rowCount", { count: 5 })}</option>
                <option value="10">{t("rowCount", { count: 10 })}</option>
                <option value="20">{t("rowCount", { count: 20 })}</option>
                <option value="30">{t("rowCount", { count: 30 })}</option>
              </select>
              <button onClick={handleCloneSelected} disabled={!canEditTC || selectedCount === 0}
                style={styles.toolBtn ?? styles.btnGhost} title={t("cloneSelected")}>
                📋 {t("cloneSelected")}
              </button>
              <button style={styles.btnDanger} onClick={handleDeleteSelected}>
                {t("deleteSelected")}
              </button>
              <div style={styles.separator} />
              <button style={{ ...styles.btnGhost, opacity: undoCount === 0 ? 0.4 : 1 }} onClick={handleUndo} title="Ctrl+Z" disabled={undoCount === 0}>
                Undo
              </button>
              <button style={{ ...styles.btnGhost, opacity: redoCount === 0 ? 0.4 : 1 }} onClick={handleRedo} title="Ctrl+Y" disabled={redoCount === 0}>
                Redo
              </button>
              <button style={styles.btnGhost} onClick={handleAutoFillTcId}>
                {t("autoFillTcId")}
              </button>
              <button
                style={styles.btnGhost}
                onClick={() => {
                  const api = gridApiRef.current;
                  if (!api) return;
                  const selected = api.getSelectedRows() as TestCase[];
                  if (selected.length === 0) {
                    toast.error(t("selectRowsFirst"));
                    return;
                  }
                  setBulkOpen(true);
                }}
              >
                {t("bulkEdit")}
              </button>
              <div style={styles.separator} />
              <button style={styles.btnGhost} onClick={() => fileInputRef.current?.click()}>
                Import
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv,.md"
                style={{ display: "none" }}
                onChange={handleImport}
              />
            </>
          )}
          <button style={styles.btnGhost} onClick={() => setShowExportModal(true)}>
            Excel Export
          </button>
          <div style={styles.separator} />
          <button onClick={handleResultHistory} disabled={selectedCount !== 1}
            style={styles.btnGhost} title={t("resultHistory")}>
            📊 {t("resultHistory")}
          </button>
          <button
            style={styles.btnGhost}
            onClick={() => {
              const api = gridApiRef.current;
              if (!api) return;
              const selected = api.getSelectedRows() as TestCase[];
              if (selected.length === 1) {
                if (!selected[0].id) {
                  toast.error(t("savedTcOnly"));
                  return;
                }
                openHistory(selected[0]);
              } else {
                openProjectHistory();
              }
            }}
          >
            {t("changeHistory")}
          </button>
        </div>
        <div style={styles.toolbarRight}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <input
              style={styles.searchInput}
              type="text"
              placeholder={t("searchPlaceholder")}
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
              title={t("replace")}
            >
              {t("replace")}
            </button>
          </div>
          {canEditTC && replaceOpen && (
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <input
                style={{ ...styles.searchInput, width: 140 }}
                type="text"
                placeholder={t("replaceAllPlaceholder")}
                value={replaceText}
                onChange={(e) => setReplaceText(e.target.value)}
              />
              <button
                style={{ ...styles.btnPrimary, fontSize: 11, padding: "4px 10px", whiteSpace: "nowrap" }}
                onClick={handleReplaceAll}
                disabled={!searchText}
              >
                {t("replaceAllBtn")}
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
            title={t("advancedFilter")}
          >
            {filterConditions.length > 0 ? t("filterWithCount", { count: filterConditions.length }) : t("filter")}
          </button>
        </div>
      </div>

      {/* ── 고급 필터 패널 ── */}
      {showFilterPanel && (
        <div style={{ padding: "8px 12px", backgroundColor: "var(--bg-card)", borderBottom: "1px solid var(--border-color)", fontSize: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{t("filterCondition")}</span>
            <select
              style={{ fontSize: 11, padding: "2px 6px", borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)" }}
              value={filterLogic}
              onChange={(e) => setFilterLogic(e.target.value as "AND" | "OR")}
            >
              <option value="AND">{t("filterLogicAnd")}</option>
              <option value="OR">{t("filterLogicOr")}</option>
            </select>
            <button
              style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
              onClick={() => {
                setFilterConditions([...filterConditions, { field: "tc_id", operator: "contains", value: "" }]);
              }}
            >
              {t("addCondition")}
            </button>
            {filterConditions.length > 0 && (
              <>
                <button
                  style={{ ...styles.btnPrimary, fontSize: 11, padding: "3px 10px" }}
                  onClick={async () => {
                    try {
                      const data = await filtersApi.apply(projectId, filterConditions, filterLogic, activeSheet || undefined);
                      setRowData(data);
                      toast.success(t("filterApplied", { count: data.length }));
                    } catch {
                      toast.error(t("filterApplyFailed"));
                    }
                  }}
                >
                  {t("common:apply")}
                </button>
                <button
                  style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
                  onClick={() => {
                    setFilterConditions([]);
                    setActiveFilterName(null);
                    loadData();
                  }}
                >
                  {t("common:reset")}
                </button>
                {canEditTC && (
                  <button
                    style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
                    onClick={async () => {
                      const name = prompt(t("filterSavePrompt"), activeFilterName || "");
                      if (!name) return;
                      try {
                        await filtersApi.create(projectId, { name, conditions: filterConditions, logic: filterLogic });
                        toast.success(t("filterSaved", { name }));
                        setActiveFilterName(name);
                      } catch {
                        toast.error(t("filterSaveFailed"));
                      }
                    }}
                  >
                    {t("common:save")}
                  </button>
                )}
                <button
                  style={{ ...styles.btnGhost, fontSize: 11, padding: "2px 8px" }}
                  onClick={async () => {
                    try {
                      const saved = await filtersApi.list(projectId);
                      if (saved.length === 0) { toast(t("noSavedFilters")); return; }
                      const names = saved.map(f => f.name).join("\n");
                      const chosen = prompt(t("filterLoadPrompt", { names }));
                      if (!chosen) return;
                      const found = saved.find(f => f.name === chosen);
                      if (!found) { toast.error(t("filterNotFound")); return; }
                      setFilterConditions(found.conditions);
                      setFilterLogic(found.logic as "AND" | "OR");
                      setActiveFilterName(found.name);
                      toast.success(t("filterLoaded", { name: found.name }));
                    } catch {
                      toast.error(t("filterLoadFailed"));
                    }
                  }}
                >
                  {t("filterLoad")}
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
                  { v: "test_type", l: "Platform" }, { v: "test_steps", l: "Steps" },
                  { v: "expected_result", l: "Expected" }, { v: "remarks", l: "Remarks" }, { v: "precondition", l: "Precondition" },
                  { v: "sheet_name", l: "Sheet" },
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
                <option value="contains">{t("operator.contains")}</option>
                <option value="not_contains">{t("operator.notContains")}</option>
                <option value="eq">{t("operator.eq")}</option>
                <option value="neq">{t("operator.neq")}</option>
                <option value="empty">{t("operator.empty")}</option>
                <option value="not_empty">{t("operator.notEmpty")}</option>
              </select>
              {!["empty", "not_empty"].includes(cond.operator) && (
                <input
                  style={{ fontSize: 11, padding: "3px 6px", borderRadius: 4, border: "1px solid var(--border-input)", backgroundColor: "var(--bg-input)", color: "var(--text-primary)", width: 150 }}
                  placeholder={t("valuePlaceholder")}
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
            {t("common:loadingData")}
          </div>
        ) : (
          <AgGridReact
            ref={gridRef}
            rowData={rowData}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            localeText={gridLocale}
            rowSelection={{ mode: "multiRow", checkboxes: true, headerCheckbox: true, selectAll: "filtered" }}
            onGridReady={onGridReady}
            onCellValueChanged={onCellValueChanged}
            onCellKeyDown={onCellKeyDown}
            onSelectionChanged={() => setSelectedCount(gridApiRef.current?.getSelectedRows().length || 0)}
            context={{ jiraBaseUrl: project.jira_base_url, searchKeyword: searchText }}
            animateRows={true}
            rowDragManaged={true}
            onRowDragEnd={handleRowDragEnd}
            singleClickEdit={true}
            stopEditingWhenCellsLoseFocus={true}
            getRowId={(params) =>
              params.data.id ? String(params.data.id) : `new_${params.data.no}`
            }
          />
        )}
      </div>
      {/* 하단 상태바 */}
      {selectedCount > 0 && (
        <div style={{ padding: "4px 12px", fontSize: 12, color: "var(--text-secondary)", backgroundColor: "var(--bg-card)", borderTop: "1px solid var(--border-color)", display: "flex", gap: 12 }}>
          <span><strong>{selectedCount}</strong> {t("selectedRows", { count: selectedCount })}</span>
          <span>{t("totalRows", { count: rowData.length })}</span>
        </div>
      )}
      {/* Bulk Edit Modal */}
      {bulkOpen && (
        <div style={historyStyles.overlay} onClick={() => setBulkOpen(false)}>
          <div
            style={{ ...historyStyles.panel, width: 400, maxHeight: "auto" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={historyStyles.header}>
              <h3 style={historyStyles.title}>
                {t("bulkEditTitle", { count: gridApiRef.current?.getSelectedRows().length || 0 })}
              </h3>
              <button style={historyStyles.closeBtn} onClick={() => setBulkOpen(false)}>✕</button>
            </div>
            <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4, display: "block" }}>
                  {t("bulkEditColumn")}
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
                  {t("bulkEditValue")}
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
                    <option value="">{t("selectOption")}</option>
                    {BULK_FIELDS.find((f) => f.field === bulkField)!.options!.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={bulkValue}
                    onChange={(e) => setBulkValue(e.target.value)}
                    placeholder={t("bulkEditValuePlaceholder")}
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
                {t("common:apply")}
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
                  ? t("projectHistoryTitle")
                  : t("historyTitle", { tcId: historyTc.tc_id || `No.${historyTc.no}` })}
              </h3>
              <button style={historyStyles.closeBtn} onClick={() => setHistoryTc(null)}>
                ✕
              </button>
            </div>
            <div style={historyStyles.body}>
              {historyLoading ? (
                <div style={historyStyles.empty}>{t("common:loadingData")}</div>
              ) : historyData.length === 0 ? (
                <div style={historyStyles.empty}>{t("noHistory")}</div>
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
                          <th style={historyStyles.th}>{t("historyLastModified")}</th>
                          <th style={historyStyles.th}>{t("historyChanger")}</th>
                          <th style={historyStyles.th}>{t("historyChangeCount")}</th>
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
                              {new Date(e.lastDate).toLocaleString(i18n.language === "ko" ? "ko-KR" : "en-US", {
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
                      <th style={historyStyles.th}>{t("historyDatetime")}</th>
                      <th style={historyStyles.th}>{t("historyChangerName")}</th>
                      <th style={historyStyles.th}>{t("historyField")}</th>
                      <th style={historyStyles.th}>{t("historyOldValue")}</th>
                      <th style={historyStyles.th}>{t("historyNewValue")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historyData.map((h) => (
                      <tr key={h.id}>
                        <td style={historyStyles.td}>
                          {new Date(h.changed_at).toLocaleString(i18n.language === "ko" ? "ko-KR" : "en-US", {
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

      {/* ── 결과 히스토리 모달 ── */}
      {resultHistoryOpen && (
        <div style={historyStyles.overlay} onClick={() => setResultHistoryOpen(false)}>
          <div style={historyStyles.panel} onClick={e => e.stopPropagation()}>
            <div style={historyStyles.header}>
              <h3 style={historyStyles.title}>{t("resultHistoryModalTitle", { tcId: resultHistoryTcId })}</h3>
              <button onClick={() => setResultHistoryOpen(false)} style={historyStyles.closeBtn}>✕</button>
            </div>
            <div style={historyStyles.body}>
              {resultHistory.length === 0 ? (
                <p style={{ color: "var(--text-secondary)", textAlign: "center", padding: 20 }}>{t("noResultHistory")}</p>
              ) : (
                <table style={historyStyles.table}>
                  <thead>
                    <tr>
                      <th style={historyStyles.th}>{t("resultRun")}</th>
                      <th style={historyStyles.th}>{t("resultVersion")}</th>
                      <th style={{ ...historyStyles.th, textAlign: "center" }}>{t("resultRound")}</th>
                      <th style={{ ...historyStyles.th, textAlign: "center" }}>{t("resultResult")}</th>
                      <th style={historyStyles.th}>{t("resultActual")}</th>
                      <th style={historyStyles.th}>{t("resultDate")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultHistory.map((h, i) => (
                      <tr key={h.result_id} style={{
                        borderBottom: "1px solid var(--border-color)",
                        backgroundColor: i % 2 === 0 ? "var(--bg-secondary)" : "transparent",
                      }}>
                        <td style={historyStyles.td}>{h.run_name}</td>
                        <td style={historyStyles.td}>{h.version || "-"}</td>
                        <td style={{ ...historyStyles.td, textAlign: "center" }}>R{h.round}</td>
                        <td style={{ ...historyStyles.td, textAlign: "center" }}>
                          <span style={{
                            padding: "2px 8px", borderRadius: 4, fontWeight: 600, fontSize: 12,
                            backgroundColor:
                              h.result === "PASS" ? "rgba(26,127,55,0.15)" :
                              h.result === "FAIL" ? "rgba(207,34,46,0.15)" :
                              h.result === "BLOCK" ? "rgba(191,135,0,0.15)" : "rgba(128,128,128,0.15)",
                            color:
                              h.result === "PASS" ? "#1a7f37" :
                              h.result === "FAIL" ? "#cf222e" :
                              h.result === "BLOCK" ? "#bf8700" : "#666",
                          }}>{h.result}</span>
                        </td>
                        <td style={{ ...historyStyles.td, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {h.actual_result || "-"}
                        </td>
                        <td style={{ ...historyStyles.td, fontSize: 12, color: "var(--text-secondary)" }}>
                          {h.run_created_at ? new Date(h.run_created_at).toLocaleDateString("ko-KR") : "-"}
                        </td>
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
              <h3 style={sheetModalStyles.title}>{t("importSelectSheets")}</h3>
              <span style={sheetModalStyles.subtitle}>{importFile.name}</span>
            </div>
            <div style={sheetModalStyles.body}>
              <div style={sheetModalStyles.actions}>
                <button
                  style={sheetModalStyles.linkBtn}
                  onClick={() => setSelectedSheets(new Set(importSheets.map((s) => s.name)))}
                >
                  {t("common:selectAll")}
                </button>
                <button
                  style={sheetModalStyles.linkBtn}
                  onClick={() => setSelectedSheets(new Set())}
                >
                  {t("common:deselectAll")}
                </button>
              </div>
              {importSheets.map((sheet) => (
                <label key={sheet.name} style={sheetModalStyles.sheetRow}>
                  <input
                    type="checkbox"
                    checked={selectedSheets.has(sheet.name)}
                    onChange={(e) => {
                      const next = new Set(selectedSheets);
                      if (e.target.checked) { next.add(sheet.name); } else { next.delete(sheet.name); }
                      setSelectedSheets(next);
                    }}
                    style={{ width: 16, height: 16 }}
                  />
                  <span style={sheetModalStyles.sheetName}>{sheet.name}</span>
                  <span style={sheetModalStyles.sheetCount}>{t("tcCount", { count: sheet.tc_count })}</span>
                  {sheet.existing > 0 && (
                    <span style={{ fontSize: 11, color: "#DC2626", fontWeight: 600 }}>
                      {t("existingOverwrite", { count: sheet.existing })}
                    </span>
                  )}
                </label>
              ))}
            </div>
            <div style={sheetModalStyles.footer}>
              <span style={sheetModalStyles.summary}>
                {t("sheetsSelected", { count: selectedSheets.size, tcCount: importSheets.filter((s) => selectedSheets.has(s.name)).reduce((a, s) => a + s.tc_count, 0) })}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  style={sheetModalStyles.cancelBtn}
                  onClick={() => { setImportFile(null); setImportSheets([]); }}
                >
                  {t("common:cancel")}
                </button>
                <button
                  style={{ ...sheetModalStyles.importBtn, opacity: selectedSheets.size === 0 || importLoading ? 0.5 : 1 }}
                  disabled={selectedSheets.size === 0 || importLoading}
                  onClick={handleImportConfirm}
                >
                  {importLoading ? t("importing") : t("importAction")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Excel Export 옵션 모달 ── */}
      {showExportModal && (
        <div style={sheetModalStyles.overlay} onClick={() => setShowExportModal(false)}>
          <div style={{ ...sheetModalStyles.panel, maxWidth: 360 }} onClick={(e) => e.stopPropagation()}>
            <div style={sheetModalStyles.header}>
              <h3 style={sheetModalStyles.title}>Excel Export</h3>
            </div>
            <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 14, color: "var(--text-primary)" }}>
                <input type="radio" name="exportMode" checked={!exportSplit} onChange={() => setExportSplit(false)} />
                시트 통합 (단일 시트)
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 14, color: "var(--text-primary)" }}>
                <input type="radio" name="exportMode" checked={exportSplit} onChange={() => setExportSplit(true)} />
                시트 분리 (시트별 탭)
              </label>
            </div>
            <div style={{ padding: "12px 20px", display: "flex", justifyContent: "flex-end", gap: 8, borderTop: "1px solid var(--border)" }}>
              <button
                onClick={() => setShowExportModal(false)}
                style={{ padding: "6px 16px", borderRadius: 6, border: "1px solid var(--border)", background: "var(--bg-card)", color: "var(--text-primary)", fontSize: 13, cursor: "pointer" }}
              >
                취소
              </button>
              <button
                onClick={handleExport}
                style={{ padding: "6px 16px", borderRadius: 6, border: "none", background: "#3182f6", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer" }}
              >
                다운로드
              </button>
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
