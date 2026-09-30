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
    heatmap: vi.fn(),
  },
  testRunsApi: {
    list: vi.fn(),
  },
}));

import { dashboardApi, testRunsApi } from "../api";
import { TestRunStatus } from "../types";

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
  { round: 1, run_id: 1, name: "R1 수행", status: "completed", total: 100, pass: 50, fail: 30, block: 10, na: 10, not_started: 0, executed: 90, pass_rate: 55.6, fail_rate: 33.3 },
  { round: 2, run_id: 2, name: "R1 수행", status: "completed", total: 100, pass: 60, fail: 20, block: 10, na: 10, not_started: 0, executed: 90, pass_rate: 66.7, fail_rate: 22.2 },
];
const mockHeatmap = [
  { category: "로그인", priority: "High", fail_count: 3 },
];
const mockRuns = [
  { id: 1, project_id: 1, name: "R1 수행", version: "1.0", environment: "dev", round: 1, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-01" },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(dashboardApi.summary).mockResolvedValue(mockSummary);
  vi.mocked(dashboardApi.priority).mockResolvedValue(mockPriority);
  vi.mocked(dashboardApi.category).mockResolvedValue(mockCategory);
  vi.mocked(dashboardApi.rounds).mockResolvedValue(mockRounds);
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

  it("담당자별 표를 그리지 않는다", async () => {
    // ★assignee 필드는 v1.2.0 에서 없어졌고 백엔드 엔드포인트는 빈 배열만
    //   돌려주는 스텁이다. 그런데 화면은 헤더까지 갖춘 표를 그려서 사용자가
    //   "아직 데이터가 없나" 로 읽게 된다. 종전 테스트는 가짜 응답을 물려
    //   그 표를 정상으로 못박고 있었다(실제로는 늘 빈 표다).
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("전체 TC")).toBeInTheDocument();
    });
    expect(screen.queryByText("담당자별 현황")).toBeNull();
  });

  it("히트맵을 렌더링한다", async () => {
    render(<Dashboard projectId={1} />);
    await waitFor(() => {
      expect(screen.getByText("결함 분포 (카테고리 × 우선순위)")).toBeInTheDocument();
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
    vi.mocked(dashboardApi.heatmap).mockResolvedValue(mockHeatmap);
    vi.mocked(testRunsApi.list).mockResolvedValue(mockRuns);

    // 첫 번째 목록이 위쪽 「테스트 수행」 이다. 두 번째는 회차 차트의 테스트 선택이다
    const select = screen.getAllByRole("combobox")[0];
    await user.selectOptions(select, "1");

    await waitFor(() => {
      expect(dashboardApi.summary).toHaveBeenCalledWith(1, 1, undefined, undefined);
    });
  });

  it("히트맵 데이터가 비어있으면 히트맵 섹션을 표시하지 않는다", async () => {
    vi.mocked(dashboardApi.heatmap).mockResolvedValue([]);
    render(<Dashboard projectId={1} />);

    await waitFor(() => {
      expect(screen.getByText("전체 TC")).toBeInTheDocument();
    });

    expect(screen.queryByText("결함 분포 (카테고리 × 우선순위)")).not.toBeInTheDocument();
  });

  it("회차 추이는 실행한 회차가 둘 이상일 때만 그린다", async () => {
    vi.mocked(dashboardApi.rounds).mockResolvedValue([
      mockRounds[0],
      { ...mockRounds[1], status: "in_progress", pass: 0, fail: 0, block: 0, na: 0, not_started: 100, executed: 0, pass_rate: null, fail_rate: null },
    ]);
    render(<Dashboard projectId={1} />);
    await screen.findByText("전체 TC");
    expect(screen.queryByTestId("pass-fail-trend")).toBeNull();
  });

  it("회차 추이 제목에 어떤 테스트인지 붙인다", async () => {
    render(<Dashboard projectId={1} />);
    const trend = await screen.findByTestId("pass-fail-trend");
    expect(trend).toHaveTextContent("Pass/Fail Rate 추이 · R1 수행");
  });

  it("차트의 테스트를 변경하면 그 이름으로 회차를 다시 불러온다", async () => {
    const user = userEvent.setup();
    vi.mocked(testRunsApi.list).mockResolvedValue([
      ...mockRuns,
      { ...mockRuns[0], id: 2, name: "Full 테스트", round: 1 },
    ]);
    render(<Dashboard projectId={1} />);
    const group = await screen.findByTestId("round-group");
    await user.selectOptions(group, "Full 테스트");
    await waitFor(() => {
      expect(dashboardApi.rounds).toHaveBeenLastCalledWith(1, undefined, undefined, "Full 테스트");
    });
  });

  it("히트맵 우선순위 열은 심각도 순, 행은 FAIL 이 많은 순이고 합계를 붙인다", async () => {
    vi.mocked(dashboardApi.heatmap).mockResolvedValue([
      { category: "로그인", priority: "낮음", fail_count: 1 },
      { category: "결제", priority: "보통", fail_count: 2 },
      { category: "결제", priority: "매우 높음", fail_count: 3 },
      { category: "", priority: "높음", fail_count: 1 },
    ]);
    render(<Dashboard projectId={1} />);
    const heat = await screen.findByTestId("heatmap");
    const heads = [...heat.querySelectorAll("thead th")].map((th) => th.textContent);
    expect(heads).toEqual(["카테고리", "매우 높음", "높음", "보통", "낮음", "합계"]);
    const rows = [...heat.querySelectorAll("tbody tr")].map((tr) => tr.querySelector("td")?.textContent);
    expect(rows).toEqual(["결제", "(미분류)", "로그인"]);
    expect(screen.getByTestId("heatmap-row-결제")).toHaveTextContent("5");
    expect(heat).toHaveTextContent("FAIL 7건 · TC별 최신 결과 기준");
  });
});
