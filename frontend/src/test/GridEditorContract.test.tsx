import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "../i18n";

// 두 그리드가 거의 같은 코드인데 한쪽만 고쳐 온 이력이 있다.
// - 여러 줄 텍스트 컬럼에 큰 편집기를 안 달면 기본 input 이 열려 줄바꿈이 지워진다(SYM-25).
//   그때 TC 그리드만 고치고 수행 그리드가 빠졌다.
// - 찾기/바꾸기가 forEachNode 를 쓰면 필터로 숨은 행까지 바꾼다.
// - 사전조건 열이 TC 그리드에만 있었다(SYM-108). 수행자가 실행 직전에 갖춰야 할
//   상태를 보려고 TC 관리 화면을 따로 열어야 했다.
// - Platform(test_type)도 같은 모양으로 빠져 있었다(SYM-109).
// - 프로젝트의 필드 표시 설정을 TC 그리드만 따랐다(SYM-111). 이름을 바꾸거나
//   숨겨도 수행 그리드는 영문 기본값을 그대로 보여 줬다.
// - Ctrl+D 가 읽기 전용 TC 열에서도 "채웠다" 고 알렸다(SYM-110).
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
vi.mock("../components/PreconditionCell", () => ({ default: (p: any) => <span>{p.value}</span> }));

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
import { PRIORITY_COLORS, priorityCellStyle } from "../utils/priority";
import IssueLinkCell from "../components/IssueLinkCell";
import TestCaseGrid from "../components/TestCaseGrid";
import PreconditionCell from "../components/PreconditionCell";
import { resolveItems } from "../utils/precondition";
import toast from "react-hot-toast";

const adminProject = {
  // 이슈 링크 칸이 context 로 받는 값을 확인하려고 주소를 채워 둔다
  id: 1, name: "P", description: "", jira_base_url: "https://linear.app/x", is_private: false,
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

describe("수행 그리드의 사전조건", () => {
  // 사전조건은 실행 직전에 갖춰야 하는 상태라 수행자가 봐야 한다.
  // TC 그리드에만 있어서 수행 중에 화면을 옮겨다녀야 했다(SYM-108).
  const REFERRING = `1. 로그인한 상태
2. TC-002 의 사전조건 참조`;

  async function openRunWithPrecondition() {
    vi.mocked(testRunsApi.getOne).mockResolvedValue({
      ...run,
      results: [
        {
          id: 71, test_run_id: 7, test_case_id: 1, result: "NS", actual_result: "",
          issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01",
          test_case: { ...mockTC, id: 1, tc_id: "TC-001", precondition: REFERRING },
        },
        {
          id: 72, test_run_id: 7, test_case_id: 2, result: "NS", actual_result: "",
          issue_link: "", remarks: "", executed_by: 1, executed_at: "2026-01-01",
          test_case: { ...mockTC, id: 2, tc_id: "TC-002", precondition: "1. 결제 수단이 등록되어 있다" },
        },
      ],
    } as any);
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());
  }

  it("사전조건 열이 있다", async () => {
    await openRunWithPrecondition();
    const col = colById(gridProps.columnDefs, "test_case.precondition");
    expect(col, "수행 그리드에 사전조건 열이 없다").toBeTruthy();
  });

  it("값은 그 행의 TC 사전조건이다", async () => {
    await openRunWithPrecondition();
    const col = colById(gridProps.columnDefs, "test_case.precondition");
    const got = col.valueGetter({ data: { test_case: { precondition: "준비 상태" } } });
    expect(got).toBe("준비 상태");
    // test_case 가 비어도 터지지 않아야 한다. 삭제된 TC 의 결과 행이 그렇다.
    expect(col.valueGetter({ data: {} })).toBe("");
  });

  it("읽기 전용이다", async () => {
    // 수행 중에 TC 원문이 고쳐지면 다른 런의 기준까지 바뀐다.
    await openRunWithPrecondition();
    const col = colById(gridProps.columnDefs, "test_case.precondition");
    expect(col.editable, "사전조건이 편집 가능하면 TC 원문이 수행 중에 바뀐다").toBe(false);
  });

  it("이슈 링크 칸은 이슈 관리 도구로 여는 렌더러를 쓰고 편집 가능하다", async () => {
    await openRunWithPrecondition();
    const col = colById(gridProps.columnDefs, "issue_link");
    expect(col.cellRenderer, "이슈 키가 링크로 이어지지 않는다(SYM-123)").toBe(IssueLinkCell);
    expect(col.editable).toBe(true);
    // 렌더러는 주소를 context 에서 읽는다. 여기서 빠지면 링크가 조용히 안 생긴다.
    expect(gridProps.context.trackerUrl).toBe("https://linear.app/x");
  });

  it("우선순위 칸은 TC 관리 그리드와 같은 색을 쓴다", async () => {
    await openRunWithPrecondition();
    const col = colById(gridProps.columnDefs, "test_case.priority");
    // 같은 함수여야 한다. 따로 들고 있으면 한쪽만 고쳤을 때 두 화면 색이 갈라진다.
    expect(col.cellStyle, "수행 그리드 우선순위에 색이 없다").toBe(priorityCellStyle);
    expect(col.cellStyle({ value: "매우 높음" })).toEqual({ color: PRIORITY_COLORS["매우 높음"], fontWeight: 600 });
    // 표시 이름은 testcase 네임스페이스의 priorityDisplay 를 따른다. 목록 밖의 값은 원문이다.
    expect(col.valueFormatter({ value: "High" })).toBe("High");
  });

  it("참조를 푸는 렌더러를 쓴다", async () => {
    await openRunWithPrecondition();
    const col = colById(gridProps.columnDefs, "test_case.precondition");
    expect(col.cellRenderer, "참조가 원문 그대로 보인다").toBe(PreconditionCell);
  });

  it("참조 색인이 context 로 간다", async () => {
    // 색인이 없으면 렌더러가 참조를 못 풀고 툴팁이 비어 보인다.
    await openRunWithPrecondition();
    const index = gridProps.context?.preconditionIndex as Map<string, string> | undefined;
    expect(index, "preconditionIndex 가 context 에 없다").toBeTruthy();
    expect(index!.get("TC-002")).toBe("1. 결제 수단이 등록되어 있다");
  });

  it("색인은 런에 담긴 TC 로만 만든다", async () => {
    // 프로젝트 전체 TC 를 따로 받지 않는다. 수행 화면을 열 때마다 조회가 한 번 더
    // 붙기 때문이다. 대신 시트를 골라 만든 런에서 다른 시트를 참조하면 색인에 없다.
    // 그때 조용히 비면 사용자는 툴팁이 고장난 줄 안다. 안내 문구가 나와야 한다.
    await openRunWithPrecondition();
    const index = gridProps.context.preconditionIndex as Map<string, string>;

    const items = resolveItems("TC-다른시트", index);
    expect(items, "안내가 한 줄로 오지 않는다").toHaveLength(1);
    expect(items[0], "어느 TC 를 못 찾았는지 알려주지 않는다").toContain("TC-다른시트");

    // 런에 있는 TC 는 정상으로 펼쳐진다.
    // 번호 접두사는 splitItems 가 떼어 낸다. 화면에서 다시 붙이는 몫이다.
    expect(resolveItems("TC-002", index)).toEqual(["결제 수단이 등록되어 있다"]);
  });

  it("검색어 하이라이트 context 는 그대로 간다", async () => {
    // preconditionIndex 를 넣으면서 기존 키를 덮어쓴 적이 있다.
    await openRunWithPrecondition();
    expect(gridProps.context).toHaveProperty("searchKeyword");
  });
});


