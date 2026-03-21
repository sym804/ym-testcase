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

function setupDefaultMocks(
  sheets: { name: string; tc_count: number }[] = [{ name: "기본", tc_count: 0 }],
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

describe("AutoSave - TestCaseGrid", () => {
  it("저장 버튼이 UI에 존재하지 않는다 (자동 저장 모드)", async () => {
    setupDefaultMocks();
    renderGrid();

    await waitFor(() => {
      expect(testCasesApi.listSheets).toHaveBeenCalled();
    });

    // "저장"이라는 텍스트의 버튼이 없어야 함
    const buttons = screen.queryAllByRole("button");
    const saveButton = buttons.find(
      (btn) => btn.textContent === "저장"
    );
    expect(saveButton).toBeUndefined();
  });

  it("시트가 2개 이상일 때 시트 탭 바가 렌더링된다", async () => {
    setupDefaultMocks([
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

  it("시트가 '기본' 1개뿐이면 탭 바가 보이지 않는다", async () => {
    setupDefaultMocks([{ name: "기본", tc_count: 3 }]);
    renderGrid();

    await waitFor(() => {
      expect(testCasesApi.list).toHaveBeenCalled();
    });

    // "기본" 시트 탭이 탭 바로 렌더링되지 않아야 함
    // 시트가 1개이고 이름이 "기본"이면 탭 바 자체가 렌더링 안 됨
    expect(screen.queryByText("전체")).not.toBeInTheDocument();
  });

  it("시트 1개이지만 이름이 '기본'이 아니면 탭 바가 보인다", async () => {
    setupDefaultMocks([{ name: "체크리스트", tc_count: 2 }]);
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("체크리스트")).toBeInTheDocument();
    });
  });

  it("빈 프로젝트(시트 없음)에서 시트 추가 화면을 표시한다", async () => {
    setupDefaultMocks([], []);
    renderGrid();

    await waitFor(() => {
      expect(
        screen.getByText("시트를 추가하여 테스트 케이스를 관리하세요.")
      ).toBeInTheDocument();
    });
    expect(screen.getByText("+ 시트 추가")).toBeInTheDocument();
  });

  it("빈 프로젝트에서 시트 추가 버튼 클릭 시 입력 UI가 나타난다", async () => {
    setupDefaultMocks([], []);
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("+ 시트 추가")).toBeInTheDocument();
    });

    await user.click(screen.getByText("+ 시트 추가"));
    expect(screen.getByPlaceholderText("시트 이름")).toBeInTheDocument();
    expect(screen.getByText("추가")).toBeInTheDocument();
  });

  it("시트 추가 후 createSheet API가 호출된다", async () => {
    setupDefaultMocks([], []);
    vi.mocked(testCasesApi.createSheet).mockResolvedValue({
      name: "새시트",
      tc_count: 0,
    });
    // 시트 생성 후 loadSheets가 다시 호출되므로 재설정
    vi.mocked(testCasesApi.listSheets)
      .mockResolvedValueOnce([])
      .mockResolvedValue([{ name: "새시트", tc_count: 0 }]);

    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("+ 시트 추가")).toBeInTheDocument();
    });

    await user.click(screen.getByText("+ 시트 추가"));
    const input = screen.getByPlaceholderText("시트 이름");
    await user.type(input, "새시트");
    await user.click(screen.getByText("추가"));

    await waitFor(() => {
      expect(testCasesApi.createSheet).toHaveBeenCalledWith(1, "새시트", null);
    });
  });

  it("시트 추가 시 빈 이름이면 API가 호출되지 않는다", async () => {
    setupDefaultMocks([], []);
    const user = userEvent.setup();
    renderGrid();

    await waitFor(() => {
      expect(screen.getByText("+ 시트 추가")).toBeInTheDocument();
    });

    await user.click(screen.getByText("+ 시트 추가"));
    // 빈 이름 상태에서 추가 클릭
    await user.click(screen.getByText("추가"));

    expect(testCasesApi.createSheet).not.toHaveBeenCalled();
  });
});
