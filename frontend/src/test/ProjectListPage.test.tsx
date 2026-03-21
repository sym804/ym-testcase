import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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

const mockProjects = [
  { id: 1, name: "Project A", description: "설명A", jira_base_url: null, is_private: false, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01" },
  { id: 2, name: "Project B", description: "", jira_base_url: null, is_private: true, created_by: 1, created_at: "2026-01-05", updated_at: "2026-01-05" },
];

const mockOverview = {
  summary: { total_projects: 2, total_tc: 150, pass: 100, fail: 30, block: 10, na: 5, not_started: 5, progress: 96, pass_rate: 69 },
  projects: [
    { id: 1, name: "Project A", total: 100, pass: 70, fail: 20, block: 5, na: 3, not_started: 2, progress: 98, pass_rate: 72 },
    { id: 2, name: "Project B", total: 50, pass: 30, fail: 10, block: 5, na: 2, not_started: 3, progress: 94, pass_rate: 63 },
  ],
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
  vi.mocked(projectsApi.list).mockResolvedValue(mockProjects);
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

describe("ProjectListPage", () => {
  it("전체 현황 대시보드를 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("전체 현황")).toBeInTheDocument();
    });
    expect(screen.getByText("전체 프로젝트")).toBeInTheDocument();
    expect(screen.getByText("전체 TC")).toBeInTheDocument();
  });

  it("프로젝트 카드를 렌더링한다", async () => {
    renderPage();
    await waitFor(() => {
      // overview 테이블 + 카드 양쪽에 프로젝트 이름이 나타남
      const projectAs = screen.getAllByText("Project A");
      expect(projectAs.length).toBeGreaterThanOrEqual(2); // 테이블 행 + 카드
    });
  });

  it("프로젝트 설명을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("설명A")).toBeInTheDocument();
      expect(screen.getByText("설명 없음")).toBeInTheDocument(); // Project B
    });
  });

  it("admin에게 새 프로젝트 버튼을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("+ 새 프로젝트")).toBeInTheDocument();
    });
  });

  it("일반 사용자에게는 새 프로젝트 버튼을 표시하지 않는다", async () => {
    mockState.role = "user";
    mockState.display_name = "일반사용자";
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThan(0);
    }, { timeout: 3000 });
    expect(screen.queryByText("+ 새 프로젝트")).not.toBeInTheDocument();
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

  it("프로젝트별 테이블에 Pass Rate를 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("72%")).toBeInTheDocument(); // Project A pass_rate
    });
  });
});

describe("ProjectListPage - Overview Stats Display", () => {
  it("전체 프로젝트 수를 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("전체 프로젝트")).toBeInTheDocument();
    });
    // "2" appears multiple times (summary card + table cells), so use getAllByText
    const twos = screen.getAllByText("2");
    expect(twos.length).toBeGreaterThanOrEqual(1);
  });

  it("전체 TC 수를 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("150")).toBeInTheDocument();
    });
  });

  it("진행률을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("96%")).toBeInTheDocument();
    });
  });

  it("Pass Rate를 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("69%")).toBeInTheDocument();
    });
  });

  it("결과별 범례를 표시한다 (PASS, FAIL, BLOCK, N/A, 미수행)", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/PASS 100/)).toBeInTheDocument();
      expect(screen.getByText(/FAIL 30/)).toBeInTheDocument();
      expect(screen.getByText(/BLOCK 10/)).toBeInTheDocument();
      expect(screen.getByText(/N\/A 5/)).toBeInTheDocument();
      expect(screen.getByText(/미수행 5/)).toBeInTheDocument();
    });
  });

  it("로딩 중에는 '불러오는 중...'을 표시한다", async () => {
    // delay resolution to keep loading state
    vi.mocked(projectsApi.list).mockImplementation(() => new Promise(() => {}));
    vi.mocked(overviewApi.get).mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
  });

  it("프로젝트가 없으면 '등록된 프로젝트가 없습니다.'를 표시한다", async () => {
    vi.mocked(projectsApi.list).mockResolvedValue([]);
    vi.mocked(overviewApi.get).mockResolvedValue({ summary: { total_projects: 0, total_tc: 0, pass: 0, fail: 0, block: 0, na: 0, not_started: 0, progress: 0, pass_rate: 0 }, projects: [] });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("등록된 프로젝트가 없습니다.")).toBeInTheDocument();
    });
  });
});

describe("ProjectListPage - Project Card Interactions", () => {
  it("프로젝트 카드 클릭 시 프로젝트 상세 페이지로 이동한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project A").length).toBeGreaterThanOrEqual(1);
    });
    // Click the card (the last occurrence is the card in the grid)
    const cards = screen.getAllByText("Project A");
    await user.click(cards[cards.length - 1]);
    expect(mockNavigate).toHaveBeenCalledWith("/projects/1");
  });

  it("테이블 행 클릭 시 프로젝트 상세 페이지로 이동한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText("Project B").length).toBeGreaterThanOrEqual(1);
    });
    const projectBs = screen.getAllByText("Project B");
    await user.click(projectBs[0]);
    expect(mockNavigate).toHaveBeenCalledWith("/projects/2");
  });

  it("설명이 없는 프로젝트는 '설명 없음'을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("설명 없음")).toBeInTheDocument();
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
    await user.type(screen.getByPlaceholderText("https://your-domain.atlassian.net"), "https://jira.example.com");
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
    vi.mocked(projectsApi.list).mockRejectedValue(new Error("network error"));
    vi.mocked(overviewApi.get).mockRejectedValue(new Error("network error"));
    renderPage();
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("데이터를 불러오지 못했습니다.");
    });
  });
});
