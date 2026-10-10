import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 보기 전용(viewer, 완료된 수행)에서 결과를 바꾸는 경로가 닫혀 있는지,
// Ctrl+Z 가 직전 조작 하나를 되돌리는지 본다.
let gridProps: any = null;

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => {
    gridProps = props;
    return <div data-testid="ag-grid">{props.rowData?.length ?? 0}</div>;
  },
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: () => {} },
}));

vi.mock("react-hot-toast", () => {
  const fn: any = vi.fn();
  fn.success = vi.fn();
  fn.error = vi.fn();
  return { default: fn };
});

vi.mock("../components/MarkdownCell", () => ({ default: (p: any) => <span>{p.value}</span> }));
vi.mock("../components/HighlightCell", () => ({ default: (p: any) => <span>{p.value}</span> }));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(), create: vi.fn(), getOne: vi.fn(), update: vi.fn(),
    submitResults: vi.fn(), complete: vi.fn(), reopen: vi.fn(),
    clone: vi.fn(), delete: vi.fn(), exportExcel: vi.fn(),
  },
  testCasesApi: { listSheets: vi.fn() },
  attachmentsApi: { list: vi.fn(), listByRun: vi.fn(), upload: vi.fn(), delete: vi.fn(), downloadUrl: vi.fn() },
}));

import { testRunsApi, testCasesApi, attachmentsApi } from "../api";
import { TestRunStatus } from "../types";
import TestRunManager from "../components/TestRunManager";

const project = (role: string) => ({
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: role,
});

const tc = (id: number) => ({
  id, project_id: 1, no: id, tc_id: `TC-00${id}`, type: "", category: "", depth1: "", depth2: "",
  priority: "보통", test_type: "", precondition: "", test_steps: "", expected_result: "",
  r1: "", r2: "", r3: "", issue_link: "", assignee: "", remarks: "", sheet_name: "기본",
  created_at: "2026-01-01", updated_at: "2026-01-01",
});

const run = (status: TestRunStatus) => ({
  id: 7, project_id: 1, name: "회귀", version: "v1", environment: "dev",
  round: 1, status, sheet_names: null, created_by: 1, created_at: "2026-01-01",
});

const rowsFor = () => [1, 2].map((i) => ({
  id: 70 + i, test_run_id: 7, test_case_id: i, result: "", actual_result: "",
  issue_link: "", remarks: "", executed_by: 1, executed_at: null, test_case: tc(i),
}));

/** 그리드 API 대역. 행 노드와 포커스, 선택만 흉내 낸다. */
function fakeApi(rows: any[], focusedIndex: number, selected: number[]) {
  const nodes = rows.map((data, rowIndex) => ({ data, rowIndex }));
  return {
    nodes,
    getFocusedCell: () => ({ rowIndex: focusedIndex, column: { getColId: () => "result" } }),
    getDisplayedRowAtIndex: (i: number) => nodes[i],
    getDisplayedRowCount: () => nodes.length,
    setFocusedCell: vi.fn(),
    refreshCells: vi.fn(),
    forEachNode: (cb: (n: any) => void) => nodes.forEach(cb),
    forEachNodeAfterFilterAndSort: (cb: (n: any) => void) => nodes.forEach(cb),
    getSelectedNodes: () => selected.map((i) => nodes[i]),
    getEditingCells: () => [] as unknown[],
    getRowNode: (id: string) => nodes.find((n) => String(n.data.id) === id),
  };
}

const key = (k: string, extra: Partial<KeyboardEvent> = {}) => ({
  event: { key: k, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, preventDefault: vi.fn(), ...extra },
  column: { getColId: () => "result" },
  node: null,
});

beforeEach(() => {
  vi.clearAllMocks();
  gridProps = null;
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 2, children: [] },
  ] as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
  vi.mocked(testRunsApi.submitResults).mockResolvedValue([] as any);
});

