import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ★공용 ag-grid 모킹(TestRunManager.test.tsx)은 rowData 길이만 찍는다.
//   그래서 셀 렌더러가 한 번도 실행되지 않고, 첨부 셀에 무엇이 그려지는지
//   어떤 테스트도 볼 수 없었다. 여기서는 첨부 컬럼의 렌더러를 실제로 돌린다.
vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">
      {(props.rowData ?? []).map((row: any) => (
        <div key={row.id} data-testid={`row-${row.id}`}>
          {(props.columnDefs ?? [])
            .filter((c: any) => c.field === "attachments" && c.cellRenderer)
            .map((c: any, i: number) => (
              <span key={i}>{c.cellRenderer({ data: row })}</span>
            ))}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: () => {} },
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../components/MarkdownCell", () => ({
  default: (props: any) => <span>{props.value}</span>,
}));

vi.mock("../components/HighlightCell", () => ({
  default: (props: any) => <span>{props.value}</span>,
}));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(),
    create: vi.fn(),
    getOne: vi.fn(),
    update: vi.fn(),
    submitResults: vi.fn(),
    complete: vi.fn(),
    reopen: vi.fn(),
    clone: vi.fn(),
    delete: vi.fn(),
    exportExcel: vi.fn(),
  },
  testCasesApi: {
    listSheets: vi.fn(),
  },
  attachmentsApi: {
    list: vi.fn(),
    listByRun: vi.fn(),
    upload: vi.fn(),
    delete: vi.fn(),
    downloadUrl: vi.fn(),
  },
}));

import { testRunsApi, testCasesApi, attachmentsApi } from "../api";
import { TestRunStatus } from "../types";
import TestRunManager from "../components/TestRunManager";
import toast from "react-hot-toast";

const adminProject = {
  id: 1,
  name: "TestProject",
  description: "desc",
  jira_base_url: null,
  is_private: false,
  created_by: 1,
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
  my_role: "admin" as string,
};

const mockTC = {
  id: 1,
  project_id: 1,
  no: 1,
  tc_id: "TC-001",
  type: "기능",
  category: "로그인",
  depth1: "인증",
  depth2: "기본",
  priority: "High",
  test_type: "수동",
  precondition: "",
  test_steps: "1. 로그인",
  expected_result: "성공",
  r1: "",
  r2: "",
  r3: "",
  issue_link: "",
  assignee: "테스터A",
  remarks: "",
  sheet_name: "기본",
  created_at: "2026-01-01",
  updated_at: "2026-01-01",
};

const mockTC2 = { ...mockTC, id: 2, no: 2, tc_id: "TC-002" };

const mockRun = {
  id: 1,
  project_id: 1,
  name: "Sprint 1 테스트",
  version: "v1.0",
  environment: "dev",
  round: 1,
  status: TestRunStatus.IN_PROGRESS,
  created_by: 1,
  created_at: "2026-01-01",
};

const mockRunDetail = {
  ...mockRun,
  results: [
    { id: 11, test_run_id: 1, test_case_id: 1, result: "PASS", actual_result: "", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01", test_case: mockTC },
    { id: 22, test_run_id: 1, test_case_id: 2, result: "FAIL", actual_result: "", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01", test_case: mockTC2 },
  ],
};

const mockAttachment = {
  id: 100,
  test_result_id: 11,
  filename: "실패화면.png",
  content_type: "image/png",
  file_size: 1024,
  uploaded_by: 1,
  uploaded_at: "2026-01-01",
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testRunsApi.list).mockResolvedValue([mockRun] as any);
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { name: "기본", tc_count: 2, id: 1, parent_id: null, sort_order: 0, is_folder: false, children: [] },
  ] as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue(mockRunDetail as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([mockAttachment] as any);
});

async function selectRun() {
  const user = userEvent.setup();
  render(<TestRunManager projectId={1} project={adminProject as any} />);
  await waitFor(() => {
    expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
  });
  await user.click(screen.getByText("Sprint 1 테스트"));
  await waitFor(() => {
    expect(screen.getByTestId("row-11")).toBeInTheDocument();
  });
  return user;
}

describe("테스트 수행 - 첨부파일 표시", () => {
  it("런을 열면 셀을 클릭하지 않아도 첨부 파일명이 보인다", async () => {
    await selectRun();

    // ★이 단언이 이 버그의 본체다. 예전에는 행을 클릭해 첨부를 받아오기 전까지
    //   셀에 + 버튼만 있었고, 첨부가 있는지 알 수 없었다.
    await waitFor(() => {
      expect(screen.getByTitle("실패화면.png")).toBeInTheDocument();
    });
    expect(screen.getByText("실패화면.png")).toBeInTheDocument();
  });

  it("런 상세를 열 때 첨부를 런 단위로 한 번에 조회한다", async () => {
    await selectRun();

    await waitFor(() => {
      expect(attachmentsApi.listByRun).toHaveBeenCalledWith(1);
    });
    // 행마다 따로 부르지 않는다
    expect(attachmentsApi.list).not.toHaveBeenCalled();
  });

  it("첨부가 없는 행에는 파일명이 없고 첨부 버튼만 있다", async () => {
    await selectRun();

    await waitFor(() => {
      expect(screen.getByTestId("row-11")).toBeInTheDocument();
    });
    const emptyRow = screen.getByTestId("row-22");
    expect(emptyRow.textContent).toBe("+");
  });

  it("런을 빠르게 바꾸면 늦게 온 이전 런의 응답이 화면을 덮지 않는다", async () => {
    // ★런 상세와 첨부 조회는 런/시트를 바꿀 때마다 다시 돈다. 앞 요청이 늦게 도착하면
    //   이전 런의 결과와 첨부가 지금 보고 있는 런 위에 그려진다.
    const run2 = { ...mockRun, id: 2, name: "Sprint 2 테스트", round: 2 };
    vi.mocked(testRunsApi.list).mockResolvedValue([mockRun, run2] as any);
    vi.mocked(testRunsApi.getOne).mockImplementation((_pid: number, runId: number) => {
      if (runId === 1) {
        return new Promise((res) => setTimeout(() => res(mockRunDetail as any), 300));
      }
      return Promise.resolve({
        ...run2,
        results: [
          { id: 33, test_run_id: 2, test_case_id: 1, result: "", actual_result: "", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01", test_case: mockTC },
        ],
      } as any);
    });
    vi.mocked(attachmentsApi.listByRun).mockImplementation((runId: number) => {
      if (runId === 1) {
        return new Promise((res) => setTimeout(() => res([mockAttachment] as any), 400));
      }
      return Promise.resolve([] as any);
    });

    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => {
      expect(screen.getByText("Sprint 1 테스트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("Sprint 1 테스트"));
    await user.click(screen.getByText("Sprint 2 테스트"));

    await waitFor(() => {
      expect(screen.getByTestId("row-33")).toBeInTheDocument();
    });
    // 이전 런의 응답이 도착할 시간을 준다
    await new Promise((r) => setTimeout(r, 1200));

    expect(screen.getByTestId("row-33")).toBeInTheDocument();
    expect(screen.queryByTestId("row-11")).toBeNull();
    expect(screen.queryByText("실패화면.png")).toBeNull();
  });

  it("첨부 일괄 조회가 실패해도 결과 그리드는 그대로 뜬다", async () => {
    vi.mocked(attachmentsApi.listByRun).mockRejectedValue(new Error("boom"));

    await selectRun();

    expect(screen.getByTestId("row-11")).toBeInTheDocument();
    expect(screen.getByTestId("row-22")).toBeInTheDocument();
    expect(toast.error).not.toHaveBeenCalled();
  });
});
