import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CompareView from "../components/CompareView";

// 느린 이전 응답이 최신 화면을 덮는 경쟁 상태.
//
// 대시보드에도 같은 지적이 있었지만 재현되지 않았다. `Dashboard.tsx:88` 의
// `if (loading || !summary)` 가 로딩 동안 필터 UI 를 통째로 감춰서 두 번째
// 요청을 낼 방법이 없다. 반면 비교 화면은 수행 선택기가 로딩과 무관하게 늘
// 떠 있어서 로딩 중에 다른 수행을 고를 수 있다. 그래서 이쪽만 막는다.

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  testRunsApi: { list: vi.fn(), getOne: vi.fn() },
}));

import { testRunsApi } from "../api";
import { TestRunStatus } from "../types";

function tc(id: number, tcId: string) {
  return {
    id, project_id: 1, no: id, tc_id: tcId, type: "기능", category: "로그인",
    depth1: "로그인", depth2: "", priority: "높음", test_type: "Web",
    precondition: "", test_steps: "1. 실행", expected_result: "성공",
    r1: "", r2: "", r3: "", issue_link: "", assignee: "", remarks: "",
    sheet_name: "기본", created_at: "2026-01-01", updated_at: "2026-01-01",
  };
}

const runs = [
  { id: 1, project_id: 1, name: "1회차", version: "1.0", environment: "dev", round: 1, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-01" },
  { id: 2, project_id: 1, name: "2회차", version: "1.1", environment: "dev", round: 2, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-02" },
  { id: 3, project_id: 1, name: "3회차", version: "1.2", environment: "dev", round: 3, status: TestRunStatus.COMPLETED, created_by: 1, created_at: "2026-01-03" },
];

function detailOf(runId: number, tcId: string) {
  return {
    ...runs.find((r) => r.id === runId)!,
    results: [{
      id: runId * 10, test_run_id: runId, test_case_id: 1, result: "PASS",
      actual_result: "", issue_link: "", remarks: "", executed_by: 1,
      executed_at: "2026-01-01", test_case: tc(1, tcId),
    }],
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testRunsApi.list).mockResolvedValue(runs as any);
});

describe("비교 화면의 경쟁 상태", () => {
  it("늦게 도착한 이전 수행의 결과가 지금 고른 수행을 덮지 않는다", async () => {
    let resolveSlow: ((v: unknown) => void) | null = null;

    vi.mocked(testRunsApi.getOne).mockImplementation((_pid: number, runId: number) => {
      if (runId === 2) {
        // 느린 쪽. 나중에 손으로 응답시킨다.
        return new Promise((res) => { resolveSlow = () => res(detailOf(2, "TC-옛것") as any); }) as any;
      }
      return Promise.resolve(detailOf(runId, runId === 3 ? "TC-새것" : "TC-기준") as any);
    });

    const user = userEvent.setup();
    render(<CompareView projectId={1} />);

    // 화면에 표시되는 TC ID 는 기준(좌) 수행의 것이라 좌측을 바꿔 가며 본다.
    const selects = await screen.findAllByRole("combobox");
    await user.selectOptions(selects[1], "1");
    await user.selectOptions(selects[0], "2"); // 느린 요청 시작

    // 아직 응답 전에 기준 수행을 3회차로 바꾼다.
    await user.selectOptions(selects[0], "3");

    await waitFor(() => {
      expect(screen.getByText("TC-새것")).toBeInTheDocument();
    });

    // 이제 2회차 응답이 뒤늦게 도착한다.
    resolveSlow?.(null);
    await new Promise((r) => setTimeout(r, 60));

    expect(
      screen.queryByText("TC-옛것"),
      "늦게 온 이전 수행의 결과가 화면을 덮었다",
    ).toBeNull();
    expect(screen.getByText("TC-새것")).toBeInTheDocument();
  });
});
