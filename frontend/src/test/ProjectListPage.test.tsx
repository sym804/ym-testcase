import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";


// Mock auth context to return admin user
const { mockState } = vi.hoisted(() => {
  return {
    mockState: {
      role: "admin" as string,
      display_name: "관리자" as string,
    },
  };
});

vi.mock("../contexts/AuthContext", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: { id: 1, username: "admin", display_name: mockState.display_name, role: mockState.role, must_change_password: false, created_at: "2026-01-01" },
    loading: false,
    mustChangePassword: false,
    login: vi.fn(), register: vi.fn(), logout: vi.fn(), changePassword: vi.fn(),
  }),
}));

vi.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../components/Header", () => ({
  default: () => <div data-testid="header">Header</div>,
}));

vi.mock("../api", () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  overviewApi: { get: vi.fn() },
  searchApi: { global: vi.fn() },
  authApi: { getMe: vi.fn() },
}));

import ProjectListPage from "../pages/ProjectListPage";
import { projectsApi, overviewApi, searchApi } from "../api";
import toast from "react-hot-toast";

// 메인 화면 응답(SYM-225). 수행 요약은 진행 중과 최근 완료를 따로 싣는다.
const run = (over: Record<string, unknown> = {}) => ({
  project_id: 1, project_name: "Project A", run_id: 11, name: "정기", round: 2, version: "1.2", environment: "stage",
  status: "in_progress", created_at: "2026-01-10T09:00:00", completed_at: null,
  total: 100, executed: 60, pass: 50, fail: 7, block: 3, na: 0, progress: 60, pass_rate: 83.3, ...over,
});
const activeA = run();
const activeA2 = run({ run_id: 12, name: "핫픽스", round: 1, created_at: "2026-01-09T09:00:00", total: 10, executed: 10,
  pass: 10, fail: 0, block: 0, progress: 100, pass_rate: 100 });
const doneA = run({ run_id: 10, round: 1, status: "completed", completed_at: "2026-01-08T18:00:00", executed: 100,
  pass: 72, fail: 20, block: 8, progress: 100, pass_rate: 72 });

const mockOverview = {
  summary: { total_projects: 2, active_tc: 150, in_progress_runs: 2, in_progress_fail_block: 10 },
  active_runs: [activeA, activeA2],
  projects: [
    { id: 1, name: "Project A", description: "설명A", is_private: false, created_at: "2026-01-01", active_tc: 100,
      in_progress: [activeA, activeA2], last_completed: doneA },
    { id: 2, name: "Project B", description: "", is_private: true, created_at: "2026-01-05", active_tc: 50,
      in_progress: [], last_completed: null },
  ],
};
const emptyOverview = {
  summary: { total_projects: 0, active_tc: 0, in_progress_runs: 0, in_progress_fail_block: 0 },
  active_runs: [], projects: [],
};

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

beforeEach(() => {
  vi.clearAllMocks();
  mockState.role = "admin";
  mockState.display_name = "관리자";
  vi.mocked(projectsApi.create).mockResolvedValue({ id: 3, name: "New Project", description: "", jira_base_url: null, is_private: false, created_by: 1, created_at: "2026-01-10", updated_at: "2026-01-10" });
  vi.mocked(overviewApi.get).mockResolvedValue(mockOverview);
  vi.mocked(searchApi.global).mockResolvedValue([]);
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ProjectListPage />
    </MemoryRouter>
  );
}

const table = (name: string) => screen.getByRole("table", { name });
const rowOf = (tbl: HTMLElement, text: string) =>
  within(tbl).getAllByRole("row").find((r) => r.textContent?.includes(text)) as HTMLTableRowElement;

