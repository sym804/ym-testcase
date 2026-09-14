import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";

// 커스텀 필드 컬럼은 field 가 `cf_<이름>` 이고 값은 valueGetter/valueSetter 로
// data.custom_fields[이름] 을 읽고 쓴다. 그런데 Ctrl+D 채우기와 undo/redo 는
// `node.data[field]` 라는 최상위 속성에 바로 대입해서, 화면 값이 안 바뀌고
// 저장 페이로드의 `cf_이름` 키는 백엔드 스키마에 없어 조용히 버려졌다.
// 그런데도 "N개 채움" 토스트는 떴다(SYM-26 과 같은 유형).
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
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

vi.mock("../components/MarkdownCell", () => ({ default: (p: any) => <span>{p.value}</span> }));
vi.mock("../components/HighlightCell", () => ({ default: (p: any) => <span>{p.value}</span> }));
vi.mock("../components/PreconditionCell", () => ({ default: (p: any) => <span>{p.value}</span> }));

vi.mock("../api", () => ({
  testCasesApi: {
    list: vi.fn(), create: vi.fn(), update: vi.fn(), bulkDelete: vi.fn(),
    listSheets: vi.fn(), createSheet: vi.fn(), deleteSheet: vi.fn(),
    previewImport: vi.fn(), importExcel: vi.fn(), exportExcel: vi.fn(),
    bulkUpdate: vi.fn(), delete: vi.fn(), restore: vi.fn(), bulkClone: vi.fn(),
  },
  historyApi: { getTestCaseHistory: vi.fn(), getProjectHistory: vi.fn() },
  customFieldsApi: { list: vi.fn() },
}));

import { testCasesApi, customFieldsApi } from "../api";
import TestCaseGrid from "../components/TestCaseGrid";

const adminProject = {
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin" as const,
};

function tc(id: number, env: string | null) {
  return {
    id, project_id: 1, no: id, tc_id: `TC-00${id}`, type: "", category: "",
    depth1: "", depth2: "", priority: "보통", test_type: "Web", precondition: "",
    test_steps: "1. 실행", expected_result: "성공", r1: "", r2: "", r3: "",
    issue_link: "", remarks: "", sheet_name: "기본",
    custom_fields: env === null ? null : { 환경: env },
    created_at: "2026-01-01", updated_at: "2026-01-01",
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  gridProps = null;
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 2, children: [] },
  ] as any);
  vi.mocked(testCasesApi.list).mockResolvedValue([tc(1, "운영"), tc(2, null)] as any);
  vi.mocked(testCasesApi.update).mockResolvedValue({} as any);
  vi.mocked(customFieldsApi.list).mockResolvedValue([
    { id: 10, project_id: 1, field_name: "환경", field_type: "text", options: null, sort_order: 0, is_required: false, created_at: "2026-01-01" },
  ] as any);
});

describe("커스텀 필드 컬럼의 Ctrl+D 채우기", () => {
  it("값이 custom_fields 에 들어가고 저장까지 간다", async () => {
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(gridProps?.onCellKeyDown).toBeTypeOf("function"));

    const source = { data: tc(1, "운영") };
    const target = { data: tc(2, null) };
    const api = {
      getSelectedNodes: () => [source, target],
      getSelectedRows: () => [source.data, target.data],
      forEachNode: (cb: (n: any) => void) => { cb(source); cb(target); },
      forEachNodeAfterFilterAndSort: (cb: (n: any) => void) => { cb(source); cb(target); },
      refreshCells: vi.fn(),
      setGridOption: vi.fn(),
    };
    gridProps.onGridReady?.({ api });

    gridProps.onCellKeyDown({
      event: { key: "d", ctrlKey: true, preventDefault: () => {} },
      column: { getColId: () => "cf_환경" },
      value: "운영",
      node: source,
      api,
    });

    expect(
      target.data.custom_fields?.["환경"],
      "최상위 속성에만 써서 화면 값이 안 바뀐다",
    ).toBe("운영");

    await waitFor(() => {
      expect(testCasesApi.update).toHaveBeenCalled();
    }, { timeout: 3000 });

    const sent = vi.mocked(testCasesApi.update).mock.calls.at(-1)?.[2] as any;
    expect(sent.custom_fields?.["환경"], "저장 페이로드에 값이 없다").toBe("운영");
  });

  it("일반 컬럼은 종전대로 최상위 속성에 채운다", async () => {
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(gridProps?.onCellKeyDown).toBeTypeOf("function"));

    const source = { data: tc(1, "운영") };
    const target = { data: tc(2, null) };
    const api = {
      getSelectedNodes: () => [source, target],
      getSelectedRows: () => [source.data, target.data],
      forEachNode: (cb: (n: any) => void) => { cb(source); cb(target); },
      forEachNodeAfterFilterAndSort: (cb: (n: any) => void) => { cb(source); cb(target); },
      refreshCells: vi.fn(),
      setGridOption: vi.fn(),
    };
    gridProps.onGridReady?.({ api });

    gridProps.onCellKeyDown({
      event: { key: "d", ctrlKey: true, preventDefault: () => {} },
      column: { getColId: () => "category" },
      value: "결제",
      node: source,
      api,
    });

    expect(target.data.category).toBe("결제");
  });
});
