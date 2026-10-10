import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ReportView from "../components/ReportView";
import i18n from "../i18n";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(),
    update: vi.fn(),
  },
  reportsApi: {
    getData: vi.fn(),
    downloadPdf: vi.fn(),
    downloadExcel: vi.fn(),
  },
  runIssuesApi: {
    carryOver: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

import { testRunsApi, reportsApi, runIssuesApi } from "../api";
import toast from "react-hot-toast";
import { TestRunStatus } from "../types";
import type { ReportData } from "../types";

const editorProject = {
  id: 1, name: "테스트 프로젝트", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "tester",
};

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

  it("실패·차단 항목에는 수행자 열이 없다", async () => {
    // 수행자는 프로젝트 정보의 "수행자" 에 모아 싣는다. 행마다 되풀이하지 않는다.
    render(<ReportView projectId={1} />);
    const row = await screen.findByTestId("issue-row-TC-005");
    expect(row.querySelectorAll("td")).toHaveLength(6);
    expect(row).not.toHaveTextContent("테스터");
  });

  it("결과 칸 이슈 링크는 실패 항목 행에만 나오고 별도 섹션은 없다", async () => {
    // 예전에는 "연관 이슈" 섹션에 배지로 한 번 더 실었다. 이슈 목록으로 합치면서 없앴다.
    render(<ReportView projectId={1} />);
    await waitFor(() => {
      expect(screen.getAllByText("https://jira.example.com/browse/TEST-1")).toHaveLength(1);
    });
    expect(screen.queryByText("연관 이슈")).toBeNull();
    expect(screen.queryByText("결과에 기록된 이슈 링크")).toBeNull();
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
      expect(reportsApi.downloadPdf).toHaveBeenCalledWith(1, 1, "ko");
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
      expect(reportsApi.downloadExcel).toHaveBeenCalledWith(1, 1, "ko");
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
        prev_fail: { total: 3, fixed: 2, still: 1, other: 0 },
        changes: [
          { tc_id: "R-1", priority: "High", category: "인증", before: "PASS", after: "FAIL", kind: "regression", issue_keys: [] },
          { tc_id: "S-1", priority: "High", category: "인증", before: "FAIL", after: "FAIL", kind: "still", issue_keys: ["SF-1089"] },
          { tc_id: "F-1", priority: "Low", category: null, before: "FAIL", after: "PASS", kind: "fixed", issue_keys: [] },
          { tc_id: "F-2", priority: null, category: "세션", before: "FAIL", after: "PASS", kind: "fixed", issue_keys: ["SF-1081", "SF-1084"] },
        ],
      },
    });
    render(<ReportView projectId={1} />);
    const section = await screen.findByTestId("comparison");
    expect(section).toHaveTextContent("지난 회귀");
    // 카드 넷: 이전 실패 3 -> 수정 2 · 미수정 1, 퇴보 1. FAIL 그대로인 TC 도 표에 실린다
    expect(screen.getByTestId("comparison-prev-fail")).toHaveTextContent("이전 실패 TC3");
    expect(screen.getByTestId("comparison-fixed")).toHaveTextContent("수정된 TC2");
    expect(screen.getByTestId("comparison-still")).toHaveTextContent("미수정 TC1");
    expect(screen.getByTestId("comparison-regressions")).toHaveTextContent("퇴보 TC1");
    expect(section).not.toHaveTextContent("결과가 변경된 TC");
    const rows = screen.getAllByTestId(/^change-row-/).map((el) => el.getAttribute("data-testid"));
    expect(rows).toEqual(["change-row-R-1", "change-row-S-1", "change-row-F-1", "change-row-F-2"]);
    expect(screen.getByTestId("change-row-S-1")).toHaveTextContent("FAIL -> FAIL");
    expect(screen.getByTestId("change-row-S-1")).toHaveTextContent("미수정");
    expect(screen.getByTestId("change-row-S-1")).toHaveTextContent("SF-1089");
    expect(screen.getByTestId("change-row-F-2")).toHaveTextContent("SF-1081, SF-1084");
    expect(screen.getByTestId("change-row-F-1")).toHaveTextContent("(미분류)");
  });

  it("비교 대상이 없으면 읽기 권한에서는 비교 섹션을 그리지 않는다", async () => {
    render(<ReportView projectId={1} />);
    await screen.findByText("전체 현황");
    expect(screen.queryByTestId("comparison")).not.toBeInTheDocument();
  });

  it("R1 처럼 비교 대상이 없으면 편집 권한에서는 안내와 선택 목록을 보여 준다", async () => {
    vi.mocked(testRunsApi.list).mockResolvedValue([
      ...mockRuns,
      { ...mockRuns[0], id: 2, name: "Full 테스트", round: 1 },
    ]);
    render(<ReportView projectId={1} project={{ ...editorProject }} />);
    const section = await screen.findByTestId("comparison");
    expect(section).toHaveTextContent("비교할 이전 회차가 없습니다.");
    const select = screen.getByTestId("compare-target");
    expect(select).toHaveValue("");
    // 자기 자신은 목록에 없다
    expect([...select.querySelectorAll("option")].map((o) => o.textContent)).toEqual([
      "자동 (같은 이름의 이전 회차)", "Full 테스트 (R1)",
    ]);
  });

  it("비교 대상을 고르면 수행에 저장하고 리포트를 다시 읽는다", async () => {
    const user = userEvent.setup();
    vi.mocked(testRunsApi.list).mockResolvedValue([
      ...mockRuns,
      { ...mockRuns[0], id: 2, name: "Full 테스트", round: 1 },
    ]);
    vi.mocked(testRunsApi.update).mockResolvedValue({ ...mockRuns[0], compare_run_id: 2 });
    render(<ReportView projectId={1} project={{ ...editorProject }} />);
    const select = await screen.findByTestId("compare-target");
    const calls = vi.mocked(reportsApi.getData).mock.calls.length;

    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      test_run: { ...mockReport.test_run, compare_run_id: 2 },
      comparison: { previous_run: { id: 2, name: "Full 테스트", round: 1 }, mode: "manual", common: 3, changed: 0, regressions: [], fixed: [] },
    });
    await user.selectOptions(select, "2");

    await waitFor(() => {
      expect(testRunsApi.update).toHaveBeenCalledWith(1, 1, { compare_run_id: 2 });
    });
    await waitFor(() => expect(vi.mocked(reportsApi.getData).mock.calls.length).toBeGreaterThan(calls));
    expect(await screen.findByText(/비교 대상: Full 테스트 \(R1\)/)).toBeInTheDocument();
    expect(screen.getByTestId("compare-target")).toHaveValue("2");
  });

  it("자동으로 고른 대상이면 그렇다고 알려 준다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      comparison: { previous_run: { id: 9, name: "R1 수행", round: 1 }, mode: "auto", common: 1, changed: 0, regressions: [], fixed: [] },
    });
    render(<ReportView projectId={1} />);
    expect(await screen.findByTestId("comparison")).toHaveTextContent("자동 선택");
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

  it("분류 없는 TC 는 요약 표와 실패·차단 목록에서 같은 이름으로 보인다", async () => {
    // 예전에는 요약 표가 "Uncategorized", 목록이 "-" 였다
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      top_failures: [
        { test_case: { tc_id: "N-1", priority: null, category: null }, result: "FAIL", actual_result: null, issue_link: null, executed_by: null },
      ],
      category_summary: [{ category: null, total: 1, pass: 0, fail: 1, block: 0, na: 0, not_started: 0, pass_rate: 0 }],
    });
    render(<ReportView projectId={1} />);
    expect(await screen.findByTestId("category-row-unset")).toHaveTextContent("(미분류)");
    expect(screen.getByTestId("issue-row-N-1")).toHaveTextContent("(미분류)");
    expect(screen.queryByText("Uncategorized")).not.toBeInTheDocument();
  });

  it("실패·차단 목록의 우선순위도 요약 표와 같은 이름을 쓴다", async () => {
    // 예전에는 비어 있으면 "-", 요약 표는 "(미지정)" 이었다
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      top_failures: [
        { test_case: { tc_id: "P-1", priority: "매우 높음", category: "c" }, result: "FAIL", actual_result: null, issue_link: null, executed_by: null },
        { test_case: { tc_id: "P-2", priority: null, category: "c" }, result: "FAIL", actual_result: null, issue_link: null, executed_by: null },
      ],
    });
    render(<ReportView projectId={1} />);
    expect(await screen.findByTestId("issue-row-P-1")).toHaveTextContent("매우 높음");
    expect(screen.getByTestId("issue-row-P-2")).toHaveTextContent("(미지정)");
  });

  it("영어 화면에서는 우선순위를 번역한 이름으로 보인다", async () => {
    // 한국어 모드에서는 "매우 높음" 이 번역 전후로 같은 글자라 번역이 빠져도 모른다
    await i18n.changeLanguage("en");
    try {
      vi.mocked(reportsApi.getData).mockResolvedValue({
        ...mockReport,
        top_failures: [
          { test_case: { tc_id: "P-1", priority: "매우 높음", category: "c" }, result: "FAIL", actual_result: null, issue_link: null, executed_by: null },
        ],
        priority_summary: [
          { priority: "보통", total: 1, pass: 0, fail: 1, block: 0, na: 0, not_started: 0, pass_rate: 0 },
        ],
      });
      render(<ReportView projectId={1} />);
      expect(await screen.findByTestId("issue-row-P-1")).toHaveTextContent("Critical");
      expect(screen.getByTestId("priority-row-보통")).toHaveTextContent("Normal");
    } finally {
      await i18n.changeLanguage("ko");
    }
  });

  it("생성일과 완료일을 따로 표시한다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...mockReport,
      test_run: { ...mockReport.test_run, created_at: "2026-07-02T09:00:00", completed_at: "2026-07-06T18:00:00" },
    });
    render(<ReportView projectId={1} />);
    // PDF 와 같은 모양이다
    expect(await screen.findByTestId("info-created")).toHaveTextContent("2026-07-02 09:00");
    expect(screen.getByTestId("info-completed")).toHaveTextContent("2026-07-06 18:00");
    // 이름만, 건수 없이. 여러 명이면 쉼표로 잇는다.
    expect(screen.getByTestId("info-executors")).toHaveTextContent("테스터");
    expect(screen.getByTestId("info-executors")).not.toHaveTextContent("48");
  });

  it("프로젝트 정보는 항목과 값의 표이고 수행 이름과 상태를 싣는다", async () => {
    render(<ReportView projectId={1} />);
    const table = await screen.findByTestId("info-table");
    const heads = [...table.querySelectorAll("th")].map((th) => th.textContent);
    expect(heads).toEqual(["프로젝트", "테스트 수행", "버전", "환경", "라운드", "상태", "생성일", "완료일", "수행자"]);
    expect(table).toHaveTextContent("R1 수행 (R1)");
    expect(screen.getByTestId("info-status")).toHaveTextContent("완료");
    expect(screen.getByTestId("info-completed")).toHaveTextContent("-");
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

// ── 등록 이슈 섹션 ──────────────────────────────────────────────────────────

const LINEAR_URL = "https://linear.app/sym/issue/SF-1081/session";
const withIssues: ReportData = {
  ...mockReport,
  project: { ...mockReport.project, issue_tracker: "linear" },
  issues: [{ id: 7, issue_key: "SF-1081", title: "세션 만료 후 재로그인 실패", url: LINEAR_URL, status: "Todo", note: null, tc_ids: ["ASP-01", "ASP-02"] }],
};
const testerProject = {
  id: 1, name: "테스트 프로젝트", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "tester",
};

describe("ReportView 이슈 섹션", () => {
  it("등록한 이슈를 제목 링크로 보여 주고 도구 이름을 붙인다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue(withIssues);
    render(<ReportView projectId={1} />);
    const link = await screen.findByRole("link", { name: "세션 만료 후 재로그인 실패" });
    expect(link).toHaveAttribute("href", LINEAR_URL);
    expect(link).toHaveAttribute("target", "_blank");
    expect(screen.getByText("이슈 (Linear)")).toBeInTheDocument();
    expect(screen.getByTestId("run-issue-7")).toHaveTextContent("SF-1081");
    // 도구의 상태(Todo)는 표에 싣지 않는다. 표의 상태는 QA 판정이다
    expect(screen.getByTestId("run-issue-7")).not.toHaveTextContent("Todo");
    expect(screen.getByTestId("run-issue-7")).toHaveTextContent("ASP-01, ASP-02");
  });

  it("이슈가 없으면 빈 안내를 보여 준다", async () => {
    render(<ReportView projectId={1} />);
    expect(await screen.findByText("등록한 이슈가 없습니다.")).toBeInTheDocument();
    expect(screen.getByText("이슈")).toBeInTheDocument();
  });

  it("권한 정보가 없거나 viewer 면 추가·수정 버튼이 없다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue(withIssues);
    const { unmount } = render(<ReportView projectId={1} />);
    await screen.findByTestId("run-issue-7");
    expect(screen.queryByTestId("issue-add")).toBeNull();
    expect(screen.queryByText("수정")).toBeNull();
    unmount();

    render(<ReportView projectId={1} project={{ ...testerProject, my_role: "viewer" }} />);
    await screen.findByTestId("run-issue-7");
    expect(screen.queryByTestId("issue-add")).toBeNull();
  });

  it("제목과 링크를 넣어 추가하고 리포트를 다시 읽는다", async () => {
    const user = userEvent.setup();
    vi.mocked(runIssuesApi.create).mockResolvedValue(withIssues.issues![0]);
    render(<ReportView projectId={1} project={testerProject} />);

    await user.click(await screen.findByTestId("issue-add"));
    const save = screen.getByTestId("issue-save");
    expect(save).toBeDisabled();

    await user.type(screen.getByPlaceholderText("이슈 제목"), "세션 만료 후 재로그인 실패");
    const urlInput = screen.getByPlaceholderText("https://linear.app/workspace/issue/ABC-123");
    await user.type(urlInput, "linear.app/sym");
    expect(screen.getByText("링크는 http:// 또는 https:// 로 시작해야 합니다.")).toBeInTheDocument();
    expect(save).toBeDisabled();

    await user.clear(urlInput);
    await user.type(urlInput, LINEAR_URL);
    vi.mocked(reportsApi.getData).mockResolvedValue(withIssues);
    await user.click(save);

    await waitFor(() => {
      expect(runIssuesApi.create).toHaveBeenCalledWith(1, 1, expect.objectContaining({
        title: "세션 만료 후 재로그인 실패", url: LINEAR_URL,
      }));
    });
    expect(await screen.findByTestId("run-issue-7")).toBeInTheDocument();
    expect(screen.queryByTestId("issue-form")).toBeNull();
  });

  it("이미 등록된 링크면 중복 안내를 띄운다", async () => {
    const user = userEvent.setup();
    vi.mocked(runIssuesApi.create).mockRejectedValue({ response: { status: 409 } });
    render(<ReportView projectId={1} project={testerProject} />);

    await user.click(await screen.findByTestId("issue-add"));
    await user.type(screen.getByPlaceholderText("이슈 제목"), "중복");
    await user.type(screen.getByPlaceholderText("https://linear.app/workspace/issue/ABC-123"), LINEAR_URL);
    await user.click(screen.getByTestId("issue-save"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("이 수행에 이미 등록된 링크입니다.");
    });
    expect(screen.getByTestId("issue-form")).toBeInTheDocument();
  });

  it("수정하면 기존 값을 채운 폼으로 열고 update 를 부른다", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.getData).mockResolvedValue(withIssues);
    vi.mocked(runIssuesApi.update).mockResolvedValue({ ...withIssues.issues![0], note: "Major" });
    render(<ReportView projectId={1} project={testerProject} />);

    await user.click(await screen.findByText("수정"));
    expect(screen.getByPlaceholderText("이슈 제목")).toHaveValue("세션 만료 후 재로그인 실패");
    // 도구 상태 입력칸은 없다(표의 상태는 QA 판정). 심각도는 note 칸이다
    expect(screen.queryByPlaceholderText("예: In Progress")).toBeNull();
    const severity = screen.getByPlaceholderText("예: Major");
    await user.clear(severity);
    await user.type(severity, "Major");
    await user.click(screen.getByTestId("issue-save"));

    await waitFor(() => {
      expect(runIssuesApi.update).toHaveBeenCalledWith(1, 1, 7, expect.objectContaining({ note: "Major" }));
    });
  });

  it("연관 TC 를 쉼표로 넣으면 목록으로 나눠 보낸다", async () => {
    const user = userEvent.setup();
    vi.mocked(runIssuesApi.create).mockResolvedValue(withIssues.issues![0]);
    render(<ReportView projectId={1} project={testerProject} />);

    await user.click(await screen.findByTestId("issue-add"));
    await user.type(screen.getByPlaceholderText("이슈 제목"), "t");
    await user.type(screen.getByPlaceholderText("https://linear.app/workspace/issue/ABC-123"), LINEAR_URL);
    await user.type(screen.getByPlaceholderText("예: ASP-01, ASP-02"), " ASP-02, ,ASP-01, ASP-02");
    await user.click(screen.getByTestId("issue-save"));

    await waitFor(() => {
      expect(runIssuesApi.create).toHaveBeenCalledWith(1, 1, expect.objectContaining({ tc_ids: ["ASP-02", "ASP-01"] }));
    });
  });

  it("수행에 없는 TC 면 어떤 TC 인지 알려 준다", async () => {
    const user = userEvent.setup();
    vi.mocked(runIssuesApi.create).mockRejectedValue({ response: { status: 422, data: { detail: "TC not in this run: OUT-1" } } });
    render(<ReportView projectId={1} project={testerProject} />);

    await user.click(await screen.findByTestId("issue-add"));
    await user.type(screen.getByPlaceholderText("이슈 제목"), "t");
    await user.type(screen.getByPlaceholderText("https://linear.app/workspace/issue/ABC-123"), LINEAR_URL);
    await user.type(screen.getByPlaceholderText("예: ASP-01, ASP-02"), "OUT-1");
    await user.click(screen.getByTestId("issue-save"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("이 수행에 없는 TC 입니다: OUT-1");
    });
  });

  it("결과 칸에만 적힌 이슈를 후보로 보여 주고, 누르면 키·링크·TC 를 채운다", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...withIssues,
      project: { ...withIssues.project, jira_base_url: "https://linear.app/sym" },
      issue_candidates: [{ issue_key: "SF-1085", url: null, tc_ids: ["ASP-02", "ASP-03"] }],
    });
    render(<ReportView projectId={1} project={testerProject} />);

    const box = await screen.findByTestId("issue-candidates");
    expect(box).toHaveTextContent("결과에 기록됐지만 목록에 없는 이슈 1건");
    expect(box).toHaveTextContent("SF-1085");
    expect(box).toHaveTextContent("ASP-02, ASP-03");

    await user.click(screen.getByRole("button", { name: "SF-1085 이슈 추가" }));
    expect(screen.getByPlaceholderText("비우면 링크에서 추출")).toHaveValue("SF-1085");
    expect(screen.getByPlaceholderText("https://linear.app/workspace/issue/ABC-123")).toHaveValue("https://linear.app/sym/issue/SF-1085");
    expect(screen.getByPlaceholderText("예: ASP-01, ASP-02")).toHaveValue("ASP-02, ASP-03");
    expect(screen.getByPlaceholderText("이슈 제목")).toHaveValue("");
  });

  it("viewer 에게는 후보가 보이지만 추가 버튼은 없다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...withIssues,
      issue_candidates: [{ issue_key: "SF-1085", url: null, tc_ids: [] }],
    });
    render(<ReportView projectId={1} project={{ ...testerProject, my_role: "viewer" }} />);
    await screen.findByTestId("issue-candidates");
    expect(screen.queryByRole("button", { name: "SF-1085 이슈 추가" })).toBeNull();
  });
});

