/**
 * 드래그 정렬은 한 시트를 통째로 보고 있을 때만 켠다.
 *
 * 정렬은 지금 보이는 행에 1..N 을 다시 매겨 서버로 보낸다. 전체 보기는 시트 경계를
 * 넘는 연번을 그리고, 검색 중에는 숨은 행이 빠진다. 그대로 저장하면 시트 안 번호가
 * 겹치거나 규약이 무너진다. 서버도 400 으로 막지만, 끌어 놓고 나서 실패를 보는 것
 * 보다 못 끌게 하는 편이 낫다.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

let lastColumnDefs: any[] = [];

let lastProps: any = null;

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => {
    lastColumnDefs = props.columnDefs ?? [];
    lastProps = props;
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

vi.mock("../api", () => ({
  testCasesApi: {
    list: vi.fn(), create: vi.fn(), update: vi.fn(), bulkDelete: vi.fn(),
    listSheets: vi.fn(), createSheet: vi.fn(), deleteSheet: vi.fn(),
    previewImport: vi.fn(), importExcel: vi.fn(), exportExcel: vi.fn(),
    bulkUpdate: vi.fn(), delete: vi.fn(), restore: vi.fn(), reorder: vi.fn(),
  },
  historyApi: { getTestCaseHistory: vi.fn(), getProjectHistory: vi.fn() },
}));

import { testCasesApi } from "../api";
import TestCaseGrid from "../components/TestCaseGrid";
import type { SheetNode } from "../types";

const adminProject = {
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01",
  my_role: "admin" as const,
};

const viewerProject = { ...adminProject, my_role: "viewer" as const };

const sheet = (name: string, tc_count: number, id: number): SheetNode =>
  ({ id, name, parent_id: null, sort_order: 0, is_folder: false, tc_count, children: [] });

const tc = (id: number, no: number, sheet_name: string) => ({
  id, project_id: 1, no, tc_id: `TC-${id}`, type: "", category: "",
  depth1: "", depth2: "", priority: "High", test_type: "Web",
  precondition: "", test_steps: "1. 실행", expected_result: "성공",
  r1: "", r2: "", r3: "", remarks: "", sheet_name,
  created_at: "2026-01-01", updated_at: "2026-01-01",
});

const noColumn = () => lastColumnDefs.find((c) => c.field === "no");
/** No 컬럼의 rowDrag 설정. */
const noColumnDrag = () => noColumn()?.rowDrag;

beforeEach(() => {
  vi.clearAllMocks();
  lastColumnDefs = [];
});

async function renderGrid(sheets: SheetNode[], rows: any[], project: any = adminProject) {
  vi.mocked(testCasesApi.listSheets).mockResolvedValue(sheets);
  vi.mocked(testCasesApi.list).mockResolvedValue(rows as any);
  render(<TestCaseGrid projectId={project.id} project={project} />);
  await waitFor(() => expect(screen.getByTestId("ag-grid")).toBeInTheDocument());
}

describe("드래그 정렬을 켜는 조건", () => {
  it("시트 하나를 보고 있으면 켠다", async () => {
    await renderGrid([sheet("결제", 2, 1)], [tc(1, 1, "결제"), tc(2, 2, "결제")]);

    await waitFor(() => expect(noColumnDrag()).toBe(true));
  });

  it("전체 보기에서는 끈다", async () => {
    // 시트가 둘이면 기본 탭은 전체다. 시트를 골랐다가 전체로 돌아와도 꺼진다.
    const user = userEvent.setup();
    await renderGrid(
      [sheet("로그인", 1, 1), sheet("결제", 1, 2)],
      [tc(1, 1, "로그인"), tc(2, 1, "결제")],
    );
    await waitFor(() => expect(noColumnDrag()).toBe(false));

    await user.click(screen.getByText("로그인"));
    await waitFor(() => expect(noColumnDrag()).toBe(true));

    await user.click(screen.getByText("전체"));
    await waitFor(() => expect(noColumnDrag()).toBe(false));
  });

  it("시트가 여럿이면 전체로 열고 시트 조건 없이 조회한다", async () => {
    // 예전에는 첫 시트를 자동으로 골라 전체 요청과 첫 시트 요청이 겹쳤고,
    // 늦게 온 전체 응답이 덮어 사이드바는 첫 시트인데 표는 전체였다.
    await renderGrid(
      [sheet("로그인", 1, 1), sheet("결제", 1, 2)],
      [tc(1, 1, "로그인"), tc(2, 1, "결제")],
    );
    await waitFor(() => expect(testCasesApi.list).toHaveBeenCalled());
    const calls = vi.mocked(testCasesApi.list).mock.calls;
    expect(calls.every(([, params]) => !params?.sheet_name)).toBe(true);
  });

  it("늦게 도착한 옛 응답은 표를 덮지 않는다", async () => {
    const user = userEvent.setup();
    let releaseAll: (v: any) => void = () => {};
    vi.mocked(testCasesApi.listSheets).mockResolvedValue([sheet("로그인", 1, 1), sheet("결제", 1, 2)]);
    vi.mocked(testCasesApi.list).mockImplementation((_pid: number, params?: any) =>
      params?.sheet_name
        ? Promise.resolve([tc(1, 1, params.sheet_name)] as any)
        // 전체 요청은 붙잡아 둔다. 시트 응답보다 늦게 풀어 준다.
        : new Promise((r) => { releaseAll = r; }) as any,
    );
    render(<TestCaseGrid projectId={1} project={adminProject} />);
    // 전체 요청이 붙잡혀 있는 동안은 로딩 중이라 표가 없다. 사이드바에서 바로 고른다.
    await user.click(await screen.findByText("결제"));
    await waitFor(() => expect(lastProps.rowData?.[0]?.sheet_name).toBe("결제"));

    releaseAll([tc(1, 1, "로그인"), tc(2, 1, "결제"), tc(3, 2, "결제")]);
    await new Promise((r) => setTimeout(r, 50));
    expect(lastProps.rowData.map((r: any) => r.sheet_name)).toEqual(["결제"]);
  });

  it("활성 시트를 지워 하나만 남으면 남은 시트를 선택한다", async () => {
    // 지운 시트가 활성이면 null 이 된다. 예전에는 처음 열 때만 자동 선택해서,
    // 시트가 하나뿐인데도 행 추가와 드래그 정렬이 막혔다.
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.mocked(testCasesApi.deleteSheet).mockResolvedValue({} as any);
    vi.mocked(testCasesApi.listSheets)
      .mockResolvedValueOnce([sheet("로그인", 1, 1), sheet("결제", 1, 2)])
      .mockResolvedValue([sheet("결제", 1, 2)]);
    vi.mocked(testCasesApi.list).mockResolvedValue([tc(1, 1, "결제")] as any);
    render(<TestCaseGrid projectId={1} project={adminProject} />);

    await user.click(await screen.findByText("로그인"));
    await waitFor(() => expect(noColumnDrag()).toBe(true));

    await user.click(screen.getAllByTitle("시트 삭제")[0]);
    await waitFor(() => expect(testCasesApi.deleteSheet).toHaveBeenCalledWith(1, "로그인"));
    await waitFor(() => expect(noColumnDrag()).toBe(true));
    expect(vi.mocked(testCasesApi.list).mock.calls.at(-1)?.[1]).toEqual({ sheet_name: "결제" });
  });

  it("검색 중에는 끈다", async () => {
    const user = userEvent.setup();
    await renderGrid([sheet("결제", 2, 1)], [tc(1, 1, "결제"), tc(2, 2, "결제")]);
    await waitFor(() => expect(noColumnDrag()).toBe(true));

    await user.type(screen.getByPlaceholderText(/검색/), "로그인");

    await waitFor(() => expect(noColumnDrag()).toBe(false));
  });

  it("편집 권한이 없으면 끈다", async () => {
    await renderGrid([sheet("결제", 1, 1)], [tc(1, 1, "결제")], viewerProject);

    await waitFor(() => expect(noColumnDrag()).toBe(false));
  });
});

