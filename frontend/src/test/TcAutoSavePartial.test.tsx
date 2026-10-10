import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor, act, fireEvent, screen } from "@testing-library/react";

// 자동저장은 바뀐 칸만 보내고, 같은 행의 저장은 앞 요청이 끝난 뒤 보낸다.
// 행 전체를 보내면 다른 사람이 그 사이 고친 칸을 옛 값으로 되돌린다.

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

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testCasesApi: {
    list: vi.fn(), create: vi.fn(), update: vi.fn(), bulkDelete: vi.fn(),
    listSheets: vi.fn(), createSheet: vi.fn(), deleteSheet: vi.fn(),
    previewImport: vi.fn(), importExcel: vi.fn(), exportExcel: vi.fn(),
    bulkUpdate: vi.fn(), delete: vi.fn(), restore: vi.fn(),
  },
  historyApi: { getTestCaseHistory: vi.fn(), getProjectHistory: vi.fn() },
}));

import { testCasesApi } from "../api";
import TestCaseGrid from "../components/TestCaseGrid";

const adminProject = {
  id: 1, name: "TestProject", description: "desc", jira_base_url: null,
  is_private: false, created_by: 1, created_at: "2026-01-01",
  updated_at: "2026-01-01", my_role: "admin" as const,
};

const tcRow = {
  id: 5, project_id: 1, no: 1, tc_id: "TC-001", type: "", category: "로그인", depth1: "", depth2: "",
  priority: "보통", test_type: "Web", precondition: "", test_steps: "절차", expected_result: "결과",
  r1: "", r2: "", r3: "", remarks: "", sheet_name: "기본", custom_fields: {},
  created_at: "2026-01-01", updated_at: "2026-01-01",
};

beforeEach(() => {
  vi.clearAllMocks();
  gridProps = null;
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 1, children: [] },
  ] as any);
  vi.mocked(testCasesApi.list).mockResolvedValue([{ ...tcRow, custom_fields: {} }] as any);
});

async function loaded() {
  render(<TestCaseGrid projectId={1} project={adminProject as any} />);
  await waitFor(() => expect(gridProps?.rowData?.length).toBe(1), { timeout: 5000 });
  return gridProps.rowData[0];
}

const edit = (data: any, field: string, value: unknown) => {
  const oldValue = data[field];
  data[field] = value;
  act(() => gridProps.onCellValueChanged({ data, oldValue, newValue: value, colDef: { field }, column: { getColId: () => field } }));
};

