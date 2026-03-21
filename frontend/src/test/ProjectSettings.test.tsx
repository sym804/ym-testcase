import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import ProjectSettings from "../components/ProjectSettings";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  projectsApi: {
    update: vi.fn().mockResolvedValue({ id: 1, name: "TestProject", is_private: true }),
    delete: vi.fn().mockResolvedValue(undefined),
  },
  membersApi: { list: vi.fn().mockResolvedValue([]) },
  usersApi: { list: vi.fn().mockResolvedValue([]) },
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

import { projectsApi } from "../api";

const adminProject = {
  id: 1, name: "TestProject", description: "테스트", jira_base_url: null,
  is_private: false, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01", my_role: "admin",
};

const testerProject = { ...adminProject, my_role: "tester" };

beforeEach(() => {
  vi.clearAllMocks();
});

function renderSettings(project = adminProject) {
  return render(
    <MemoryRouter>
      <ProjectSettings project={project} onUpdate={vi.fn()} />
    </MemoryRouter>
  );
}

describe("ProjectSettings", () => {
  it("접근 설정 섹션을 표시한다", () => {
    renderSettings();
    expect(screen.getByText("접근 설정")).toBeInTheDocument();
    expect(screen.getByText("프로젝트 공개 범위")).toBeInTheDocument();
  });

  it("admin은 공개/비공개 토글 버튼을 볼 수 있다", () => {
    renderSettings();
    expect(screen.getByRole("button", { name: "공개" })).toBeInTheDocument();
  });

  it("tester는 상태 배지만 볼 수 있다 (토글 불가)", () => {
    renderSettings(testerProject);
    expect(screen.queryByRole("button", { name: "공개" })).not.toBeInTheDocument();
  });

  it("admin은 위험 영역(삭제)을 볼 수 있다", () => {
    renderSettings();
    expect(screen.getByText("위험 영역")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "프로젝트 삭제" })).toBeInTheDocument();
  });

  it("tester는 위험 영역을 볼 수 없다", () => {
    renderSettings(testerProject);
    expect(screen.queryByText("위험 영역")).not.toBeInTheDocument();
  });

  it("삭제 버튼 클릭 시 확인 입력란을 표시한다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    expect(screen.getByText(/삭제를 확인하려면/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("TestProject")).toBeInTheDocument();
  });

  it("프로젝트 이름 불일치 시 영구 삭제 버튼이 비활성화된다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    await user.type(screen.getByPlaceholderText("TestProject"), "WrongName");
    expect(screen.getByText("영구 삭제")).toBeDisabled();
  });

  it("프로젝트 이름 일치 시 삭제가 가능하다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    await user.type(screen.getByPlaceholderText("TestProject"), "TestProject");

    const deleteBtn = screen.getByText("영구 삭제");
    expect(deleteBtn).not.toBeDisabled();
    await user.click(deleteBtn);

    await waitFor(() => {
      expect(projectsApi.delete).toHaveBeenCalledWith(1);
    });
  });

  it("내 역할을 표시한다", () => {
    renderSettings();
    expect(screen.getByText("내 프로젝트 역할")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("취소 버튼으로 확인 입력란을 닫을 수 있다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    expect(screen.getByPlaceholderText("TestProject")).toBeInTheDocument();
    await user.click(screen.getByText("취소"));
    expect(screen.queryByPlaceholderText("TestProject")).not.toBeInTheDocument();
  });
});
