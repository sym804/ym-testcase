import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import ProjectPage from "../pages/ProjectPage";
import { UserRole } from "../types";

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 1, username: "admin", display_name: "관리자", role: UserRole.ADMIN, must_change_password: false, created_at: "2026-01-01" },
    logout: vi.fn(),
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
    getOne: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  searchApi: { global: vi.fn() },
  authApi: { getMe: vi.fn() },
  testCasesApi: { list: vi.fn() },
  testRunsApi: { list: vi.fn() },
  dashboardApi: {
    summary: vi.fn(),
    priority: vi.fn(),
    category: vi.fn(),
    rounds: vi.fn(),
    heatmap: vi.fn(),
  },
  reportsApi: { getData: vi.fn() },
  membersApi: { list: vi.fn() },
  usersApi: { list: vi.fn() },
}));

import { projectsApi, searchApi, testCasesApi, testRunsApi, dashboardApi, reportsApi, membersApi, usersApi } from "../api";

const mockProject = {
  id: 1, name: "TestProject", description: "설명", jira_base_url: null,
  is_private: false, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin",
};

// Mock heavy components
// 마운트될 때마다 번호를 새로 받는다. 프로젝트를 바꿨는데 같은 번호면 시트 선택 같은 내부 상태가 남는다.
const gridMounts = vi.hoisted(() => ({ n: 0 }));
vi.mock("../components/TestCaseGrid", async () => {
  const { useState } = await import("react");
  function MockGrid({ projectId }: { projectId: number }) {
    const [inst] = useState(() => ++gridMounts.n);
    return <div data-testid="tc-grid" data-inst={inst} data-project={projectId}>TestCaseGrid</div>;
  }
  return { default: MockGrid };
});
vi.mock("../components/TestRunManager", () => ({
  default: () => <div data-testid="run-manager">TestRunManager</div>,
}));

vi.mock("react-chartjs-2", () => ({
  Doughnut: () => <div>Doughnut</div>,
  Bar: () => <div>Bar</div>,
  Line: () => <div>Line</div>,
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(projectsApi.list).mockResolvedValue([mockProject]);
  vi.mocked(projectsApi.getOne).mockResolvedValue(mockProject);
  vi.mocked(searchApi.global).mockResolvedValue([]);
  vi.mocked(testCasesApi.list).mockResolvedValue([]);
  vi.mocked(testRunsApi.list).mockResolvedValue([]);
  vi.mocked(dashboardApi.summary).mockResolvedValue({ total: 0, pass: 0, fail: 0, block: 0, na: 0, not_started: 0, pass_rate: 0, fail_rate: 0, block_rate: 0, na_rate: 0, not_started_rate: 0 });
  vi.mocked(dashboardApi.priority).mockResolvedValue([]);
  vi.mocked(dashboardApi.category).mockResolvedValue([]);
  vi.mocked(dashboardApi.rounds).mockResolvedValue([]);
  vi.mocked(dashboardApi.heatmap).mockResolvedValue([]);
  vi.mocked(reportsApi.getData).mockResolvedValue(null as any);
  vi.mocked(membersApi.list).mockResolvedValue([]);
  vi.mocked(usersApi.list).mockResolvedValue([]);
});

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/projects/1"]}>
      <Routes>
        <Route path="/projects/:id" element={<ProjectPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ProjectPage", () => {
  it("프로젝트 이름을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TestProject")).toBeInTheDocument();
    });
  });

  it("프로젝트 설명을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("설명")).toBeInTheDocument();
    });
  });

  it("6개 탭 버튼을 렌더링한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TC 관리")).toBeInTheDocument();
    });
    expect(screen.getByText("테스트 수행")).toBeInTheDocument();
    expect(screen.getByText("비교")).toBeInTheDocument();
    expect(screen.getByText("대시보드")).toBeInTheDocument();
    expect(screen.getByText("리포트")).toBeInTheDocument();
    expect(screen.getByText("설정")).toBeInTheDocument();
  });

  it("기본 탭은 TC 관리이다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("tc-grid")).toBeInTheDocument();
    });
  });

  it("탭 전환이 작동한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TestProject")).toBeInTheDocument();
    });

    await user.click(screen.getByText("테스트 수행"));
    await waitFor(() => {
      expect(screen.getByTestId("run-manager")).toBeInTheDocument();
    });
  });

  it("설정 탭에서 접근 설정을 표시한다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TestProject")).toBeInTheDocument();
    });

    await user.click(screen.getByText("설정"));
    await waitFor(() => {
      expect(screen.getByText("접근 설정")).toBeInTheDocument();
    });
  });

  it("로딩 중 메시지를 표시한다", () => {
    vi.mocked(projectsApi.getOne).mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
  });

  it("프로젝트를 찾을 수 없으면 안내 메시지를 표시한다", async () => {
    vi.mocked(projectsApi.getOne).mockRejectedValue(new Error("Not found"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("프로젝트를 찾을 수 없습니다.")).toBeInTheDocument();
    });
  });

  it("프로젝트 설명이 없으면 description 영역을 표시하지 않는다", async () => {
    const projectNoDesc = { ...mockProject, description: "" };
    vi.mocked(projectsApi.getOne).mockResolvedValue(projectNoDesc);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("TestProject")).toBeInTheDocument();
    });
    // description이 빈 문자열이므로 "설명" 텍스트가 없어야 함
    expect(screen.queryByText("설명")).not.toBeInTheDocument();
  });
});

describe("ProjectPage 프로젝트 전환", () => {
  function GoTo2() {
    const nav = useNavigate();
    return <button onClick={() => nav("/projects/2")}>go2</button>;
  }

  function renderSwitchable() {
    return render(
      <MemoryRouter initialEntries={["/projects/1"]}>
        <GoTo2 />
        <Routes>
          <Route path="/projects/:id" element={<ProjectPage />} />
        </Routes>
      </MemoryRouter>
    );
  }

  it("다른 프로젝트로 가면 TC 그리드를 새로 띄워 이전 프로젝트의 시트 선택이 남지 않는다", async () => {
    const second = { ...mockProject, id: 2, name: "SecondProject" };
    vi.mocked(projectsApi.getOne).mockImplementation(async (id: number) => (id === 2 ? second : mockProject) as any);
    renderSwitchable();
    const first = await screen.findByTestId("tc-grid");
    const firstInst = first.getAttribute("data-inst");

    await userEvent.click(screen.getByText("go2"));

    await waitFor(() => expect(screen.getByText("SecondProject")).toBeInTheDocument());
    const grid = screen.getByTestId("tc-grid");
    expect(grid.getAttribute("data-project")).toBe("2");
    expect(grid.getAttribute("data-inst")).not.toBe(firstInst);
  });

  it("새 프로젝트를 못 불러오면 이전 프로젝트 이름 아래 새 데이터를 보이지 않는다", async () => {
    vi.mocked(projectsApi.getOne).mockImplementation(async (id: number) => {
      if (id === 2) throw new Error("500");
      return mockProject as any;
    });
    renderSwitchable();
    await screen.findByText("TestProject");

    await userEvent.click(screen.getByText("go2"));

    await waitFor(() => expect(screen.queryByText("TestProject")).not.toBeInTheDocument());
    expect(screen.queryByTestId("tc-grid")).not.toBeInTheDocument();
  });
});
