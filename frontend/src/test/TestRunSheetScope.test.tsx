import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">{JSON.stringify(props.rowData?.length ?? 0)}</div>
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

const sheet = (name: string, tc_count: number, extra: object = {}) => ({
  id: 1, name, parent_id: null, sort_order: 0, is_folder: false, tc_count, children: [], ...extra,
});

const mockRun = {
  id: 1, project_id: 1, name: "Sprint 1", version: "v1", environment: "dev",
  round: 1, status: TestRunStatus.IN_PROGRESS, created_by: 1, created_at: "2026-01-01",
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testRunsApi.list).mockResolvedValue([] as any);
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    sheet("로그인", 3), sheet("결제", 2), sheet("마이페이지", 4),
  ] as any);
  vi.mocked(testRunsApi.create).mockResolvedValue({ ...mockRun, id: 9 } as any);
  vi.mocked(testRunsApi.getOne).mockResolvedValue({ ...mockRun, id: 9, results: [] } as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
});

async function openModal() {
  const user = userEvent.setup();
  render(<TestRunManager projectId={1} project={adminProject as any} />);
  await waitFor(() => {
    expect(screen.getAllByText("+ 새 테스트 수행 만들기").length).toBeGreaterThan(0);
  });
  await user.click(screen.getAllByText("+ 새 테스트 수행 만들기")[0]);
  await waitFor(() => {
    expect(screen.getByText("포함할 시트")).toBeInTheDocument();
  });
  return user;
}

function sheetBox(name: string): HTMLInputElement {
  const row = screen.getByText(name).closest("label") as HTMLElement;
  return within(row).getByRole("checkbox") as HTMLInputElement;
}

describe("새 테스트 수행 - 시트 선택", () => {
  it("모달을 열면 시트가 전부 선택된 상태로 보인다", async () => {
    await openModal();
    for (const name of ["로그인", "결제", "마이페이지"]) {
      expect(sheetBox(name).checked).toBe(true);
    }
    expect(screen.getByText("3개 시트 (9개 TC)를 이 수행에 담습니다")).toBeInTheDocument();
  });

  it("체크를 풀면 고른 시트만 보낸다", async () => {
    const user = await openModal();
    await user.click(sheetBox("결제"));
    await user.click(sheetBox("마이페이지"));
    expect(screen.getByText("1개 시트 (3개 TC)를 이 수행에 담습니다")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("예: Sprint 5 기능 테스트"), "로그인 회귀");
    await user.click(screen.getByText("생성"));

    await waitFor(() => {
      expect(testRunsApi.create).toHaveBeenCalled();
    });
    const payload = vi.mocked(testRunsApi.create).mock.calls[0][1] as any;
    expect(payload.sheet_names).toEqual(["로그인"]);
  });

  it("전부 고르면 범위를 보내지 않는다", async () => {
    // ★전체 선택은 범위를 두지 않은 것과 같아야 한다. 범위를 박아 두면 나중에
    //   추가되는 시트가 진행 중 런에 들어오지 않는다.
    const user = await openModal();
    await user.type(screen.getByPlaceholderText("예: Sprint 5 기능 테스트"), "전체 회귀");
    await user.click(screen.getByText("생성"));

    await waitFor(() => {
      expect(testRunsApi.create).toHaveBeenCalled();
    });
    const payload = vi.mocked(testRunsApi.create).mock.calls[0][1] as any;
    expect(payload.sheet_names).toBeUndefined();
  });

  it("전체 해제하면 생성 버튼이 잠긴다", async () => {
    const user = await openModal();
    await user.click(screen.getByText("전체 해제"));
    expect(screen.getByText("생성").closest("button")).toBeDisabled();
  });

  it("시트가 하나뿐이면 선택 UI 를 띄우지 않는다", async () => {
    vi.mocked(testCasesApi.listSheets).mockResolvedValue([sheet("기본", 5)] as any);
    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => {
      expect(screen.getAllByText("+ 새 테스트 수행 만들기").length).toBeGreaterThan(0);
    });
    await user.click(screen.getAllByText("+ 새 테스트 수행 만들기")[0]);
    await waitFor(() => {
      expect(screen.getByText("새 테스트 수행")).toBeInTheDocument();
    });
    expect(screen.queryByText("포함할 시트")).toBeNull();
  });

  it("폴더와 TC 가 없는 시트는 고를 수 없다", async () => {
    vi.mocked(testCasesApi.listSheets).mockResolvedValue([
      sheet("모바일", 0, { is_folder: true, children: [sheet("안드로이드", 2)] }),
      sheet("웹", 3),
      sheet("빈시트", 0),
    ] as any);
    await openModal();
    expect(screen.queryByText("모바일")).toBeNull();
    expect(screen.queryByText("빈시트")).toBeNull();
    expect(sheetBox("안드로이드").checked).toBe(true);
    expect(sheetBox("웹").checked).toBe(true);
  });

  it("고른 시트로 만든 런은 그 시트의 탭만 보여 준다", async () => {
    const scoped = { ...mockRun, id: 5, name: "결제만", sheet_names: ["결제"] };
    vi.mocked(testRunsApi.list).mockResolvedValue([scoped] as any);
    vi.mocked(testRunsApi.getOne).mockResolvedValue({ ...scoped, results: [] } as any);

    const user = userEvent.setup();
    render(<TestRunManager projectId={1} project={adminProject as any} />);
    await waitFor(() => {
      expect(screen.getByText("결제만")).toBeInTheDocument();
    });
    await user.click(screen.getByText("결제만"));

    await waitFor(() => {
      expect(screen.getByTestId("ag-grid")).toBeInTheDocument();
    });
    // 범위 밖 시트 탭은 뜨지 않는다
    expect(screen.queryByText("로그인")).toBeNull();
    expect(screen.queryByText("마이페이지")).toBeNull();
  });
});