describe("ReportView 이슈 묶음과 판정", () => {
  const carried: ReportData = {
    ...mockReport,
    project: { ...mockReport.project, issue_tracker: "linear" },
    issue_summary: { open: 3, resolved: 1, unverified: 1 },
    issues: [
      { id: 1, issue_key: "SF-2", title: "유지되는 이슈", url: LINEAR_URL, status: "Dev Deployed", note: null, tc_ids: [], origin_round: 1, verdict: "open", group: "open" },
      { id: 2, issue_key: "SF-9", title: "새 이슈", url: "https://linear.app/sym/issue/SF-9", status: null, note: null, tc_ids: [], origin_round: null, verdict: null, group: "open" },
      { id: 3, issue_key: "SF-4", title: "안 본 이슈", url: "https://linear.app/sym/issue/SF-4", status: null, note: null, tc_ids: ["ASP-01"], origin_round: 1, verdict: "unverified", group: "open", tcs_all_pass: true },
      { id: 4, issue_key: "SF-1", title: "고쳐진 이슈", url: "https://linear.app/sym/issue/SF-1", status: null, note: null, tc_ids: [], origin_round: 1, verdict: "resolved", group: "resolved" },
    ],
  };

  it("서버가 정한 묶음 차례로 나누고 요약 줄과 발견 회차를 보여 준다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue(carried);
    render(<ReportView projectId={1} project={testerProject} />);
    expect(await screen.findByTestId("issue-summary")).toHaveTextContent("미해결 3 · 처리 완료 1 (미해결 중 미확인 1)");
    // 묶음은 둘뿐이다. 신규 · 미확인도 해결 전이면 미해결이고, 신규는 발견 열 "이번 수행" 으로 안다
    const rows = screen.getAllByTestId(/^(issue-group-|run-issue-)/).map((el) => el.getAttribute("data-testid"));
    expect(rows).toEqual([
      "issue-group-open", "run-issue-1", "run-issue-2", "run-issue-3", "issue-group-resolved", "run-issue-4",
    ]);
    expect(screen.getByTestId("issue-group-open")).toHaveTextContent("미해결");
    expect(screen.getByTestId("issue-group-open").querySelector("td")?.getAttribute("style")).toContain("var(--color-fail)");
    expect(screen.getByTestId("run-issue-1")).toHaveTextContent("R1");
    expect(screen.getByTestId("run-issue-2")).toHaveTextContent("이번 수행");
    // 새 이슈는 판정 칸이 "-" 가 아니라 "신규" 다
    expect(screen.getByTestId("issue-verdict-2")).toHaveDisplayValue("신규");
    // 미확인인데 연관 TC 가 전부 PASS 면 해결 후보 표시가 붙는다
    expect(screen.getByTestId("run-issue-3")).toHaveTextContent("해결 후보");
    expect(screen.getByTestId("run-issue-1")).not.toHaveTextContent("해결 후보");
  });

  it("행의 판정을 고르면 바로 저장하고 리포트를 다시 읽는다", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.getData).mockResolvedValue(carried);
    vi.mocked(runIssuesApi.update).mockResolvedValue({ ...carried.issues![2], verdict: "resolved" });
    render(<ReportView projectId={1} project={testerProject} />);
    await user.selectOptions(await screen.findByTestId("issue-verdict-3"), "resolved");
    await waitFor(() => {
      expect(runIssuesApi.update).toHaveBeenCalledWith(1, 1, 3, { verdict: "resolved" });
      expect(reportsApi.getData).toHaveBeenCalledTimes(2);
    });
  });

  it("viewer 는 판정을 글자로만 보고 가져오기 버튼이 없다", async () => {
    vi.mocked(reportsApi.getData).mockResolvedValue(carried);
    render(<ReportView projectId={1} project={{ ...testerProject, my_role: "viewer" }} />);
    await screen.findByTestId("run-issue-1");
    expect(screen.queryByTestId("issue-verdict-1")).toBeNull();
    expect(screen.getByTestId("run-issue-1")).toHaveTextContent("유지");
    expect(screen.queryByTestId("issue-carry-over")).toBeNull();
  });

  it("출처 수행을 고르면 그 수행에서 가져오고, 이름이 다른 수행의 이슈는 발견 열에 이름이 붙는다", async () => {
    const user = userEvent.setup();
    vi.mocked(testRunsApi.list).mockResolvedValue([
      ...mockRuns,
      { id: 5, project_id: 1, name: "Full 테스트", version: "1.0", environment: "dev", round: 1, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-10T09:00:00" },
    ]);
    vi.mocked(reportsApi.getData).mockResolvedValue({
      ...carried,
      issues: [
        { id: 1, issue_key: "SF-2", title: "같은 이름", url: LINEAR_URL, status: null, note: null, tc_ids: [], origin_round: 1, origin_run_name: "R1 수행", verdict: "open", group: "open" },
        { id: 2, issue_key: "SF-3", title: "다른 이름", url: "https://linear.app/sym/issue/SF-3", status: null, note: null, tc_ids: [], origin_round: 1, origin_run_name: "Full 테스트", verdict: "open", group: "open" },
      ],
    });
    vi.mocked(runIssuesApi.carryOver).mockResolvedValue({
      from_run_id: 5, from_run_name: "Full 테스트", from_run_round: 1, added: 1, skipped: 0, issues: [],
    });
    render(<ReportView projectId={1} project={testerProject} />);
    // 현재 수행(id 1)은 출처 목록에 없다
    const from = await screen.findByTestId("issue-carry-from");
    expect(within(from).queryByText("R1 수행 (R1)")).toBeNull();
    await user.selectOptions(from, "5");
    await user.click(screen.getByTestId("issue-carry-over"));
    await waitFor(() => expect(runIssuesApi.carryOver).toHaveBeenCalledWith(1, 1, 5));
    expect(screen.getByTestId("run-issue-1")).toHaveTextContent("R1");
    expect(screen.getByTestId("run-issue-1")).not.toHaveTextContent("R1 수행 R1");
    expect(screen.getByTestId("run-issue-2")).toHaveTextContent("Full 테스트 R1");
  });

  it("이전 회차 이슈 가져오기는 서버 결과를 알리고 리포트를 다시 읽는다", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.getData).mockResolvedValue(carried);
    vi.mocked(runIssuesApi.carryOver).mockResolvedValue({
      from_run_id: 6, from_run_name: "세션 정책", from_run_round: 1, added: 3, skipped: 1, issues: [],
    });
    render(<ReportView projectId={1} project={testerProject} />);
    await user.click(await screen.findByTestId("issue-carry-over"));
    await waitFor(() => {
      expect(runIssuesApi.carryOver).toHaveBeenCalledWith(1, 1, undefined);
      expect(reportsApi.getData).toHaveBeenCalledTimes(2);
    });
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("세션 정책 (R1) 에서 이슈 3건"));
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("이미 등록된 1건"));
  });

  it("가져올 이전 회차가 없으면(404) 비교 대상을 고르라고 알린다", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.getData).mockResolvedValue(carried);
    vi.mocked(runIssuesApi.carryOver).mockRejectedValue({ response: { status: 404 } });
    render(<ReportView projectId={1} project={testerProject} />);
    await user.click(await screen.findByTestId("issue-carry-over"));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("가져올 이전 회차가 없습니다")));
    expect(reportsApi.getData).toHaveBeenCalledTimes(1);
  });

  it("추가 폼에서 판정을 고르면 함께 보낸다", async () => {
    const user = userEvent.setup();
    vi.mocked(reportsApi.getData).mockResolvedValue(carried);
    vi.mocked(runIssuesApi.create).mockResolvedValue(carried.issues![1]);
    render(<ReportView projectId={1} project={testerProject} />);
    await user.click(await screen.findByTestId("issue-add"));
    await user.type(screen.getByPlaceholderText("이슈 제목"), "t");
    await user.type(screen.getByPlaceholderText("https://linear.app/workspace/issue/ABC-123"), LINEAR_URL);
    await user.selectOptions(screen.getByLabelText("상태"), "partial");
    await user.click(screen.getByTestId("issue-save"));
    await waitFor(() => {
      expect(runIssuesApi.create).toHaveBeenCalledWith(1, 1, expect.objectContaining({ verdict: "partial" }));
    });
  });
});