describe("수행 그리드의 Platform", () => {
  // 사전조건(SYM-108)과 같은 모양의 누락이다. TC 그리드와 TC 목록 엑셀에는 있고
  // 프로젝트 설정에 숨김 가능 필드로 등록돼 있는데 수행 화면에만 없었다.
  async function openRun() {
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());
  }

  it("Platform 열이 있다", async () => {
    await openRun();
    expect(colById(gridProps.columnDefs, "test_case.test_type"), "Platform 열이 없다").toBeTruthy();
  });

  it("읽기 전용이다", async () => {
    await openRun();
    expect(colById(gridProps.columnDefs, "test_case.test_type").editable).toBe(false);
  });

  it("값은 그 행의 TC Platform 이다", async () => {
    await openRun();
    const col = colById(gridProps.columnDefs, "test_case.test_type");
    expect(col.valueGetter({ data: { test_case: { test_type: "Android" } } })).toBe("Android");
    expect(col.valueGetter({ data: {} })).toBe("");
  });
});

describe("수행 그리드와 프로젝트 필드 설정", () => {
  // TC 그리드만 field_config 를 따랐다. 이름을 "사전조건 / 테스트 데이터" 로 바꾼
  // 프로젝트에서 두 화면의 헤더가 다르게 보였다(SYM-111).
  const configured = {
    ...adminProject,
    field_config: {
      tc_id: { display_name: "케이스 번호", visible: true },
      precondition: { display_name: "사전조건 / 테스트 데이터", visible: true },
      test_type: { display_name: "플랫폼", visible: true },
      priority: { display_name: "우선순위", visible: false },
      remarks: { display_name: "TC 비고", visible: false },
    },
  };

  async function openRunWith(project: any) {
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={project} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());
  }

  it("바꾼 표시 이름을 쓴다", async () => {
    await openRunWith(configured);
    expect(colById(gridProps.columnDefs, "test_case.precondition").headerName).toBe("사전조건 / 테스트 데이터");
    expect(colById(gridProps.columnDefs, "test_case.test_type").headerName).toBe("플랫폼");
    // tc_id 는 숨길 수 없지만 이름은 바꿀 수 있다. 그 열만 하드코딩으로 남아 있었다.
    expect(colById(gridProps.columnDefs, "test_case.tc_id").headerName).toBe("케이스 번호");
  });

  it("숨긴 필드는 수행 그리드에서도 빠진다", async () => {
    await openRunWith(configured);
    expect(colById(gridProps.columnDefs, "test_case.priority"), "숨긴 필드가 그대로 있다").toBeUndefined();
  });

  it("설정이 없으면 기본 이름을 쓴다", async () => {
    await openRunWith(adminProject);
    expect(colById(gridProps.columnDefs, "test_case.precondition").headerName).toBe("Precondition");
    expect(colById(gridProps.columnDefs, "test_case.priority")).toBeTruthy();
  });

  it("수행 전용 Remarks 는 TC 의 remarks 설정에 휘둘리지 않는다", async () => {
    // ★이름만 같고 다른 값이다. 수행 그리드의 Remarks 는 TestResult.remarks 이고
    //   field_config 의 remarks 는 TestCase.remarks 다. 위 설정은 remarks 를
    //   숨김으로 뒀는데, 그것 때문에 수행 결과 비고가 사라지면 결과를 못 적는다.
    await openRunWith(configured);
    const col = colById(gridProps.columnDefs, "remarks");
    expect(col, "수행 결과 비고 열이 사라졌다").toBeTruthy();
    expect(col.headerName).toBe("Remarks");
  });
});