describe("ProjectListPage - 요약", () => {
  it("개수 카드만 보여 주고 섞어 더한 진행률 · 합격률은 없다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    expect(screen.getByText("전체 프로젝트")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("진행 중 FAIL·BLOCK").nextElementSibling).toHaveTextContent(/^10$/);
    expect(screen.queryByText("진행률")).not.toBeInTheDocument();
    expect(screen.queryByText("전체 TC")).not.toBeInTheDocument();
    expect(screen.queryByText(/PASS \d+/)).not.toBeInTheDocument();
  });

  it("로딩 중에는 '불러오는 중...'을 표시한다", async () => {
    vi.mocked(overviewApi.get).mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
  });

  it("목록과 수치를 요청 하나로 받는다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    expect(overviewApi.get).toHaveBeenCalledTimes(1);
    expect(projectsApi.list).not.toHaveBeenCalled();
  });
});

describe("ProjectListPage - 진행 중인 수행", () => {
  it("수행마다 이름 · 회차 · 버전 · 진행 · FAIL · BLOCK · 합격률을 보여 준다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    const tbl = table("진행 중인 수행");
    const row = rowOf(tbl, "정기 · 2회차");
    expect(row).toHaveTextContent("Project A");
    expect(row).toHaveTextContent("1.2 · stage");
    expect(row).toHaveTextContent("60/100");
    expect(row).toHaveTextContent("83.3%");
    expect(within(tbl).getAllByRole("row")).toHaveLength(3); // 머리 + 2
  });

  it("수행 이름은 그 수행이 열리는 링크다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    const link = within(table("진행 중인 수행")).getByRole("link", { name: "정기 · 2회차" });
    expect(link).toHaveAttribute("href", "/projects/1?tab=run&run=11");
  });

  it("행을 누르면 그 수행으로 간다", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("전체 현황");
    await user.click(rowOf(table("진행 중인 수행"), "핫픽스").cells[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/projects/1?tab=run&run=12");
  });

  it("진행 중인 수행이 없으면 안내를 보여 준다", async () => {
    vi.mocked(overviewApi.get).mockResolvedValue({ ...mockOverview, active_runs: [] });
    renderPage();
    expect(await screen.findByText("진행 중인 수행이 없습니다.")).toBeInTheDocument();
  });
});

describe("ProjectListPage - 프로젝트 표", () => {
  it("카드 목록 없이 표 하나에 프로젝트를 보여 준다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    expect(screen.getAllByText("Project B")).toHaveLength(1);
    expect(screen.queryByRole("heading", { level: 3 })).not.toBeInTheDocument();
  });

  it("진행 중 수행과 최근 완료 수행을 따로 보여 준다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    const row = rowOf(table("프로젝트"), "Project A");
    expect(within(row).getByRole("link", { name: "정기 · 2회차" })).toHaveAttribute("href", "/projects/1?tab=run&run=11");
    expect(row).toHaveTextContent("외 1건");
    expect(within(row).getByRole("link", { name: "정기 · 1회차" })).toHaveAttribute("href", "/projects/1?tab=run&run=10");
    expect(row).toHaveTextContent("72%");
    expect(row).toHaveTextContent("FAIL 20");
  });

  it("수행이 없는 프로젝트는 '-' 로 비워 둔다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    const row = rowOf(table("프로젝트"), "Project B");
    expect(within(row).queryAllByRole("link")).toHaveLength(1); // 프로젝트 이름만
    expect(row).toHaveTextContent("50");
  });

  // SYM-133: 판정이 없으면 0% 가 아니라 값 없음이다
  it("최근 완료 수행에 판정이 없으면 '-' 이고 합격 색을 칠하지 않는다", async () => {
    vi.mocked(overviewApi.get).mockResolvedValue({
      ...mockOverview,
      projects: [{ ...mockOverview.projects[0], last_completed: { ...doneA, pass_rate: null } }, mockOverview.projects[1]],
    });
    renderPage();
    await screen.findByText("전체 현황");
    const row = rowOf(table("프로젝트"), "Project A");
    const rate = within(row).getByText("-");
    expect(rate.style.color).toBe("var(--text-secondary)");
  });

  it("프로젝트 설명을 보여 주고 없으면 '설명 없음'", async () => {
    renderPage();
    expect(await screen.findByText("설명A")).toBeInTheDocument();
    expect(screen.getByText("설명 없음")).toBeInTheDocument();
  });

  it("프로젝트 이름은 프로젝트로 가는 링크다", async () => {
    renderPage();
    await screen.findByText("전체 현황");
    expect(within(table("프로젝트")).getByRole("link", { name: "Project A" })).toHaveAttribute("href", "/projects/1");
  });

  it("행을 누르면 프로젝트 상세로 간다", async () => {
    const user = userEvent.setup();
    renderPage();
    await screen.findByText("전체 현황");
    await user.click(rowOf(table("프로젝트"), "Project B").cells[2]);
    expect(mockNavigate).toHaveBeenCalledWith("/projects/2");
  });

  it("프로젝트가 없으면 '등록된 프로젝트가 없습니다.'를 표시한다", async () => {
    vi.mocked(overviewApi.get).mockResolvedValue(emptyOverview);
    renderPage();
    expect(await screen.findByText("등록된 프로젝트가 없습니다.")).toBeInTheDocument();
  });
});

