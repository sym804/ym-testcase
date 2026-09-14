import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 저장 디바운스 타이머가 행별인지 본다.
// 타이머가 하나뿐이면 0.3초 안에 다른 행을 편집할 때 앞 행의 저장이 통째로
// 취소되고, 에러도 토스트도 없이 입력이 사라진다. TC 관리 그리드는 행별 키로
// 타이머를 두는데 수행 그리드만 전역 하나였다.
let gridProps: any = null;

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => {
    gridProps = props;
    return <div data-testid="ag-grid">{props.rowData?.length ?? 0}</div>;
  },
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: () => {} },
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../components/MarkdownCell", () => ({ default: (p: any) => <span>{p.value}</span> }));
vi.mock("../components/HighlightCell", () => ({ default: (p: any) => <span>{p.value}</span> }));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(), create: vi.fn(), getOne: vi.fn(), update: vi.fn(),
    submitResults: vi.fn(), complete: vi.fn(), reopen: vi.fn(),
    clone: vi.fn(), delete: vi.fn(), exportExcel: vi.fn(),
  },
  testCasesApi: { listSheets: vi.fn() },
  attachmentsApi: { list: vi.fn(), listByRun: vi.fn(), upload: vi.fn(), delete: vi.fn(), downloadUrl: vi.fn() },
}));

import { testRunsApi, testCasesApi, attachmentsApi } from "../api";
import { TestRunStatus } from "../types";
import TestRunManager from "../components/TestRunManager";

const adminProject = {
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin",
};

function tc(id: number) {
  return {
    id, project_id: 1, no: id, tc_id: `TC-00${id}`, type: "기능", category: "결제",
    depth1: "", depth2: "", priority: "높음", test_type: "Web", precondition: "",
    test_steps: "1. 실행", expected_result: "성공", r1: "", r2: "", r3: "",
    issue_link: "", assignee: "", remarks: "", sheet_name: "결제",
    created_at: "2026-01-01", updated_at: "2026-01-01",
  };
}

const run = {
  id: 7, project_id: 1, name: "결제 회귀", version: "v1", environment: "dev",
  round: 1, status: TestRunStatus.IN_PROGRESS, sheet_names: null,
  created_by: 1, created_at: "2026-01-01",
};

function resultRow(id: number, tcId: number) {
  return {
    id, test_run_id: 7, test_case_id: tcId, result: "NS", actual_result: "",
    issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01",
    test_case: tc(tcId),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  gridProps = null;
  vi.mocked(testRunsApi.list).mockResolvedValue([run] as any);
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "결제", parent_id: null, sort_order: 0, is_folder: false, tc_count: 2, children: [] },
  ] as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue({
    ...run, results: [resultRow(71, 1), resultRow(72, 2)],
  } as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
  vi.mocked(testRunsApi.submitResults).mockResolvedValue([] as any);
});

async function openRun() {
  const user = userEvent.setup();
  render(<TestRunManager projectId={1} project={adminProject as any} />);
  await waitFor(() => {
    expect(screen.getByText("결제 회귀")).toBeInTheDocument();
  });
  await user.click(screen.getByText("결제 회귀"));
  await waitFor(() => {
    expect(gridProps?.onCellValueChanged).toBeTypeOf("function");
  });
  return user;
}

describe("수행 결과 저장 디바운스", () => {
  it("서로 다른 행을 연달아 편집해도 둘 다 저장된다", async () => {
    await openRun();

    // 디바운스 창(300ms) 안에 A 행, B 행을 연달아 편집한다.
    gridProps.onCellValueChanged({
      data: { ...resultRow(71, 1), result: "PASS" },
      column: { getColId: () => "result" },
      oldValue: "NS",
    });
    gridProps.onCellValueChanged({
      data: { ...resultRow(72, 2), result: "FAIL" },
      column: { getColId: () => "result" },
      oldValue: "NS",
    });

    await waitFor(() => {
      expect(vi.mocked(testRunsApi.submitResults).mock.calls.length).toBe(2);
    }, { timeout: 3000 });

    const saved = vi.mocked(testRunsApi.submitResults).mock.calls
      .map((c: any) => c[2][0])
      .sort((a: any, b: any) => a.test_case_id - b.test_case_id);

    expect(saved[0]).toMatchObject({ test_case_id: 1, result: "PASS" });
    expect(saved[1]).toMatchObject({ test_case_id: 2, result: "FAIL" });
  });

  it("잰 소요 시간을 함께 보낸다", async () => {
    // ★페이로드에 duration_sec 이 없으면 백엔드가 갱신할 값을 못 받는다.
    //   매뉴얼은 결과 입력 시 경과 시간이 기록된다고 안내하고 수행 엑셀에도
    //   칸이 있는데, 실 DB 결과 5,209건 중 기록된 것이 0건이었다.
    await openRun();

    gridProps.onCellValueChanged({
      data: { ...resultRow(71, 1), result: "PASS", duration_sec: 42 },
      column: { getColId: () => "result" },
      oldValue: "NS",
    });

    await waitFor(() => {
      expect(vi.mocked(testRunsApi.submitResults).mock.calls.length).toBe(1);
    }, { timeout: 3000 });

    const saved = vi.mocked(testRunsApi.submitResults).mock.calls[0] as any;
    expect(saved[2][0]).toMatchObject({ test_case_id: 1, duration_sec: 42 });
  });

  it("같은 행을 연달아 편집하면 마지막 값 한 번만 저장한다", async () => {
    await openRun();

    gridProps.onCellValueChanged({
      data: { ...resultRow(71, 1), result: "PASS" },
      column: { getColId: () => "result" },
      oldValue: "NS",
    });
    gridProps.onCellValueChanged({
      data: { ...resultRow(71, 1), result: "FAIL" },
      column: { getColId: () => "result" },
      oldValue: "PASS",
    });

    await waitFor(() => {
      expect(vi.mocked(testRunsApi.submitResults).mock.calls.length).toBe(1);
    }, { timeout: 3000 });

    const saved = vi.mocked(testRunsApi.submitResults).mock.calls[0] as any;
    expect(saved[2][0]).toMatchObject({ test_case_id: 1, result: "FAIL" });
  });
});
