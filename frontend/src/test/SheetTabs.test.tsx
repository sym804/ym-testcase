import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">{JSON.stringify(props.rowData?.length ?? 0)}</div>
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
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    bulkDelete: vi.fn(),
    listSheets: vi.fn(),
    createSheet: vi.fn(),
    deleteSheet: vi.fn(),
    previewImport: vi.fn(),
    importExcel: vi.fn(),
    exportExcel: vi.fn(),
    bulkUpdate: vi.fn(),
    delete: vi.fn(),
    restore: vi.fn(),
  },
  historyApi: {
    getTestCaseHistory: vi.fn(),
    getProjectHistory: vi.fn(),
  },
}));

import { testCasesApi } from "../api";
import TestCaseGrid from "../components/TestCaseGrid";

const adminProject = {
  id: 1,
  name: "TestProject",
  description: "desc",
  jira_base_url: null,
  is_private: false,
  created_by: 1,
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
  my_role: "admin" as const,
};

beforeEach(() => {
  vi.clearAllMocks();
});

function setupSheets(
  sheets: { name: string; tc_count: number }[],
  rows: any[] = []
) {
  vi.mocked(testCasesApi.listSheets).mockResolvedValue(sheets);
  vi.mocked(testCasesApi.list).mockResolvedValue(rows);
}

function renderGrid(project = adminProject) {
  return render(
    <TestCaseGrid projectId={project.id} project={project} />
  );
}

describe("SheetTabs", () => {
  it("시트 1개 + 이름 '기본' → 탭 바가 보이지 않는다", async () => {
    setupSheets([{ name: "기본", tc_count: 5 }]);
    renderGrid();

    await waitFor(() => {
      expect(testCasesApi.list).toHaveBeenCalled();
    });

    // 탭 바가 렌더링되지 않으므로 "전체" 탭도 없음
    expect(screen.queryByText("전체")).not.toBeInTheDocument();
  });

  it("시트 1개 + 이름 '체크리스트' → 탭 바가 보인다", async () => {
    setupSheets([{ name: "체크리스트", tc_count: 3 }]);
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("체크리스트")).toBeInTheDocument();
    });
  });

  it("시트 2개 → 모든 탭과 '전체' 탭이 표시된다", async () => {
    setupSheets([
      { name: "기능", tc_count: 10 },
      { name: "UI", tc_count: 5 },
    ]);
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("기능")).toBeInTheDocument();
    });
    expect(screen.getByText("UI")).toBeInTheDocument();
    expect(screen.getByText("전체")).toBeInTheDocument();
  });

  it("시트 탭 클릭 시 해당 시트의 TC가 로드된다", async () => {
    setupSheets([
      { name: "기능", tc_count: 10 },
      { name: "UI", tc_count: 5 },
    ]);
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("UI")).toBeInTheDocument();
    });

    await user.click(screen.getByText("UI"));

    await waitFor(() => {
      expect(testCasesApi.list).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ sheet_name: "UI" })
      );
    });
  });

  it("시트 삭제 × 버튼 클릭 + confirm → deleteSheet API 호출", async () => {
    setupSheets([
      { name: "기능", tc_count: 2 },
      { name: "UI", tc_count: 3 },
    ]);
    vi.mocked(testCasesApi.deleteSheet).mockResolvedValue({
      deleted: 2,
      sheet: "기능",
    });
    // confirm을 true로 mock
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("기능")).toBeInTheDocument();
    });

    // × 버튼 찾기 (title 속성으로 식별)
    const deleteBtn = screen.getAllByTitle("시트 삭제")[0];
    await user.click(deleteBtn);

    await waitFor(() => {
      expect(testCasesApi.deleteSheet).toHaveBeenCalledWith(1, "기능");
    });

    vi.mocked(window.confirm).mockRestore();
  });

  it("시트 삭제 × 버튼 클릭 + confirm 취소 → API 미호출", async () => {
    setupSheets([
      { name: "기능", tc_count: 2 },
      { name: "UI", tc_count: 3 },
    ]);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("기능")).toBeInTheDocument();
    });

    const deleteBtn = screen.getAllByTitle("시트 삭제")[0];
    await user.click(deleteBtn);

    expect(testCasesApi.deleteSheet).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockRestore();
  });

  it("+ 버튼 클릭 → 시트 이름 입력 → createSheet API 호출", async () => {
    setupSheets([
      { name: "기능", tc_count: 10 },
      { name: "UI", tc_count: 5 },
    ]);
    vi.mocked(testCasesApi.createSheet).mockResolvedValue({
      name: "새시트",
      tc_count: 0,
    });
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("기능")).toBeInTheDocument();
    });

    // + 버튼 클릭 (title="시트 추가")
    const addBtn = screen.getByTitle("루트 시트 추가");
    await user.click(addBtn);

    // 입력 UI 표시 확인
    const input = screen.getByPlaceholderText("시트 이름");
    expect(input).toBeInTheDocument();

    await user.type(input, "새시트");
    await user.click(screen.getByText("추가"));

    await waitFor(() => {
      expect(testCasesApi.createSheet).toHaveBeenCalledWith(1, "새시트", null);
    });
  });

  it("시트 추가 입력에서 Escape 키 시 입력 UI가 사라진다", async () => {
    setupSheets([
      { name: "기능", tc_count: 10 },
    ]);
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("기능")).toBeInTheDocument();
    });

    const addBtn = screen.getByTitle("루트 시트 추가");
    await user.click(addBtn);

    expect(screen.getByPlaceholderText("시트 이름")).toBeInTheDocument();

    await user.keyboard("{Escape}");

    expect(screen.queryByPlaceholderText("시트 이름")).not.toBeInTheDocument();
  });
});
