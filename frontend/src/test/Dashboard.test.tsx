import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Dashboard from "../components/Dashboard";

// Mock Chart.js components
vi.mock("react-chartjs-2", () => ({
  Doughnut: () => <div data-testid="doughnut-chart">Doughnut</div>,
  Bar: () => <div data-testid="bar-chart">Bar</div>,
  Line: () => <div data-testid="line-chart">Line</div>,
}));

vi.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light" }),
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  dashboardApi: {
    summary: vi.fn(),
    priority: vi.fn(),
    category: vi.fn(),
    rounds: vi.fn(),
    assignee: vi.fn(),
    heatmap: vi.fn(),
  },
  testRunsApi: {
    list: vi.fn(),
  },
}));

import { dashboardApi, testRunsApi } from "../api";

const mockSummary = {
  total: 100, pass: 60, fail: 20, block: 10, na: 5, not_started: 5,
  pass_rate: 60, fail_rate: 20, block_rate: 10, na_rate: 5, not_started_rate: 5,
};
const mockPriority = [
  { priority: "High", total: 40, pass: 30, fail: 5, block: 3, na: 2, not_started: 0 },
  { priority: "Medium", total: 60, pass: 30, fail: 15, block: 7, na: 3, not_started: 5 },
];
const mockCategory = [
  { category: "로그인", total: 20, pass: 15, fail: 3, block: 1, na: 1, not_started: 0 },
];
const mockRounds = [
  { round: 1, total: 100, pass: 50, fail: 30, block: 10, na: 10, pass_rate: 50 },
  { round: 2, total: 100, pass: 60, fail: 20, block: 10, na: 10, pass_rate: 60 },
];
const mockAssignee = [
  { assignee: "테스터A", total: 50, pass: 40, fail: 5, block: 3, na: 2, not_started: 0, completion_rate: 100 },
];
const mockHeatmap = [
  { category: "로그인", priority: "High", fail_count: 3 },
];
const mockRuns = [
  { id: 1, project_id: 1, name: "R1 수행", version: "1.0", environment: "dev", round: 1, status: "completed", created_by: 1, created_at: "2026-01-01" },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(dashboardApi.summary).mockResolvedValue(mockSummary);
  vi.mocked(dashboardApi.priority).mockResolvedValue(mockPriority);
  vi.mocked(dashboardApi.category).mockResolvedValue(mockCategory);
  vi.mocked(dashboardApi.rounds).mockResolvedValue(mockRounds);
  vi.mocked(dashboardApi.assignee).mockResolvedValue(mockAssignee);
  vi.mocked(dashboardApi.heatmap).mockResolvedValue(mockHeatmap);
  vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);
});

describe("Dashboard", () => {
  it("로딩 중 메시지를 표시한다", () => {
    render(<Dashboard projectId={1} />);
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
  });

  it("요약 카드를 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("전체 TC")).toBeInTheDocument();
    });
    // 퍼센트 값으로 카드 렌더링 확인
    expect(screen.getByText("60.0%")).toBeInTheDocument(); // pass_rate
    expect(screen.getByText("20.0%")).toBeInTheDocument(); // fail_rate
    expect(screen.getByText("10.0%")).toBeInTheDocument(); // block_rate
  });

  it("도넛 차트를 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByTestId("doughnut-chart")).toBeInTheDocument();
    });
  });

  it("바 차트를 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
    });
  });

  it("트렌드 라인 차트를 렌더링한다 (라운드 > 1)", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByTestId("line-chart")).toBeInTheDocument();
    });
  });

  it("우선순위 테이블을 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("우선순위별 분포")).toBeInTheDocument();
    });
  });

  it("카테고리 테이블을 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("카테고리별 분포")).toBeInTheDocument();
    });
  });

  it("담당자 테이블을 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("담당자별 현황")).toBeInTheDocument();
    });
    expect(screen.getByText("테스터A")).toBeInTheDocument();
  });

  it("히트맵을 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("결함 밀집 히트맵 (Category x Priority)")).toBeInTheDocument();
    });
  });

  it("테스트 수행 셀렉터를 표시한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("테스트 수행:")).toBeInTheDocument();
    });
    expect(screen.getByText("R1 수행 (R1)")).toBeInTheDocument();
  });

  it("수행 셀렉터에서 특정 수행 선택 시 API가 run_id와 함께 호출된다", async () => {
    const user = userEvent.setup();
    render(<Dashboard projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("R1 수행 (R1)")).toBeInTheDocument();
    });

    vi.clearAllMocks();
    // 재선택 후에도 API가 동작하도록 mock 유지
    vi.mocked(dashboardApi.summary).mockResolvedValue(mockSummary);
    vi.mocked(dashboardApi.priority).mockResolvedValue(mockPriority);
    vi.mocked(dashboardApi.category).mockResolvedValue(mockCategory);
    vi.mocked(dashboardApi.rounds).mockResolvedValue(mockRounds);
    vi.mocked(dashboardApi.assignee).mockResolvedValue(mockAssignee);
    vi.mocked(dashboardApi.heatmap).mockResolvedValue(mockHeatmap);
    vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "1");

    await waitFor(() => {
      expect(dashboardApi.summary).toHaveBeenCalledWith(1, 1);
    });
  });

  it("히트맵 데이터가 비어있으면 히트맵 섹션을 표시하지 않는다", async () => {
    vi.mocked(dashboardApi.heatmap).mockResolvedValue([]);
    render(<Dashboard projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("전체 TC")).toBeInTheDocument();
    });

    expect(screen.queryByText("결함 밀집 히트맵 (Category x Priority)")).not.toBeInTheDocument();
  });
});
