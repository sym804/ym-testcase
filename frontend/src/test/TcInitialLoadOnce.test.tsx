import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// 처음 열 때 TC 목록을 한 번만 받는다. loadData 가 flatSheets 에 의존해서, 시트 목록과
// 함께 보내면 시트가 도착하는 순간 같은 목록을 한 번 더 받았다(요청 2회).

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">{props.rowData?.length ?? 0}</div>
  ),
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

const sheet = (id: number, name: string) =>
  ({ id, name, parent_id: null, sort_order: id, is_folder: false, tc_count: 1, children: [] });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testCasesApi.list).mockResolvedValue([
    { id: 1, tc_id: "TC-001", sheet_name: "B", no: 1 },
    { id: 2, tc_id: "TC-002", sheet_name: "A", no: 1 },
  ] as any);
});

describe("TC 관리 첫 로딩", () => {
  it("시트가 여럿이면 전체 목록을 한 번만 받는다", async () => {
    vi.mocked(testCasesApi.listSheets).mockResolvedValue([sheet(1, "A"), sheet(2, "B")] as any);
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);

    await waitFor(() => expect(screen.getByTestId("ag-grid")).toHaveTextContent("2"));
    // 효과가 다시 돌 시간을 준다
    await new Promise((r) => setTimeout(r, 50));
    expect(testCasesApi.list).toHaveBeenCalledTimes(1);
    expect(vi.mocked(testCasesApi.list).mock.calls[0][1]).toEqual({});
  });

  it("시트가 하나면 그 시트로 한 번만 받는다", async () => {
    vi.mocked(testCasesApi.listSheets).mockResolvedValue([sheet(1, "A")] as any);
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);

    await waitFor(() => expect(testCasesApi.list).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 50));
    expect(testCasesApi.list).toHaveBeenCalledTimes(1);
    expect(vi.mocked(testCasesApi.list).mock.calls[0][1]).toEqual({ sheet_name: "A" });
  });

  it("시트 목록이 실패해도 TC 목록은 받는다", async () => {
    vi.mocked(testCasesApi.listSheets).mockRejectedValue(new Error("500"));
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);

    await waitFor(() => expect(testCasesApi.list).toHaveBeenCalledTimes(1));
  });
});
