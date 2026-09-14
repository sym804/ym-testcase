import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../i18n";

// 두 그리드가 거의 같은 코드인데 한쪽만 고쳐 온 이력이 있다.
// - 여러 줄 텍스트 컬럼에 큰 편집기를 안 달면 기본 input 이 열려 줄바꿈이 지워진다(SYM-25).
//   그때 TC 그리드만 고치고 수행 그리드가 빠졌다.
// - 찾기/바꾸기가 forEachNode 를 쓰면 필터로 숨은 행까지 바꾼다.
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
  default: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

vi.mock("../components/MarkdownCell", () => ({ default: (p: any) => <span>{p.value}</span> }));
vi.mock("../components/HighlightCell", () => ({ default: (p: any) => <span>{p.value}</span> }));

vi.mock("../api", () => ({
  testRunsApi: {
    list: vi.fn(), create: vi.fn(), getOne: vi.fn(), update: vi.fn(),
    submitResults: vi.fn(), complete: vi.fn(), reopen: vi.fn(),
    clone: vi.fn(), delete: vi.fn(), exportExcel: vi.fn(),
  },
  testCasesApi: {
    list: vi.fn(), create: vi.fn(), update: vi.fn(), bulkDelete: vi.fn(),
    listSheets: vi.fn(), createSheet: vi.fn(), deleteSheet: vi.fn(),
    previewImport: vi.fn(), importExcel: vi.fn(), exportExcel: vi.fn(),
    bulkUpdate: vi.fn(), delete: vi.fn(), restore: vi.fn(),
  },
  historyApi: { getTestCaseHistory: vi.fn(), getProjectHistory: vi.fn() },
  attachmentsApi: { list: vi.fn(), listByRun: vi.fn(), upload: vi.fn(), delete: vi.fn(), downloadUrl: vi.fn() },
}));

import { testRunsApi, testCasesApi, attachmentsApi } from "../api";
import { TestRunStatus } from "../types";
import TestRunManager from "../components/TestRunManager";
import TestCaseGrid from "../components/TestCaseGrid";

const adminProject = {
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin" as const,
};

const mockTC = {
  id: 1, project_id: 1, no: 1, tc_id: "TC-001", type: "기능", category: "결제",
  depth1: "", depth2: "", priority: "높음", test_type: "Web", precondition: "",
  test_steps: "1. 실행", expected_result: "성공", r1: "", r2: "", r3: "",
  issue_link: "", assignee: "", remarks: "", sheet_name: "결제",
  created_at: "2026-01-01", updated_at: "2026-01-01",
};

const run = {
  id: 7, project_id: 1, name: "결제 회귀", version: "v1", environment: "dev",
  round: 1, status: TestRunStatus.IN_PROGRESS, sheet_names: null,
  created_by: 1, created_at: "2026-01-01",
};

afterEach(async () => {
  await i18n.changeLanguage("ko");
});

beforeEach(() => {
  vi.clearAllMocks();
  gridProps = null;
  // 소요(초) 컬럼은 타이머를 켜야 생긴다. 그 헤더가 t() 를 쓰는 자리다.
  localStorage.setItem("tc_timer_enabled", "true");
  vi.mocked(testRunsApi.list).mockResolvedValue([run] as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue({
    ...run,
    results: [{
      id: 71, test_run_id: 7, test_case_id: 1, result: "NS", actual_result: "",
      issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01",
      test_case: mockTC,
    }],
  } as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "결제", parent_id: null, sort_order: 0, is_folder: false, tc_count: 1, children: [] },
  ] as any);
  vi.mocked(testCasesApi.list).mockResolvedValue([mockTC] as any);
});

function colById(defs: any[], field: string) {
  return defs.find((c) => c.field === field);
}

describe("여러 줄 텍스트 컬럼의 편집기", () => {
  it("수행 그리드의 Remarks 도 큰 편집기를 쓴다", async () => {
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());

    const remarks = colById(gridProps.columnDefs, "remarks");
    expect(remarks, "remarks 컬럼이 없다").toBeTruthy();
    expect(
      remarks.cellEditor,
      "기본 input 이 열리면 값 설정 단계에서 줄바꿈이 지워진다",
    ).toBe("agLargeTextCellEditor");
  });

  it("수행 그리드의 Actual Result 는 이미 큰 편집기를 쓴다", async () => {
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());

    expect(colById(gridProps.columnDefs, "actual_result").cellEditor).toBe("agLargeTextCellEditor");
  });
});

describe("언어 전환", () => {
  it("언어를 바꾸면 수행 그리드 헤더도 바뀐다", async () => {
    // ★columnDefs 가 t 를 클로저로 잡는데 의존성 배열에 t 가 없어서, 언어를
    //   바꿔도 헤더가 옛 언어로 남았다. 첨부 맵이 바뀔 때(다른 런을 열 때)
    //   우연히 갱신되는 것에 기대고 있었다.
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());

    const before = colById(gridProps.columnDefs, "duration_sec")?.headerName;

    await i18n.changeLanguage("en");
    await waitFor(() => {
      const after = colById(gridProps.columnDefs, "duration_sec")?.headerName;
      expect(after).not.toBe(before);
    });
  });
});

describe("찾기/바꾸기 범위", () => {
  it("필터로 걸러진 행은 바꾸지 않는다", async () => {
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(testCasesApi.list).toHaveBeenCalled());

    // 화면에 보이는 행(A)과 필터로 숨은 행(B)을 가진 그리드 API 를 흉내낸다.
    const visible = { data: { ...mockTC, id: 1, remarks: "바꿀값" } };
    const hidden = { data: { ...mockTC, id: 2, remarks: "바꿀값" } };
    const api = {
      forEachNode: (cb: (n: any) => void) => { cb(visible); cb(hidden); },
      forEachNodeAfterFilterAndSort: (cb: (n: any) => void) => { cb(visible); },
      refreshCells: vi.fn(),
      getSelectedRows: () => [],
      getSelectedNodes: () => [],
      // 검색 입력이 부른다. 없으면 테스트는 통과해도 처리되지 않은 예외가 남는다.
      setGridOption: vi.fn(),
    };
    gridProps.onGridReady?.({ api });

    const user = userEvent.setup();
    await user.type(await screen.findByPlaceholderText("검색..."), "바꿀값");
    await user.click(screen.getByTitle("바꾸기"));
    await user.type(await screen.findByPlaceholderText("바꿀 내용..."), "새값");
    await user.click(screen.getByText("모두 바꾸기"));

    expect(hidden.data.remarks, "필터로 숨은 행까지 바뀌었다").toBe("바꿀값");
    expect(visible.data.remarks).toBe("새값");
  });
});