describe("ReportView 수행 전환 경합", () => {
  it("늦게 도착한 이전 수행의 리포트가 지금 고른 수행을 덮지 않는다", async () => {
    const r2 = { ...mockRuns[0], id: 2, name: "R2 수행" };
    vi.mocked(testRunsApi.list).mockResolvedValue([mockRuns[0], r2] as any);
    let releaseFirst!: () => void;
    vi.mocked(reportsApi.getData).mockImplementation(async (_pid: number, runId: number) => {
      if (runId === 1) {
        await new Promise<void>((r) => { releaseFirst = r; });
        return mockReport;
      }
      return { ...mockReport, test_run: { ...mockReport.test_run, id: 2, name: "R2 수행" } };
    });
    render(<ReportView projectId={1} />);
    await waitFor(() => expect(reportsApi.getData).toHaveBeenCalledWith(1, 1));

    await userEvent.selectOptions(screen.getByRole("combobox"), "2");
    await waitFor(() => expect(reportsApi.getData).toHaveBeenCalledWith(1, 2));
    await screen.findAllByText(/R2 수행/);
    releaseFirst();
    await new Promise((r) => setTimeout(r, 50));

    expect(screen.queryAllByText(/R1 수행/).filter((el) => el.tagName !== "OPTION")).toHaveLength(0);
  });
});

