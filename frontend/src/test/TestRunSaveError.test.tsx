import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// 셀 편집 저장 경로를 실제로 태우려면 그리드가 넘겨받는 콜백이 필요하다.
// 공용 모킹은 rowData 길이만 찍어서 이 경로를 볼 수 없다.
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
import toast from "react-hot-toast";

const adminProject = {
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin",
};

const mockTC = {
  id: 1, project_id: 1, no: 1, tc_id: "TC-001", type: "기능", category: "결제",
  depth1: "", depth2: "", priority: "High", test_type: "수동", precondition: "",
  test_steps: "1. 실행", expected_result: "성공", r1: "", r2: "", r3: "",
  issue_link: "", assignee: "", remarks: "", sheet_name: "결제",
  created_at: "2026-01-01", updated_at: "2026-01-01",
};

const scopedRun = {
  id: 7, project_id: 1, name: "결제만", version: "v1", environment: "dev",
  round: 1, status: TestRunStatus.IN_PROGRESS, sheet_names: ["결제"],
  created_by: 1, created_at: "2026-01-01",
};

const row = {
  id: 71, test_run_id: 7, test_case_id: 1, result: "PASS", actual_result: "",
  issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01",
  test_case: mockTC,
};

beforeEach(() => {
  vi.clearAllMocks();
  gridProps = null;
  vi.mocked(testRunsApi.list).mockResolvedValue([scopedRun] as any);
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "결제", parent_id: null, sort_order: 0, is_folder: false, tc_count: 1, children: [] },
  ] as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue({ ...scopedRun, results: [row] } as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
});

async function openRun() {
  const user = userEvent.setup();
  render(<TestRunManager projectId={1} project={adminProject as any} />);
  await waitFor(() => {
    expect(screen.getByText("결제만")).toBeInTheDocument();
  });
  await user.click(screen.getByText("결제만"));
  await waitFor(() => {
    expect(gridProps?.onCellValueChanged).toBeTypeOf("function");
  });
  return user;
}

describe("결과 저장이 거부될 때", () => {
  it("서버가 준 이유를 그대로 띄운다", async () => {
    // ★"저장 실패" 로 뭉개면 무엇이 막혔는지 알 수 없다.
    //   시트 범위 밖 TC 거부가 이번에 새로 생긴 실패 경로다.
    vi.mocked(testRunsApi.submitResults).mockRejectedValue({
      response: { data: { detail: "이 수행의 시트 범위 밖 TC 입니다: TC-001" } },
    });
    await openRun();

    gridProps.onCellValueChanged({ data: { ...row, result: "FAIL" } });

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("이 수행의 시트 범위 밖 TC 입니다: TC-001");
    }, { timeout: 3000 });
  });

  it("저장이 거부되면 서버 값을 다시 받아 화면을 되돌린다", async () => {
    // ★화면 값만 바뀐 채로 남으면 저장된 것처럼 보인다(SYM-35 와 같은 유형).
    vi.mocked(testRunsApi.submitResults).mockRejectedValue({
      response: { data: { detail: "거부" } },
    });
    await openRun();
    const before = vi.mocked(testRunsApi.getOne).mock.calls.length;

    gridProps.onCellValueChanged({ data: { ...row, result: "FAIL" } });

    await waitFor(() => {
      expect(vi.mocked(testRunsApi.getOne).mock.calls.length).toBeGreaterThan(before);
    }, { timeout: 3000 });
  });

  it("이유가 없으면 기본 문구를 띄운다", async () => {
    vi.mocked(testRunsApi.submitResults).mockRejectedValue(new Error("network"));
    await openRun();

    gridProps.onCellValueChanged({ data: { ...row, result: "FAIL" } });

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("저장 실패");
    }, { timeout: 3000 });
  });

  it("저장에 성공하면 다시 불러오지 않는다", async () => {
    vi.mocked(testRunsApi.submitResults).mockResolvedValue([] as any);
    await openRun();
    const before = vi.mocked(testRunsApi.getOne).mock.calls.length;

    gridProps.onCellValueChanged({ data: { ...row, result: "FAIL" } });

    await waitFor(() => {
      expect(testRunsApi.submitResults).toHaveBeenCalled();
    }, { timeout: 3000 });
    expect(toast.error).not.toHaveBeenCalled();
    expect(vi.mocked(testRunsApi.getOne).mock.calls.length).toBe(before);
  });
});