describe("No 컬럼 편집", () => {
  it("No 는 손으로 고칠 수 없다", async () => {
    // 서버가 보낸 값을 쓰지 않으므로, 열어 두면 화면과 DB 가 갈린다.
    await renderGrid([sheet("결제", 1, 1)], [tc(1, 1, "결제")]);

    await waitFor(() => expect(noColumn()).toBeTruthy());
    expect(noColumn()?.editable).toBe(false);
  });
});

describe("드래그 저장 직전 검사", () => {
  /** 화면에 보이는 행과 정렬 상태를 흉내낸 그리드 API. */
  const fakeApi = (visible: any[], sortState: any[] = []) => ({
    forEachNodeAfterFilterAndSort: (fn: (n: any) => void) =>
      visible.forEach((data) => fn({ data })),
    getColumnState: () => sortState,
    refreshCells: () => {},
  });

  const rows = [tc(1, 1, "결제"), tc(2, 2, "결제"), tc(3, 3, "결제")];

  it("한 시트 전체를 보고 있으면 보낸다", async () => {
    vi.mocked(testCasesApi.reorder).mockResolvedValue({ updated: 3 } as any);
    await renderGrid([sheet("결제", 3, 1)], rows);
    await waitFor(() => expect(lastProps).toBeTruthy());

    lastProps.onGridReady({ api: fakeApi([...rows].reverse()) });
    await lastProps.onRowDragEnd();

    await waitFor(() => expect(testCasesApi.reorder).toHaveBeenCalled());
    const sent = vi.mocked(testCasesApi.reorder).mock.calls[0][1];
    expect(sent.map((x: any) => x.no)).toEqual([1, 2, 3]);
  });

  it("일부만 보이면 보내지 않는다", async () => {
    await renderGrid([sheet("결제", 3, 1)], rows);
    await waitFor(() => expect(lastProps).toBeTruthy());

    lastProps.onGridReady({ api: fakeApi(rows.slice(0, 2)) });
    await lastProps.onRowDragEnd();

    expect(testCasesApi.reorder).not.toHaveBeenCalled();
  });

  it("정렬이 걸려 있으면 보내지 않는다", async () => {
    // 행 수는 그대로라 개수 비교로는 안 걸린다.
    await renderGrid([sheet("결제", 3, 1)], rows);
    await waitFor(() => expect(lastProps).toBeTruthy());

    lastProps.onGridReady({ api: fakeApi(rows, [{ colId: "tc_id", sort: "asc" }]) });
    await lastProps.onRowDragEnd();

    expect(testCasesApi.reorder).not.toHaveBeenCalled();
  });

  it("거절할 때 화면 번호를 미리 바꾸지 않는다", async () => {
    const local = [tc(1, 1, "결제"), tc(2, 2, "결제"), tc(3, 3, "결제")];
    await renderGrid([sheet("결제", 3, 1)], local);
    await waitFor(() => expect(lastProps).toBeTruthy());

    const visible = local.slice(0, 2);
    lastProps.onGridReady({ api: fakeApi(visible) });
    await lastProps.onRowDragEnd();

    expect(visible.map((r) => r.no)).toEqual([1, 2]);
  });
});
