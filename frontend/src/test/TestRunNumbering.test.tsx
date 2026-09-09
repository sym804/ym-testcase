/**
 * 테스트 수행 화면의 No 는 지금 보고 있는 목록의 순번이다.
 *
 * 재번호는 "전체" 탭 경로에만 있었다. 그런데 런 화면의 기본 탭은 첫 시트고
 * (시트가 둘 이상일 때), 시트를 골라 만든 런은 전체 탭 자체가 없다. 그래서 실제로
 * 보게 되는 화면은 대부분 재번호가 없는 쪽이었고, 저장된 no 가 그대로 나왔다.
 * 시트 안 번호에 구멍이 있으면(복제가 프로젝트 전체 max+1 을 준 TC) 4, 5, 6, 51 이 된다.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <>
      <div data-testid="run-nos">
        {(props.rowData ?? []).map((r: any) => r.test_case?.no).join(",")}
      </div>
      <div data-testid="run-tcids">
        {(props.rowData ?? []).map((r: any) => r.test_case?.tc_id).join(",")}
      </div>
    </>
  ),
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

let sheetId = 0;
const sheet = (name: string, tc_count: number, extra: object = {}) => ({
  id: ++sheetId, name, parent_id: null, sort_order: 0,
  is_folder: false, tc_count, children: [], ...extra,
});

const folder = (name: string, children: object[]) =>
  sheet(name, 0, { is_folder: true, children });

const makeRun = (overrides: object = {}) => ({
  id: 1, project_id: 1, name: "Sprint 1", version: "v1", environment: "dev",
  round: 1, status: TestRunStatus.IN_PROGRESS, created_by: 1, created_at: "2026-01-01",
  ...overrides,
});

/** 저장된 no 를 그대로 담은 결과 행. */
const result = (id: number, no: number, sheet_name: string) => ({
  id, test_run_id: 1, test_case_id: id, result: "NS",
  actual_result: "", issue_link: "", remarks: "",
  executed_by: 1, executed_at: "2026-01-01",
  test_case: {
    id, project_id: 1, no, tc_id: `TC-${id}`, type: "", category: "",
    depth1: "", depth2: "", priority: "High", test_type: "Web",
    precondition: "", test_steps: "1. 실행", expected_result: "성공",
    r1: "", r2: "", r3: "", issue_link: "", assignee: "", remarks: "",
    sheet_name, created_at: "2026-01-01", updated_at: "2026-01-01",
  },
});

