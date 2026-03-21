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