describe("읽기 전용 열에서의 Ctrl+D", () => {
  // 읽기 전용 TC 열에서 Ctrl+D 를 누르면 값은 안 바뀌는데 "채웠다" 토스트가 뜨고
  // 저장 요청이 나갔다(SYM-110). node.data["test_case.precondition"] 처럼 점 찍힌
  // 키가 평평하게 새로 생겨서 화면 값은 그대로였다.
  async function openRun() {
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.onCellKeyDown).toBeTruthy());
  }

  // ★colDef 를 손으로 만들지 않고 실제 columnDefs 에서 찾아 쓴다. 손으로 만들면
  //   테스트가 구현과 같은 가정을 공유해, editable 을 아예 안 쓴 열(undefined)이
  //   있다는 사실 자체를 못 본다.
  function ctrlD(colId: string, targets: any[]) {
    const colDef = gridProps.columnDefs.find(
      (c: any) => c.field === colId || c.colId === colId,
    );
    expect(colDef, `${colId} 열이 그리드에 없다`).toBeTruthy();

    const source = { data: { id: 71, result: "원본", test_case: { precondition: "원본" } } };
    const api = {
      getSelectedNodes: () => [source, ...targets],
      refreshCells: vi.fn(),
      forEachNode: vi.fn(),
      setGridOption: vi.fn(),
    };
    // ★핸들러는 event.api 가 아니라 gridApiRef.current 를 쓴다. 이것을 안 채우면
    //   `if (!api) return` 에서 조용히 빠져나가, 읽기 전용 테스트가 거짓으로
    //   통과한다(처음에 그렇게 썼다가 짝 테스트가 실패해서 알았다).
    gridProps.onGridReady?.({ api });
    gridProps.onCellKeyDown({
      event: { key: "d", ctrlKey: true, preventDefault: () => {} },
      column: { getColId: () => colId, getColDef: () => colDef },
      value: "원본",
      node: source,
      api,
    });
  }

  it("읽기 전용 TC 열에서는 아무 일도 하지 않는다", async () => {
    await openRun();
    const target = { data: { id: 72, test_case: { precondition: "대상" } } };

    ctrlD("test_case.precondition", [target]);

    expect(toast.success, "채웠다고 알렸다").not.toHaveBeenCalled();
    expect(
      Object.prototype.hasOwnProperty.call(target.data, "test_case.precondition"),
      "점 찍힌 평평한 키가 생겼다",
    ).toBe(false);
    expect(testRunsApi.submitResults, "저장 요청이 나갔다").not.toHaveBeenCalled();
  });

  it("editable 을 안 쓴 읽기 전용 열도 막힌다", async () => {
    // ★editable 이 undefined 인 열이 아홉이다(No, TC ID, Category, Depth 1/2,
    //   Priority, 절차, 기대 결과, 소요). "editable !== false 면 통과" 로
    //   판정하면 이것들이 전부 새어 나간다.
    await openRun();
    const target = { data: { id: 72, test_case: { tc_id: "TC-002" } } };

    ctrlD("test_case.tc_id", [target]);

    expect(toast.success).not.toHaveBeenCalled();
    expect(Object.prototype.hasOwnProperty.call(target.data, "test_case.tc_id")).toBe(false);
  });

  it("소요(초) 는 채우지 않는다", async () => {
    // 타이머가 잰 값이라 사람이 퍼뜨릴 값이 아니다. 게다가 저장 본문
    // 화이트리스트에 있어서 그냥 두면 측정값이 실제로 덮어써진다.
    await openRun();
    const target = { data: { id: 72, duration_sec: 42 } };

    ctrlD("duration_sec", [target]);

    expect(target.data.duration_sec, "측정된 수행 시간이 덮어써졌다").toBe(42);
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("Result 열은 그대로 채워진다", async () => {
    // ★Ctrl+D 의 주 용도다. 매뉴얼이 "동일 결과 반복 시" 라고 적고 있다.
    //   Result 는 커스텀 렌더러를 쓰느라 editable:false 라서, 편집 가능 여부로
    //   판정하면 이 기능이 죽는다.
    await openRun();
    const target = { data: { id: 72, test_case_id: 2, result: "NS" } };

    ctrlD("result", [target]);

    expect(target.data.result, "결과가 채워지지 않았다").toBe("원본");
    expect(toast.success).toHaveBeenCalled();
    expect(testRunsApi.submitResults, "저장 요청이 나가지 않았다").toHaveBeenCalled();
  });

  it("실제 결과 열도 그대로 채워진다", async () => {
    await openRun();
    const target = { data: { id: 72, test_case_id: 2, actual_result: "" } };

    ctrlD("actual_result", [target]);

    expect(target.data.actual_result).toBe("원본");
    expect(toast.success).toHaveBeenCalled();
  });
});

