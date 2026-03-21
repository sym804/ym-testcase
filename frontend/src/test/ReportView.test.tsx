import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReportView from "../components/ReportView";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(),
  },
  reportsApi: {
    getData: vi.fn(),
    downloadPdf: vi.fn(),
    downloadExcel: vi.fn(),
  },
}));

import { testRunsApi, reportsApi } from "../api";

const mockRuns = [
  { id: 1, project_id: 1, name: "R1 수행", version: "1.0", environment: "staging", round: 1, status: "completed", created_by: 1, created_at: "2026-01-15T09:00:00" },
];

const mockReport = {
  project: { id: 1, name: "테스트 프로젝트", description: "", jira_base_url: null, is_private: false, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01" },
  test_run: { id: 1, project_id: 1, name: "R1 수행", version: "1.0", environment: "staging", round: 1, status: "completed", created_by: 1, created_at: "2026-01-15T09:00:00" },
  summary: { total: 50, pass: 35, fail: 10, block: 3, na: 2, not_started: 0, pass_rate: 70, fail_rate: 20, block_rate: 6, na_rate: 4, not_started_rate: 0 },
  top_failures: [
    { id: 1, test_run_id: 1, test_case_id: 1, result: "FAIL", actual_result: "500 에러", issue_link: "https://jira.example.com/TEST-1", remarks: "", executed_by: 1, executed_at: "2026-01-15", test_case: { id: 1, project_id: 1, no: 1, tc_id: "TC-005", type: "", category: "", depth1: "", depth2: "", priority: "", test_type: "", precondition: "", test_steps: "", expected_result: "", r1: "", r2: "", r3: "", issue_link: "", assignee: "", remarks: "", created_at: "", updated_at: "" } },
  ],
  jira_issues: ["TEST-1", "TEST-2"],
  category_summary: [
    { category: "인증", total: 20, pass: 15, fail: 3, block: 1, na: 1, not_started: 0 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);
  vi.mocked(reportsApi.getData).mockResolvedValue(mockReport);
  vi.mocked(reportsApi.downloadPdf).mockResolvedValue(new Blob(["pdf"]));
  vi.mocked(reportsApi.downloadExcel).mockResolvedValue(new Blob(["excel"]));
});

describe("ReportView", () => {
  it("테스트 수행 셀렉터를 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("테스트 수행:")).toBeInTheDocument();
    });
  });

  it("다운로드 버튼을 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("PDF 다운로드")).toBeInTheDocument();
      expect(screen.getByText("Excel 다운로드")).toBeInTheDocument();
    });
  });

  it("프로젝트 정보를 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("프로젝트 정보")).toBeInTheDocument();
      expect(screen.getByText("테스트 프로젝트")).toBeInTheDocument();
    });
  });

  it("전체 현황 카드를 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("전체 현황")).toBeInTheDocument();
      expect(screen.getByText("70.0%")).toBeInTheDocument(); // pass_rate
    });
  });

  it("주요 실패 항목을 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("주요 실패 항목")).toBeInTheDocument();
      expect(screen.getByText("TC-005")).toBeInTheDocument();
      expect(screen.getByText("500 에러")).toBeInTheDocument();
    });
  });

  it("Jira 이슈 배지를 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("TEST-1")).toBeInTheDocument();
      expect(screen.getByText("TEST-2")).toBeInTheDocument();
    });
  });

  it("카테고리별 요약 테이블을 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("카테고리별 요약")).toBeInTheDocument();
      expect(screen.getByText("인증")).toBeInTheDocument();
    });
  });

  it("PDF 다운로드 버튼 클릭 시 reportsApi.downloadPdf를 호출한다", async () => {
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn() });
    const user = userEvent.setup();
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("PDF 다운로드")).toBeInTheDocument();
    });

    await user.click(screen.getByText("PDF 다운로드"));

    await waitFor(() => {
      expect(reportsApi.downloadPdf).toHaveBeenCalledWith(1, 1);
    });
  });

  it("Excel 다운로드 버튼 클릭 시 reportsApi.downloadExcel을 호출한다", async () => {
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn() });
    const user = userEvent.setup();
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("Excel 다운로드")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Excel 다운로드"));

    await waitFor(() => {
      expect(reportsApi.downloadExcel).toHaveBeenCalledWith(1, 1);
    });
  });

  it("수행 미선택 시 다운로드 버튼이 disabled이다", async () => {
    vi.mocked(testRunsApi.list).mockResolvedValue([]);
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("PDF 다운로드")).toBeDisabled();
      expect(screen.getByText("Excel 다운로드")).toBeDisabled();
    });
  });

  it("실패 항목이 없으면 '실패 항목이 없습니다' 표시한다", async () => {
    const reportNoFailures = { ...mockReport, top_failures: [] };
    vi.mocked(reportsApi.getData).mockResolvedValue(reportNoFailures);
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("실패 항목이 없습니다.")).toBeInTheDocument();
    });
  });
});
