import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 시트 조회 실패를 빈 프로젝트로 보이면 사용자는 데이터가 사라졌다고 받아들인다.

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

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testCasesApi.list).mockResolvedValue([{ id: 1, tc_id: "TC-001", sheet_name: "기본", no: 1 }] as any);
});

describe("시트 목록 조회 실패", () => {
  it("빈 프로젝트 안내 대신 실패와 다시 시도를 보인다", async () => {
    vi.mocked(testCasesApi.listSheets).mockRejectedValueOnce(new Error("500"));
    vi.mocked(testCasesApi.listSheets).mockResolvedValue([
      { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 1, children: [] },
    ] as any);
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("시트 목록을 불러오지 못했습니다");
    expect(screen.queryByText("폴더나 시트를 추가하여 테스트 케이스를 관리하세요.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("다시 시도"));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(testCasesApi.listSheets).toHaveBeenCalledTimes(2);
  });
});