describe("셀 선택과 편집 진입", () => {
  // 클릭 한 번에 편집기가 열리면 TC 를 눈으로 훑는 동안 값이 바뀔 수 있고,
  // 편집기가 떠 있는 칸은 텍스트를 끌어서 복사할 수 없다. 수행 시트에서
  // 절차나 기대 결과를 복사하려던 것이 매번 막혔다.
  // 두 그리드가 같은 규칙을 따라야 화면을 옮길 때 조작이 달라지지 않는다.

  async function openRunGrid() {
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("결제 회귀")).toBeInTheDocument());
    await user.click(screen.getByText("결제 회귀"));
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());
    return gridProps;
  }

  async function openTcGrid() {
    render(<TestCaseGrid projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(testCasesApi.list).toHaveBeenCalled());
    await waitFor(() => expect(gridProps?.columnDefs).toBeTruthy());
    return gridProps;
  }

  it("수행 그리드는 클릭 한 번으로 편집기를 열지 않는다", async () => {
    const p = await openRunGrid();
    expect(p.singleClickEdit, "클릭만 해도 편집기가 열린다").not.toBe(true);
  });

  it("수행 그리드는 셀 텍스트를 끌어서 선택할 수 있다", async () => {
    const p = await openRunGrid();
    expect(p.enableCellTextSelection, "셀 텍스트를 선택할 수 없다").toBe(true);
    // ensureDomOrder 가 없으면 DOM 순서가 화면 순서와 달라져 여러 행에 걸친
    // 선택 범위가 엉뚱하게 잡힌다. AG Grid 가 둘을 함께 켜라고 요구한다.
    expect(p.ensureDomOrder, "DOM 순서를 맞추지 않아 선택 범위가 어긋난다").toBe(true);
  });

  it("TC 그리드는 클릭 한 번으로 편집기를 열지 않는다", async () => {
    const p = await openTcGrid();
    expect(p.singleClickEdit, "클릭만 해도 편집기가 열린다").not.toBe(true);
  });

  it("TC 그리드는 셀 텍스트를 끌어서 선택할 수 있다", async () => {
    const p = await openTcGrid();
    expect(p.enableCellTextSelection, "셀 텍스트를 선택할 수 없다").toBe(true);
    expect(p.ensureDomOrder, "DOM 순서를 맞추지 않아 선택 범위가 어긋난다").toBe(true);
  });

  it("수행 그리드에서 편집 가능한 열은 셋뿐이다", async () => {
    // ★수행 화면에서 TC 원문을 고치면 같은 TC 를 담은 다른 런의 기준까지 흔들린다.
    //   편집 진입 방식을 바꾸다가 읽기 전용이 풀리지 않았는지 여기서 잡는다.
    const p = await openRunGrid();
    const editable = p.columnDefs
      .filter((c: any) => c.editable === true)
      .map((c: any) => c.field)
      .sort();
    expect(editable).toEqual(["actual_result", "issue_link", "remarks"]);
  });
});