function mockRun(sheets: object[], run: object, results: object[]) {
  vi.mocked(testCasesApi.listSheets).mockResolvedValue(sheets as any);
  vi.mocked(testRunsApi.list).mockResolvedValue([run] as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue({ ...run, results } as any);
}

async function openRun() {
  const user = userEvent.setup();
  render(<TestRunManager projectId={1} project={adminProject as any} />);
  await waitFor(() => expect(screen.getByText("Sprint 1")).toBeInTheDocument());
  await user.click(screen.getByText("Sprint 1"));
  await waitFor(() => expect(screen.getByTestId("run-nos")).toBeInTheDocument());
  return user;
}

const nos = () => screen.getByTestId("run-nos").textContent;
/** 번호만 보면 시트 순서가 틀려도 1,2,3,4 로 보인다. 어떤 행이 그 번호를 받았는지 같이 본다. */
const tcIds = () => screen.getByTestId("run-tcids").textContent;

beforeEach(() => {
  vi.clearAllMocks();
  sheetId = 0;
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
});

describe("테스트 수행 화면의 No", () => {
  it("시트 하나로 범위를 잡은 런은 1 부터 매긴다", async () => {
    mockRun(
      [sheet("로그인", 3), sheet("결제", 4)],
      makeRun({ sheet_names: ["결제"] }),
      // 51 은 복제가 프로젝트 전체 max+1 을 준 흔적이다.
      [result(1, 4, "결제"), result(2, 5, "결제"),
       result(3, 6, "결제"), result(4, 51, "결제")],
    );

    await openRun();

    await waitFor(() => expect(nos()).toBe("1,2,3,4"));
  });

  it("시트 탭을 눌러도 그 시트 안에서 1 부터 매긴다", async () => {
    mockRun(
      [sheet("로그인", 2), sheet("결제", 2)],
      makeRun({}),
      [result(1, 3, "로그인"), result(2, 5, "로그인"),
       result(3, 7, "결제"), result(4, 9, "결제")],
    );

    // 시트가 둘 이상이면 기본 탭이 첫 시트다.
    const user = await openRun();
    await waitFor(() => expect(nos()).toBe("1,2"));

    await user.click(screen.getByText("결제"));

    await waitFor(() => expect(nos()).toBe("1,2"));
  });

  it("시트를 폴더 하나에 모아 둔 프로젝트도 전체 탭에서 1 부터 매긴다", async () => {
    // 트리 루트가 폴더 하나뿐이다. 루트 개수로 판정하면 재번호가 걸리지 않는다.
    mockRun(
      [folder("회귀", [sheet("로그인", 2), sheet("결제", 2)])],
      makeRun({}),
      [result(1, 11, "로그인"), result(2, 12, "로그인"),
       result(3, 20, "결제"), result(4, 21, "결제")],
    );

    const user = await openRun();
    // 폴더로 묶었어도 기본 탭은 첫 잎 시트다. flat 프로젝트와 같아야 한다.
    await waitFor(() => expect(nos()).toBe("1,2"));
    await user.click(screen.getByText("전체"));

    await waitFor(() => expect(nos()).toBe("1,2,3,4"));
    expect(tcIds()).toBe("TC-1,TC-2,TC-3,TC-4");
  });

  it("전체 탭은 시트 순서대로 세운 뒤 이어서 매긴다", async () => {
    mockRun(
      [sheet("로그인", 2), sheet("결제", 2)],
      makeRun({}),
      // 런에 편입된 순서로 온다. 결제가 먼저 와도 화면은 시트 순서를 따른다.
      [result(3, 5, "결제"), result(1, 1, "로그인"),
       result(4, 6, "결제"), result(2, 2, "로그인")],
    );

    const user = await openRun();
    await user.click(screen.getByText("전체"));

    await waitFor(() => expect(nos()).toBe("1,2,3,4"));
    expect(tcIds()).toBe("TC-1,TC-2,TC-3,TC-4");
  });

  it("런에 나중에 들어온 TC 도 번호 순서를 지킨다", async () => {
    // 런 생성 뒤 추가된 TC 는 결과 행 끝에 붙는다. 화면은 no 순서로 세운다.
    mockRun(
      [sheet("결제", 3)],
      makeRun({ sheet_names: ["결제"] }),
      [result(1, 2, "결제"), result(2, 4, "결제"), result(3, 3, "결제")],
    );

    await openRun();

    await waitFor(() => expect(nos()).toBe("1,2,3"));
    expect(tcIds()).toBe("TC-1,TC-3,TC-2");
  });

  it("전체 탭은 시트가 늦게 와도 순서를 다시 잡는다", async () => {
    // 런 목록이 먼저 오고 시트 목록이 늦게 올 수 있다. 그 사이에 런을 열면
    // 시트 순서를 모른 채 세우게 되는데, 뒤늦게 도착해도 화면이 그대로 남으면
    // 스스로 고쳐지지 않는다.
    let resolveSheets: (v: unknown) => void = () => {};
    vi.mocked(testCasesApi.listSheets).mockReturnValue(
      new Promise((res) => { resolveSheets = res; }) as any,
    );
    const run = makeRun({});
    vi.mocked(testRunsApi.list).mockResolvedValue([run] as any);
    vi.mocked(testRunsApi.getOne).mockResolvedValue({
      ...run,
      // 시트 순서(로그인 먼저)와 no 순서(결제가 작다)를 일부러 어긋나게 둔다.
      // 같으면 시트 순서를 몰라도 결과가 맞아 버려 이 테스트가 아무것도 못 잡는다.
      results: [
        result(3, 1, "결제"), result(1, 5, "로그인"),
        result(4, 2, "결제"), result(2, 6, "로그인"),
      ],
    } as any);

    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => expect(screen.getByText("Sprint 1")).toBeInTheDocument());
    await user.click(screen.getByText("Sprint 1"));
    await waitFor(() => expect(screen.getByTestId("run-nos")).toBeInTheDocument());

    // 시트를 폴더 하나에 모아 둔 프로젝트다. 기본 탭이 전체로 남아 탭 전환이
    // 일어나지 않으므로, 재계산을 걸어 두지 않으면 잘못된 순서가 그대로 남는다.
    resolveSheets([folder("회귀", [sheet("로그인", 2), sheet("결제", 2)])]);

    // 시트가 도착하면 기본 탭이 정해지며 상세를 다시 받는다. 도착 전 순서(결제가
    // no 가 작아 앞)로 남아 있으면 여기서 걸린다.
    await waitFor(() => expect(tcIds()).toBe("TC-1,TC-2"));
    await user.click(screen.getByText("전체"));
    await waitFor(() => expect(tcIds()).toBe("TC-1,TC-2,TC-3,TC-4"));
    expect(nos()).toBe("1,2,3,4");
  });

  it("루트에 폴더가 섞여 있어도 기본 탭은 잎 시트다", async () => {
    // 루트 첫 칸이 폴더면 폴더 이름으로 걸러 그리드가 빈 채로 열리고, 보정이
    // 뒤늦게 잎 시트로 옮기면서 상세를 두 번 받는다.
    mockRun(
      [folder("회귀", [sheet("로그인", 2)]), sheet("웹", 2)],
      makeRun({}),
      [result(1, 3, "로그인"), result(2, 8, "로그인"),
       result(3, 4, "웹"), result(4, 6, "웹")],
    );

    await openRun();

    await waitFor(() => expect(nos()).toBe("1,2"));
    expect(vi.mocked(testRunsApi.getOne)).toHaveBeenCalledTimes(1);
  });

  it("저장된 no 를 덮어쓰지 않는다", async () => {
    // 화면 번호는 표시용이다. 결과 저장 payload 에 no 가 실려 가지는 않지만,
    // 서버가 준 객체를 제자리에서 고치면 다음에 그 값을 읽는 쪽이 물린다.
    const results = [result(1, 4, "결제"), result(2, 51, "결제")];
    mockRun([sheet("결제", 2)], makeRun({ sheet_names: ["결제"] }), results);

    await openRun();
    await waitFor(() => expect(nos()).toBe("1,2"));

    expect(results.map((r) => r.test_case.no)).toEqual([4, 51]);
  });
});