describe("ReportView 이전 수행에서 시작된 갱신", () => {
  it("비교 대상 저장이 늦게 끝나도 이미 고른 다른 수행의 리포트를 덮지 않는다", async () => {
    const user = userEvent.setup();
    const r2 = { ...mockRuns[0], id: 2, name: "R2 수행" };
    vi.mocked(testRunsApi.list).mockResolvedValue([mockRuns[0], r2] as any);
    let releaseUpdate!: () => void;
    vi.mocked(testRunsApi.update).mockImplementation(
      () => new Promise((r) => { releaseUpdate = () => r({ ...mockRuns[0], compare_run_id: 2 } as any); }));
    vi.mocked(reportsApi.getData).mockImplementation(async (_pid: number, runId: number) =>
      runId === 2 ? { ...mockReport, test_run: { ...mockReport.test_run, id: 2, name: "R2 수행" } } : mockReport);
    render(<ReportView projectId={1} project={{ ...editorProject }} />);
    await user.selectOptions(await screen.findByTestId("compare-target"), "2");   // R1 의 비교 대상 변경 시작

    await user.selectOptions(screen.getAllByRole("combobox")[0], "2");            // R2 로 옮김
    await screen.findAllByText(/R2 수행/);
    const before = vi.mocked(reportsApi.getData).mock.calls.length;
    releaseUpdate();
    await new Promise((r) => setTimeout(r, 50));

    expect(vi.mocked(reportsApi.getData).mock.calls.slice(before).filter((c) => c[1] === 1)).toHaveLength(0);
    expect(screen.queryAllByText(/R1 수행/).filter((el) => el.tagName !== "OPTION")).toHaveLength(0);
  });
});