describe("TC 자동저장", () => {
  it("바뀐 칸만 보낸다", { timeout: 20000 }, async () => {
    vi.mocked(testCasesApi.update).mockResolvedValue({} as any);
    const data = await loaded();

    edit(data, "priority", "높음");

    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(1), { timeout: 5000 });
    expect(vi.mocked(testCasesApi.update).mock.calls[0][2]).toEqual({ priority: "높음" });
  });

  it("같은 행의 다음 저장은 앞 요청이 끝난 뒤 보낸다", { timeout: 20000 }, async () => {
    let release!: () => void;
    vi.mocked(testCasesApi.update)
      .mockImplementationOnce(() => new Promise((r) => { release = () => r({} as any); }))
      .mockResolvedValue({} as any);
    const data = await loaded();

    edit(data, "priority", "높음");
    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(1), { timeout: 5000 });
    edit(data, "remarks", "메모");
    await new Promise((r) => setTimeout(r, 600));
    expect(testCasesApi.update).toHaveBeenCalledTimes(1);

    release();
    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(2), { timeout: 5000 });
    expect(vi.mocked(testCasesApi.update).mock.calls[1][2]).toEqual({ remarks: "메모" });
  });

  it("커스텀 필드만 바꿔도 저장한다", { timeout: 20000 }, async () => {
    vi.mocked(testCasesApi.update).mockResolvedValue({} as any);
    const data = await loaded();

    // 커스텀 필드 편집기는 행의 custom_fields 객체를 직접 고친다
    data.custom_fields.env = "stage";
    act(() => gridProps.onCellValueChanged({ data, oldValue: "", newValue: "stage", colDef: { field: "cf_env" }, column: { getColId: () => "cf_env" } }));

    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(1), { timeout: 5000 });
    expect(vi.mocked(testCasesApi.update).mock.calls[0][2]).toEqual({ custom_fields: { env: "stage" } });
  });

  it("저장 전에 행 목록이 바뀌어도 그 편집을 저장한다", { timeout: 20000 }, async () => {
    vi.mocked(testCasesApi.update).mockResolvedValue({} as any);
    vi.mocked(testCasesApi.create).mockImplementation(async (_pid: number, row: any) => ({ ...row, id: 99 }) as any);
    const data = await loaded();

    // 편집하고 0.3초 저장 전에 행을 추가해 rowData 를 바꾼다
    edit(data, "remarks", "편집");
    fireEvent.click(screen.getByText("+ 행 추가"));
    await waitFor(() => expect(gridProps.rowData.length).toBe(2), { timeout: 5000 });

    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(1), { timeout: 5000 });
    expect(vi.mocked(testCasesApi.update).mock.calls[0][2]).toEqual({ remarks: "편집" });
  });

  it("앞 저장이 거부되면 그 칸만 되돌리고, 그 사이 고친 다른 칸은 남겨 저장한다", { timeout: 20000 }, async () => {
    let reject!: (e: unknown) => void;
    vi.mocked(testCasesApi.update)
      .mockImplementationOnce(() => new Promise((_, rj) => { reject = rj; }))
      .mockResolvedValue({} as any);
    const data = await loaded();
    // 저장 거부 때 행을 되돌리는 경로가 그리드 API 로 행을 찾는다
    act(() => gridProps.onGridReady({ api: {
      getRowNode: (id: string) => (id === String(data.id) ? { data } : undefined),
      refreshCells: () => {}, forEachNode: () => {},
    } }));

    edit(data, "priority", "높음");
    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(1), { timeout: 5000 });
    edit(data, "remarks", "메모");
    await new Promise((r) => setTimeout(r, 400));   // 두 번째 저장이 앞 요청 뒤에 줄을 선다
    reject({ response: { data: { detail: "거부" } } });

    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(2), { timeout: 5000 });
    expect(vi.mocked(testCasesApi.update).mock.calls[1][2]).toEqual({ remarks: "메모" });
    expect(data.priority).toBe("보통");
    expect(data.remarks).toBe("메모");
  });

  it("커스텀 칸 A 저장이 거부돼도 그 사이 고친 커스텀 칸 B 는 남겨 저장한다", { timeout: 20000 }, async () => {
    let reject!: (e: unknown) => void;
    vi.mocked(testCasesApi.update)
      .mockImplementationOnce(() => new Promise((_, rj) => { reject = rj; }))
      .mockResolvedValue({} as any);
    const data = await loaded();
    act(() => gridProps.onGridReady({ api: {
      getRowNode: (id: string) => (id === String(data.id) ? { data } : undefined),
      refreshCells: () => {}, forEachNode: () => {},
    } }));
    const editCf = (k: string, v: string) => {
      data.custom_fields[k] = v;
      act(() => gridProps.onCellValueChanged({ data, oldValue: "", newValue: v, colDef: { field: `cf_${k}` }, column: { getColId: () => `cf_${k}` } }));
    };

    editCf("a", "A1");
    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(1), { timeout: 5000 });
    editCf("b", "B1");
    await new Promise((r) => setTimeout(r, 400));
    reject({ response: { data: { detail: "거부" } } });

    await waitFor(() => expect(testCasesApi.update).toHaveBeenCalledTimes(2), { timeout: 5000 });
    expect(data.custom_fields).toEqual({ b: "B1" });
    expect(vi.mocked(testCasesApi.update).mock.calls[1][2]).toEqual({ custom_fields: { b: "B1" } });
  });
});