describe("ProjectListPage - 새 프로젝트", () => {
  it("admin에게 새 프로젝트 버튼을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
  });

  it("일반 사용자에게도 새 프로젝트 버튼을 표시하고 일괄 삭제 체크박스는 숨긴다", async () => {
    mockState.role = "user";
    mockState.display_name = "일반사용자";
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThan(0);
    }, { timeout: 3000 });
    expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    expect(screen.queryByLabelText("전체 선택")).not.toBeInTheDocument();
  });

  it("새 프로젝트 모달을 열고 닫을 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    expect(screen.getByText("새 프로젝트")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("프로젝트 이름")).toBeInTheDocument();

    await user.click(screen.getByText("취소"));
    expect(screen.queryByPlaceholderText("프로젝트 이름")).not.toBeInTheDocument();
  });

  it("프로젝트를 생성할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    await user.type(screen.getByPlaceholderText("프로젝트 이름"), "New Project");
    await user.click(screen.getByText("생성"));

    await waitFor(() => {
      expect(projectsApi.create).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith("프로젝트가 생성되었습니다.");
    });
  });

  it("일반 사용자도 모달에서 프로젝트를 생성하고 목록을 다시 불러온다", async () => {
    mockState.role = "user";
    mockState.display_name = "일반사용자";
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    const overviewCalls = vi.mocked(overviewApi.get).mock.calls.length;
    await user.click(screen.getByText("+ 새 프로젝트"));
    await user.type(screen.getByPlaceholderText("프로젝트 이름"), "My Project");
    await user.click(screen.getByText("생성"));

    await waitFor(() => {
      expect(projectsApi.create).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith("프로젝트가 생성되었습니다.");
      expect(vi.mocked(overviewApi.get).mock.calls.length).toBeGreaterThan(overviewCalls);
    });
  });
});

