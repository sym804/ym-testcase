import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CompareView from "../components/CompareView";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(),
    getOne: vi.fn(),
  },
}));

import { testRunsApi } from "../api";
import { TestRunStatus } from "../types";

const mockTC = { id: 1, project_id: 1, no: 1, tc_id: "TC-001", type: "기능", category: "로그인", depth1: "로그인", depth2: "", priority: "High", test_type: "수동", precondition: "", test_steps: "로그인 테스트", expected_result: "성공", r1: "", r2: "", r3: "", issue_link: "", assignee: "테스터A", remarks: "", sheet_name: "기본", created_at: "2026-01-01", updated_at: "2026-01-01" };

const mockRuns = [
  { id: 1, project_id: 1, name: "R1 수행", version: "1.0", environment: "dev", round: 1, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-01" },
  { id: 2, project_id: 1, name: "R2 수행", version: "1.1", environment: "dev", round: 2, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-02" },
];

const mockLeftDetail = {
  ...mockRuns[0],
  results: [{ id: 1, test_run_id: 1, test_case_id: 1, result: "PASS", actual_result: "", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01", test_case: mockTC }],
};
const mockRightDetail = {
  ...mockRuns[1],
  results: [{ id: 2, test_run_id: 2, test_case_id: 1, result: "FAIL", actual_result: "에러 발생", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-02", test_case: mockTC }],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);
  vi.mocked(testRunsApi.getOne).mockImplementation((_pid: number, runId: number) =>
    Promise.resolve(runId === 1 ? mockLeftDetail : mockRightDetail)
  );
});

describe("CompareView", () => {
  it("수행 선택 드롭다운을 표시한다", async () => {
    render(<CompareView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("기준 수행 (Left)")).toBeInTheDocument();
      expect(screen.getByText("비교 수행 (Right)")).toBeInTheDocument();
    });
  });

  it("양쪽 미선택 시 안내 메시지를 표시한다", async () => {
    render(<CompareView projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("두 개의 테스트 수행을 선택하면 비교 결과가 표시됩니다.")).toBeInTheDocument();
    });
  });

  it("양쪽 선택 후 비교 결과를 표시한다", async () => {
    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    // Left 선택
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    // Right 선택
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      expect(screen.getByText("TC-001")).toBeInTheDocument();
    });
  });

  it("퇴보(regression)를 감지한다 (PASS→FAIL)", async () => {
    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      // 퇴보 통계가 표시됨
      expect(screen.getByText(/퇴보 1/)).toBeInTheDocument();
    });
  });

  it("필터 버튼이 작동한다", async () => {
    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      expect(screen.getByText("전체")).toBeInTheDocument();
      expect(screen.getByText("변경만")).toBeInTheDocument();
      expect(screen.getByText("퇴보만")).toBeInTheDocument();
    });
  });

  it("필터 '변경만' 클릭 시 변경된 행만 표시한다", async () => {
    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      expect(screen.getByText("변경만")).toBeInTheDocument();
    });

    await user.click(screen.getByText("변경만"));

    await waitFor(() => {
      // PASS→FAIL 변경된 TC-001이 표시됨
      expect(screen.getByText("TC-001")).toBeInTheDocument();
    });
  });

  it("필터 '퇴보만' 클릭 시 PASS→FAIL 행만 표시한다", async () => {
    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      expect(screen.getByText("퇴보만")).toBeInTheDocument();
    });

    await user.click(screen.getByText("퇴보만"));

    await waitFor(() => {
      // PASS→FAIL인 TC-001이 퇴보 행으로 표시됨
      expect(screen.getByText("TC-001")).toBeInTheDocument();
    });
  });

  it("개선 통계를 표시한다 (FAIL→PASS)", async () => {
    // Left: FAIL, Right: PASS (개선)
    vi.mocked(testRunsApi.getOne).mockImplementation((_pid: number, runId: number) =>
      Promise.resolve(runId === 1
        ? { ...mockRuns[0], results: [{ id: 1, test_run_id: 1, test_case_id: 1, result: "FAIL", actual_result: "에러", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01", test_case: mockTC }] }
        : { ...mockRuns[1], results: [{ id: 2, test_run_id: 2, test_case_id: 1, result: "PASS", actual_result: "", issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-02", test_case: mockTC }] }
      )
    );

    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      expect(screen.getByText(/개선 1/)).toBeInTheDocument();
    });
  });

  it("비교 결과 없을 때 테이블을 표시하지 않는다", async () => {
    vi.mocked(testRunsApi.getOne).mockImplementation((_pid: number, runId: number) =>
      Promise.resolve(runId === 1
        ? { ...mockRuns[0], results: [] }
        : { ...mockRuns[1], results: [] }
      )
    );

    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    await waitFor(() => {
      expect(screen.getAllByText("R1 수행 (R1)").length).toBeGreaterThan(0);
    });

    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "1");
    await user.selectOptions(selects[1], "2");

    await waitFor(() => {
      // 결과가 없으므로 TC ID 컬럼 헤더가 없어야 함
      expect(screen.queryByText("TC ID")).not.toBeInTheDocument();
    });
  });
});