async function openRun(role: string, status: TestRunStatus) {
  const rows = rowsFor();
  vi.mocked(testRunsApi.list).mockResolvedValue([run(status)] as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue({ ...run(status), results: rows } as any);
  const user = userEvent.setup();
  render(<TestRunManager projectId={1} project={project(role) as any} />);
  // 완료된 수행만 든 버전 묶음은 접혀서 열린다
  if (status === TestRunStatus.COMPLETED) {
    const tree = await screen.findByTestId("run-tree");
    await user.click(await waitFor(() => tree.querySelector('button[aria-expanded="false"]') as HTMLElement));
  }
  await user.click(await screen.findByText("회귀"));
  await waitFor(() => expect(gridProps?.rowData?.length).toBe(2), { timeout: 5000 });
  return { user, rows: gridProps.rowData as any[] };
}

const editableOf = (field: string) => gridProps.columnDefs.find((c: any) => c.field === field)?.editable;

describe("수행 화면 보기 전용", () => {
  it.each([
    ["viewer", TestRunStatus.IN_PROGRESS],
    ["admin", TestRunStatus.COMPLETED],
  ])("%s / %s 에서는 편집 칸, 단축키, 일괄 입력이 닫힌다", async (role, status) => {
    const { rows } = await openRun(role, status);
    for (const f of ["actual_result", "issue_link", "remarks"]) expect(editableOf(f)).toBe(false);
    expect(screen.queryByText("결과 일괄입력 ▾")).not.toBeInTheDocument();

    const api = fakeApi(rows, 0, [0, 1]);
    act(() => gridProps.onGridReady({ api }));
    act(() => gridProps.onCellKeyDown(key("p")));
    act(() => gridProps.onCellKeyDown(key("d", { ctrlKey: true })));

    expect(rows[0].result).toBe("");
    expect(testRunsApi.submitResults).not.toHaveBeenCalled();
  });

  it("진행 중 수행의 tester 는 편집할 수 있다", async () => {
    await openRun("tester", TestRunStatus.IN_PROGRESS);
    for (const f of ["actual_result", "issue_link", "remarks"]) expect(editableOf(f)).toBe(true);
    expect(screen.getByText("결과 일괄입력 ▾")).toBeInTheDocument();
  });
});

describe("수행 화면 Ctrl+Z", () => {
  it("일괄 입력 직후 되돌리면 그 행들만 되돌리고 앞서 단축키로 넣은 행은 둔다", async () => {
    const { user, rows } = await openRun("admin", TestRunStatus.IN_PROGRESS);
    const api = fakeApi(rows, 0, [1]);
    act(() => gridProps.onGridReady({ api }));

    act(() => gridProps.onCellKeyDown(key("p")));          // 행 1 = PASS
    expect(rows[0].result).toBe("PASS");
    await user.click(screen.getByText("결과 일괄입력 ▾"));
    await user.click(screen.getByRole("button", { name: "FAIL" }));  // 선택한 행 2 = FAIL
    expect(rows[1].result).toBe("FAIL");
    vi.mocked(testRunsApi.submitResults).mockClear();

    act(() => gridProps.onCellKeyDown(key("z", { ctrlKey: true })));

    expect(rows[1].result).toBe("");
    expect(rows[0].result).toBe("PASS");
    await waitFor(() => expect(testRunsApi.submitResults).toHaveBeenCalledTimes(1));
    const sent = vi.mocked(testRunsApi.submitResults).mock.calls[0][2] as any[];
    expect(sent.map((r) => r.test_case_id)).toEqual([2]);
  });

  it("셀 편집기 안에서는 Ctrl+Z 를 가로채지 않는다", async () => {
    const { rows } = await openRun("admin", TestRunStatus.IN_PROGRESS);
    const api = fakeApi(rows, 0, []);
    api.getEditingCells = () => [{}];
    act(() => gridProps.onGridReady({ api }));
    act(() => gridProps.onCellKeyDown(key("p")));
    const ev = key("z", { ctrlKey: true });

    act(() => gridProps.onCellKeyDown(ev));

    expect(ev.event.preventDefault).not.toHaveBeenCalled();
    expect(rows[0].result).toBe("PASS");
  });
});

describe("수행 화면 QA 지적 회귀", () => {
  it("완료된 수행에서는 끌어 놓은 이미지도 올리지 않는다", async () => {
    const { rows } = await openRun("admin", TestRunStatus.COMPLETED);
    act(() => gridProps.onGridReady({ api: fakeApi(rows, 0, []) }));
    const grid = document.querySelector(".ag-theme-alpine") as HTMLElement;
    const file = new File(["x"], "a.png", { type: "image/png" });

    fireEvent.drop(grid, { dataTransfer: { files: [file] } });
    await new Promise((r) => setTimeout(r, 50));

    expect(attachmentsApi.upload).not.toHaveBeenCalled();
  });

  it("저장이 거부되면 되돌리기 기록을 비운다", async () => {
    const { rows } = await openRun("admin", TestRunStatus.IN_PROGRESS);
    act(() => gridProps.onGridReady({ api: fakeApi(rows, 0, []) }));
    vi.mocked(testRunsApi.submitResults).mockRejectedValueOnce({ response: { data: { detail: "다른 사용자가 먼저 저장했습니다." } } });
    act(() => gridProps.onCellKeyDown(key("b")));
    await waitFor(() => expect(testRunsApi.submitResults).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 20));

    act(() => gridProps.onCellKeyDown(key("z", { ctrlKey: true })));

    expect(testRunsApi.submitResults).toHaveBeenCalledTimes(1);
  });
});

