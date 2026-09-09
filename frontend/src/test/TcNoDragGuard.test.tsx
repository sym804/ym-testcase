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

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => {
    lastColumnDefs = props.columnDefs ?? [];
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
    // 시트가 둘이면 기본 탭은 첫 시트다. 전체 탭으로 옮겨 확인한다.
    const user = userEvent.setup();
    await renderGrid(
      [sheet("로그인", 1, 1), sheet("결제", 1, 2)],
      [tc(1, 1, "로그인"), tc(2, 1, "결제")],
    );
    await waitFor(() => expect(noColumnDrag()).toBe(true));

    await user.click(screen.getByText("전체"));

    await waitFor(() => expect(noColumnDrag()).toBe(false));
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