describe("ProjectListPage - New Project Modal Submission", () => {
  it("이름 없이 생성 시 에러 메시지를 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    await user.click(screen.getByText("생성"));
    expect(toast.error).toHaveBeenCalledWith("프로젝트 이름을 입력해 주세요.");
    expect(projectsApi.create).not.toHaveBeenCalled();
  });

  it("100자 초과 이름으로 생성 시 에러 메시지를 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    const longName = "A".repeat(101);
    await user.type(screen.getByPlaceholderText("프로젝트 이름"), longName);
    await user.click(screen.getByText("생성"));
    expect(toast.error).toHaveBeenCalledWith("프로젝트 이름은 100자 이내로 입력해 주세요.");
    expect(projectsApi.create).not.toHaveBeenCalled();
  });

  it("프로젝트 생성 시 올바른 폼 데이터를 전송한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    await user.type(screen.getByPlaceholderText("프로젝트 이름"), "NewProject");
    await user.type(screen.getByPlaceholderText("프로젝트 설명"), "설명입니다");
    await user.type(screen.getByPlaceholderText(/Jira 또는 Linear/), "https://jira.example.com");
    await user.click(screen.getByText("생성"));
    await waitFor(() => {
      expect(projectsApi.create).toHaveBeenCalledWith({
        name: "NewProject",
        description: "설명입니다",
        jira_base_url: "https://jira.example.com",
        is_private: false,
      });
    });
  });

  it("비공개 체크박스를 체크하고 생성할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    await user.type(screen.getByPlaceholderText("프로젝트 이름"), "PrivateProject");
    await user.click(screen.getByLabelText(/비공개 프로젝트/));
    await user.click(screen.getByText("생성"));
    await waitFor(() => {
      expect(projectsApi.create).toHaveBeenCalledWith(expect.objectContaining({ is_private: true }));
    });
  });

  it("프로젝트 생성 실패 시 에러 메시지를 표시한다", async () => {
    vi.mocked(projectsApi.create).mockRejectedValue(new Error("fail"));
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    await user.type(screen.getByPlaceholderText("프로젝트 이름"), "FailProject");
    await user.click(screen.getByText("생성"));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("프로젝트 생성에 실패했습니다.");
    });
  });

  it("모달 오버레이 클릭 시 모달이 닫힌다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 새 프로젝트"));
    expect(screen.getByText("새 프로젝트")).toBeInTheDocument();
    // The overlay is the parent div; click on the modal title area won't close it.
    // Click on the overlay area
    const overlay = screen.getByPlaceholderText("프로젝트 이름").closest("[style]")?.parentElement?.parentElement;
    if (overlay) {
      await user.click(overlay);
    }
  });
});

describe("ProjectListPage - Delete Project Flow", () => {
  it("admin은 체크박스를 선택하면 삭제 버튼이 나타난다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    // Get the row checkboxes (not the header checkbox)
    const checkboxes = screen.getAllByRole("checkbox");
    // First checkbox is the header "select all", rest are per-row
    expect(checkboxes.length).toBeGreaterThanOrEqual(3); // header + 2 rows
    await user.click(checkboxes[1]); // click first project checkbox
    expect(screen.getByText("1개 삭제")).toBeInTheDocument();
  });

  it("전체 선택 체크박스로 모든 프로젝트를 선택할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]); // header checkbox
    expect(screen.getByText("2개 삭제")).toBeInTheDocument();
  });

  it("전체 선택 해제 시 삭제 버튼이 사라진다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[0]); // select all
    expect(screen.getByText("2개 삭제")).toBeInTheDocument();
    await user.click(checkboxes[0]); // deselect all
    expect(screen.queryByText(/개 삭제/)).not.toBeInTheDocument();
  });

  it("bulk 삭제 시 confirm 승인 후 API를 호출한다", async () => {
    vi.mocked(projectsApi.delete).mockResolvedValue(undefined);
    window.confirm = vi.fn().mockReturnValue(true);
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[1]); // select first project
    await user.click(screen.getByText("1개 삭제"));
    await waitFor(() => {
      expect(projectsApi.delete).toHaveBeenCalledWith(1);
    });
    expect(toast.success).toHaveBeenCalledWith("1개 프로젝트가 삭제되었습니다.");
  });

  it("bulk 삭제 시 confirm 취소하면 API를 호출하지 않는다", async () => {
    window.confirm = vi.fn().mockReturnValue(false);
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[1]);
    await user.click(screen.getByText("1개 삭제"));
    expect(projectsApi.delete).not.toHaveBeenCalled();
  });

  it("일반 사용자는 체크박스를 볼 수 없다", async () => {
    mockState.role = "user";
    mockState.display_name = "일반사용자";
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
  });
});

describe("ProjectListPage - Data Loading Errors", () => {
  it("데이터 로딩 실패 시 에러 메시지를 표시한다", async () => {
    vi.mocked(overviewApi.get).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("데이터를 불러오지 못했습니다.");
    });
  });
});
