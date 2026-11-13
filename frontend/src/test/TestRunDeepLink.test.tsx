import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";

// 메인 화면의 수행 링크(?tab=run&run=<id>)로 들어오면 그 수행이 열린다(SYM-225).
// 주소는 ProjectPage 가 읽어 openRunId 로 넘기고, 연 뒤 onRunOpened 로 지운다.
vi.mock("ag-grid-react", () => ({
  AgGridReact: (props: any) => <div data-testid="ag-grid">{props.rowData?.length ?? 0}</div>,
}));

vi.mock("ag-grid-community", () => ({
  AllCommunityModule: {},
  ModuleRegistry: { registerModules: () => {} },
}));

vi.mock("react-hot-toast", () => {
  const fn: any = vi.fn();
  fn.success = vi.fn();
  fn.error = vi.fn();
  return { default: fn };
});

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

import toast from "react-hot-toast";
import { testRunsApi, testCasesApi, attachmentsApi } from "../api";
import TestRunManager from "../components/TestRunManager";

const project = {
  id: 1, name: "P", description: "", jira_base_url: null, is_private: false,
  created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin",
};
const run = (id: number, name: string) => ({
  id, project_id: 1, name, version: "v1", environment: "dev",
  round: 1, status: "in_progress", sheet_names: null, created_by: 1, created_at: "2026-01-01",
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(testCasesApi.listSheets).mockResolvedValue([
    { id: 1, name: "기본", parent_id: null, sort_order: 0, is_folder: false, tc_count: 0, children: [] },
  ] as any);
  vi.mocked(attachmentsApi.listByRun).mockResolvedValue([] as any);
  vi.mocked(testRunsApi.list).mockResolvedValue([run(7, "회귀"), run(9, "핫픽스")] as any);
  vi.mocked(testRunsApi.getOne).mockImplementation(async (_p: number, id: number) => ({ ...run(id, "x"), results: [] }) as any);
});

describe("수행 바로 열기", () => {
  it("openRunId 의 수행을 열고 onRunOpened 를 부른다", async () => {
    const opened = vi.fn();
    render(<TestRunManager projectId={1} project={project as any} openRunId={9} onRunOpened={opened} />);
    await waitFor(() => expect(testRunsApi.getOne).toHaveBeenCalledWith(1, 9));
    expect(opened).toHaveBeenCalledTimes(1);
    expect(testRunsApi.getOne).not.toHaveBeenCalledWith(1, 7);
  });

  it("목록에 없는 수행이면 안내하고 파라미터를 지운다", async () => {
    const opened = vi.fn();
    render(<TestRunManager projectId={1} project={project as any} openRunId={404} onRunOpened={opened} />);
    await waitFor(() => expect(opened).toHaveBeenCalledTimes(1));
    expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("찾지 못했습니다"));
    expect(testRunsApi.getOne).not.toHaveBeenCalled();
  });

  it("수행 목록 조회가 실패하면 '없음' 으로 판정하지 않고 링크를 남긴다", async () => {
    vi.mocked(testRunsApi.list).mockRejectedValueOnce(new Error("network"));
    const opened = vi.fn();
    render(<TestRunManager projectId={1} project={project as any} openRunId={9} onRunOpened={opened} />);
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 100));
    expect(opened).not.toHaveBeenCalled();
    expect(toast.error).not.toHaveBeenCalledWith(expect.stringContaining("찾지 못했습니다"));
  });

  it("openRunId 가 없으면 아무 수행도 열지 않는다", async () => {
    const opened = vi.fn();
    render(<TestRunManager projectId={1} project={project as any} onRunOpened={opened} />);
    await waitFor(() => expect(testRunsApi.list).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 100));
    expect(testRunsApi.getOne).not.toHaveBeenCalled();
    expect(opened).not.toHaveBeenCalled();
  });
});
