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
import { TestRunStatus } from "../types";
import type { ReportData } from "../types";

const mockRuns = [
  { id: 1, project_id: 1, name: "R1 수행", version: "1.0", environment: "staging", round: 1, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-15T09:00:00" },
];

const mockReport: ReportData = {
  // 리포트 응답은 전용 모양이다. 엔티티 전체가 아니라 화면에 쓰는 조각만 온다.
  project: { id: 1, name: "테스트 프로젝트", description: "", jira_base_url: null, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01" },
  test_run: { id: 1, name: "R1 수행", version: "1.0", environment: "staging", round: 1, status: TestRunStatus.COMPLETED, created_at: "2026-01-15T09:00:00", completed_at: null },
  summary: { total: 50, executed: 48, pass: 35, fail: 10, block: 3, na: 2, not_started: 0, pass_rate: 70, fail_rate: 20, block_rate: 6, na_rate: 4, not_started_rate: 0 },
  // ★jira_issues 는 백엔드가 항목의 issue_link 값을 그대로 모은 것이다. 픽스처가 이
  //   관계를 어기면(예전: 링크는 URL 인데 목록은 키) 틀린 계약이 통과한다.
  top_failures: [
    { test_case: { tc_id: "TC-005", priority: "High", category: "인증" }, result: "FAIL", actual_result: "500 에러", issue_link: "https://jira.example.com/browse/TEST-1", executed_by: "테스터" },
  ],
  jira_issues: ["https://jira.example.com/browse/TEST-1"],
  category_summary: [
    { category: "인증", total: 20, pass: 15, fail: 3, block: 1, na: 1, not_started: 0, pass_rate: 78.9 },
  ],
  priority_summary: [
    { priority: "High", total: 30, pass: 20, fail: 8, block: 2, na: 0, not_started: 0, pass_rate: 66.7 },
    { priority: null, total: 20, pass: 15, fail: 2, block: 1, na: 2, not_started: 0, pass_rate: 83.3 },
  ],
  comparison: null,
  executors: [{ name: "테스터", count: 48 }],
  total_duration_sec: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);
  vi.mocked(reportsApi.getData).mockResolvedValue(mockReport);
  vi.mocked(reportsApi.downloadPdf).mockResolvedValue({ blob: new Blob(["pdf"]), filename: "테스트 프로젝트_Report_R1.pdf" });
  vi.mocked(reportsApi.downloadExcel).mockResolvedValue({ blob: new Blob(["excel"]), filename: null });
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

  it("실패·차단 항목을 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("실패·차단 항목")).toBeInTheDocument();
      expect(screen.getByText("TC-005")).toBeInTheDocument();
      expect(screen.getByText("500 에러")).toBeInTheDocument();
    });
  });

  it("관련 이슈 배지를 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      // 항목 행과 배지 두 곳에 나온다
      expect(screen.getAllByText("https://jira.example.com/browse/TEST-1")).toHaveLength(2);
    });
  });

  it("카테고리별 요약 테이블을 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("카테고리별 요약")).toBeInTheDocument();
      // 실패 항목 행의 분류 칸에도 "인증" 이 나오므로 표의 행으로 좁힌다
      expect(screen.getByTestId("category-row-인증")).toHaveTextContent("78.9%");
    });
  });

  it("전체 현황 카드에 미수행과 N/A 건수를 표시한다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      summary: { total: 50, executed: 33, pass: 20, fail: 10, block: 3, na: 2, not_started: 15, pass_rate: 60.6, fail_rate: 20, block_rate: 6, na_rate: 4, not_started_rate: 30 },
    });
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("전체 현황")).toBeInTheDocument();
    });

    const nsCard = screen.getByTestId("stat-not-started");
    expect(nsCard).toHaveTextContent("미수행");
    expect(nsCard).toHaveTextContent("15");

    const naCard = screen.getByTestId("stat-na");
    expect(naCard).toHaveTextContent("N/A");
    expect(naCard).toHaveTextContent("2");
  });

  it("전체 현황 카드의 PASS/FAIL/BLOCK/N-A/미수행 합이 전체 TC 와 일치한다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      summary: { total: 50, executed: 33, pass: 20, fail: 10, block: 3, na: 2, not_started: 15, pass_rate: 60.6, fail_rate: 20, block_rate: 6, na_rate: 4, not_started_rate: 30 },
    });
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByTestId("stat-total")).toHaveTextContent("50");
    });

    const nums = ["stat-pass", "stat-fail", "stat-block", "stat-na", "stat-not-started"].map(
      (id) => Number(screen.getByTestId(id).textContent?.replace(/[^0-9]/g, "")),
    );
    expect(nums.reduce((a, b) => a + b, 0)).toBe(50);
  });

  it("카테고리별 요약 표에 미수행 컬럼을 표시한다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      category_summary: [{ category: "인증", total: 20, pass: 12, fail: 3, block: 1, na: 1, not_started: 3, pass_rate: 75 }],
    });
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("카테고리별 요약")).toBeInTheDocument();
    });

    // FAIL 도 3 이라서 행 전체 텍스트로 단언하면 미수행 칸이 없어도 통과한다. 셀로 좁힌다.
    expect(screen.getByTestId("category-ns-인증")).toHaveTextContent("3");
    expect(screen.getByTestId("category-na-인증")).toHaveTextContent("1");
    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent);
    expect(headers).toContain("미수행");
    expect(headers).toContain("N/A");
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

  it("실패·차단 항목이 없으면 없다고 표시한다", async () => {
    const reportNoFailures = { ...mockReport, top_failures: [] };
    vi.mocked(reportsApi.getData).mockResolvedValue(reportNoFailures);
    render(<ReportView projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("실패하거나 차단된 항목이 없습니다.")).toBeInTheDocument();
    });
  });

  // ── 2026-09-23 리포트 개선 ───────────────────────────────────────────────

  it("BLOCK 항목도 실리고 결과 칸이 BLOCK 으로 표시된다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      top_failures: [
        { test_case: { tc_id: "SRCH-012", priority: null, category: "검색" }, result: "BLOCK", actual_result: "검색 input 요소를 찾지 못함", issue_link: null, executed_by: null },
      ],
      jira_issues: [],
    });
    render(<ReportView projectId={1} />);
    const row = await screen.findByTestId("issue-row-SRCH-012");
    expect(row).toHaveTextContent("BLOCK");
    expect(row).toHaveTextContent("검색 input 요소를 찾지 못함");
    expect(row).not.toHaveTextContent("FAIL");
    expect(screen.queryByText("실패하거나 차단된 항목이 없습니다.")).not.toBeInTheDocument();
  });

  it("이슈 키는 이슈 관리 도구 주소로 링크하고, 못 만들면 링크를 걸지 않는다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      project: { ...mockReport.project, jira_base_url: "https://jira.example.com" },
      top_failures: [
        { test_case: { tc_id: "A-1" }, result: "FAIL", actual_result: null, issue_link: "PROJ-7", executed_by: null },
        { test_case: { tc_id: "A-2" }, result: "FAIL", actual_result: null, issue_link: "메모만 적음", executed_by: null },
      ],
      jira_issues: ["PROJ-7", "메모만 적음"],
    });
    render(<ReportView projectId={1} />);
    const row1 = await screen.findByTestId("issue-row-A-1");
    expect(row1.querySelector("a")).toHaveAttribute("href", "https://jira.example.com/browse/PROJ-7");
    // 예전에는 href="#" 로 걸려 눌러도 아무 일이 없었다
    const row2 = screen.getByTestId("issue-row-A-2");
    expect(row2.querySelector("a")).toBeNull();
    expect(row2).toHaveTextContent("메모만 적음");
    expect(document.querySelector('a[href="#"]')).toBeNull();
  });

  it("직전 수행 대비 회귀와 해결을 표시한다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      comparison: {
        previous_run: { id: 9, name: "지난 회귀", round: 3 },
        common: 40,
        changed: 5,
        regressions: [{ tc_id: "R-1", priority: "High", before: "PASS", after: "FAIL" }],
        fixed: [
          { tc_id: "F-1", priority: "Low", before: "FAIL", after: "PASS" },
          { tc_id: "F-2", priority: null, before: "FAIL", after: "PASS" },
        ],
      },
    });
    render(<ReportView projectId={1} />);
    const section = await screen.findByTestId("comparison");
    expect(section).toHaveTextContent("지난 회귀");
    expect(screen.getByTestId("comparison-regressions")).toHaveTextContent("1");
    expect(screen.getByTestId("comparison-fixed")).toHaveTextContent("2");
    expect(section).toHaveTextContent("R-1");
    expect(section).toHaveTextContent("F-1, F-2");
  });

  it("직전 수행이 없으면 비교 섹션을 그리지 않는다", async () => {
    render(<ReportView projectId={1} />);
    await screen.findByText("전체 현황");
    expect(screen.queryByTestId("comparison")).not.toBeInTheDocument();
  });

  it("우선순위별 요약을 그리고 비어 있는 우선순위는 (미지정) 으로 표시한다", async () => {
    render(<ReportView projectId={1} />);
    await screen.findByText("우선순위별 요약");
    expect(screen.getByTestId("priority-row-High")).toHaveTextContent("66.7%");
    expect(screen.getByTestId("priority-row-unset")).toHaveTextContent("(미지정)");
  });

  it("수행이 없는 분류의 합격률은 0% 가 아니라 - 다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      category_summary: [{ category: "결제", total: 4, pass: 0, fail: 0, block: 0, na: 1, not_started: 3, pass_rate: null }],
    });
    render(<ReportView projectId={1} />);
    expect(await screen.findByTestId("category-rate-결제")).toHaveTextContent("-");
  });

  it("생성일과 완료일을 따로 표시한다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      test_run: { ...mockReport.test_run, created_at: "2026-07-02T09:00:00", completed_at: "2026-07-06T18:00:00" },
    });
    render(<ReportView projectId={1} />);
    expect(await screen.findByTestId("info-created")).toHaveTextContent("2026. 7. 2.");
    expect(screen.getByTestId("info-completed")).toHaveTextContent("2026. 7. 6.");
    expect(screen.getByTestId("info-executors")).toHaveTextContent("테스터 48");
  });

  it("다운로드 파일 이름은 서버가 정한 것을 쓰고, 없으면 대신할 이름을 쓴다", async () => {
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:mock"), revokeObjectURL: vi.fn() });
    const names: string[] = [];
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      names.push(this.download);
    });
    const user = userEvent.setup();
    render(<ReportView projectId={1} />);
    await screen.findByText("전체 현황");

    await user.click(screen.getByText("PDF 다운로드"));
    await user.click(screen.getByText("Excel 다운로드"));
    await waitFor(() => expect(names).toHaveLength(2));
    expect(names).toEqual(["테스트 프로젝트_Report_R1.pdf", "report_1.xlsx"]);
    clickSpy.mockRestore();
  });
});
