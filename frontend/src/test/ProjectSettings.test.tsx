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
  customFieldsApi: {
    list: vi.fn().mockResolvedValue([]),
    create: vi.fn().mockResolvedValue({ id: 10, project_id: 1, field_name: "환경", field_type: "text", sort_order: 0, is_required: false, created_at: "2026-01-01" }),
    delete: vi.fn().mockResolvedValue(undefined),
  },
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

import { projectsApi, customFieldsApi } from "../api";
import toast from "react-hot-toast";

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

describe("ProjectSettings - Toggle Public/Private", () => {
  it("공개→비공개 토글 시 API를 호출하고 성공 메시지를 표시한다", async () => {
    const onUpdate = vi.fn();
    vi.mocked(projectsApi.update).mockResolvedValue({ ...adminProject, is_private: true });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ProjectSettings project={adminProject} onUpdate={onUpdate} />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: "공개" }));
    await waitFor(() => {
      expect(projectsApi.update).toHaveBeenCalledWith(1, { is_private: true });
    });
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("비공개 프로젝트로 변경되었습니다.");
    });
    expect(onUpdate).toHaveBeenCalledWith(expect.objectContaining({ is_private: true }));
  });

  it("비공개→공개 토글 시 API를 호출하고 성공 메시지를 표시한다", async () => {
    const privateProject = { ...adminProject, is_private: true };
    const onUpdate = vi.fn();
    vi.mocked(projectsApi.update).mockResolvedValue({ ...adminProject, is_private: false });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ProjectSettings project={privateProject} onUpdate={onUpdate} />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: "비공개" }));
    await waitFor(() => {
      expect(projectsApi.update).toHaveBeenCalledWith(1, { is_private: false });
    });
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("공개 프로젝트로 변경되었습니다.");
    });
  });

  it("토글 API 실패 시 에러 메시지를 표시한다", async () => {
    vi.mocked(projectsApi.update).mockRejectedValue(new Error("fail"));
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "공개" }));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("설정 변경에 실패했습니다.");
    });
  });
});

describe("ProjectSettings - Member Role Display", () => {
  it("admin 역할을 표시한다", () => {
    renderSettings();
    expect(screen.getByText("내 프로젝트 역할")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("tester 역할을 표시한다", () => {
    renderSettings(testerProject);
    expect(screen.getByText("tester")).toBeInTheDocument();
  });

  it("역할이 없으면 '없음'을 표시한다", () => {
    const noRoleProject = { ...adminProject, my_role: "" };
    renderSettings(noRoleProject);
    expect(screen.getByText("없음")).toBeInTheDocument();
  });

  it("비공개 프로젝트에 대한 설명 텍스트를 표시한다", () => {
    const privateProject = { ...adminProject, is_private: true };
    render(
      <MemoryRouter>
        <ProjectSettings project={privateProject} onUpdate={vi.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByText(/멤버로 등록된 사용자만 접근/)).toBeInTheDocument();
  });

  it("공개 프로젝트에 대한 설명 텍스트를 표시한다", () => {
    renderSettings();
    expect(screen.getByText(/모든 인증된 사용자가 조회/)).toBeInTheDocument();
  });
});

describe("ProjectSettings - Danger Zone (Delete Flow)", () => {
  it("삭제 성공 후 /projects로 이동한다", async () => {
    vi.mocked(projectsApi.delete).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    await user.type(screen.getByPlaceholderText("TestProject"), "TestProject");
    await user.click(screen.getByText("영구 삭제"));
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/projects");
    });
    expect(toast.success).toHaveBeenCalledWith("프로젝트가 삭제되었습니다.");
  });

  it("삭제 API 실패 시 에러 메시지를 표시한다", async () => {
    vi.mocked(projectsApi.delete).mockRejectedValue(new Error("fail"));
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    await user.type(screen.getByPlaceholderText("TestProject"), "TestProject");
    await user.click(screen.getByText("영구 삭제"));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("프로젝트 삭제에 실패했습니다.");
    });
  });

  it("삭제 중 버튼 텍스트가 '삭제 중...'으로 바뀐다", async () => {
    let resolveDelete: () => void;
    vi.mocked(projectsApi.delete).mockImplementation(
      () => new Promise<void>((resolve) => { resolveDelete = resolve; })
    );
    const user = userEvent.setup();
    renderSettings();
    await user.click(screen.getByRole("button", { name: "프로젝트 삭제" }));
    await user.type(screen.getByPlaceholderText("TestProject"), "TestProject");
    await user.click(screen.getByText("영구 삭제"));
    expect(screen.getByText("삭제 중...")).toBeInTheDocument();
    resolveDelete!();
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/projects");
    });
  });
});

describe("ProjectSettings - Custom Fields CRUD", () => {
  it("커스텀 필드 섹션이 admin에게만 표시된다", async () => {
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("커스텀 필드")).toBeInTheDocument();
    });
  });

  it("tester에게는 커스텀 필드 섹션이 표시되지 않는다", () => {
    renderSettings(testerProject);
    expect(screen.queryByText("커스텀 필드")).not.toBeInTheDocument();
  });

  it("필드가 없을 때 빈 메시지를 표시한다", async () => {
    vi.mocked(customFieldsApi.list).mockResolvedValue([]);
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("등록된 커스텀 필드가 없습니다.")).toBeInTheDocument();
    });
  });

  it("기존 필드 목록을 표시한다", async () => {
    vi.mocked(customFieldsApi.list).mockResolvedValue([
      { id: 1, project_id: 1, field_name: "환경", field_type: "text", sort_order: 0, is_required: false, created_at: "2026-01-01" },
      { id: 2, project_id: 1, field_name: "브라우저", field_type: "select", options: ["Chrome", "Firefox"], sort_order: 1, is_required: false, created_at: "2026-01-01" },
    ]);
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("환경")).toBeInTheDocument();
      expect(screen.getByText("브라우저")).toBeInTheDocument();
    });
    expect(screen.getByText("텍스트")).toBeInTheDocument();
    expect(screen.getByText("단일 선택")).toBeInTheDocument();
    expect(screen.getByText("Chrome, Firefox")).toBeInTheDocument();
  });

  it("+ 필드 추가 버튼으로 추가 폼을 열고 닫을 수 있다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("+ 필드 추가")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 필드 추가"));
    expect(screen.getByPlaceholderText("예: 환경")).toBeInTheDocument();
    await user.click(screen.getByText("취소"));
    expect(screen.queryByPlaceholderText("예: 환경")).not.toBeInTheDocument();
  });

  it("새 필드를 추가할 수 있다", async () => {
    vi.mocked(customFieldsApi.list).mockResolvedValue([]);
    vi.mocked(customFieldsApi.create).mockResolvedValue({
      id: 10, project_id: 1, field_name: "환경", field_type: "text", sort_order: 0, is_required: false, created_at: "2026-01-01",
    });
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("+ 필드 추가")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 필드 추가"));
    await user.type(screen.getByPlaceholderText("예: 환경"), "환경");
    await user.click(screen.getByText("추가"));
    await waitFor(() => {
      expect(customFieldsApi.create).toHaveBeenCalledWith(1, {
        field_name: "환경",
        field_type: "text",
        options: undefined,
      });
    });
    expect(toast.success).toHaveBeenCalledWith('"환경" 필드가 추가되었습니다.');
  });

  it("필드 이름이 비어있으면 에러를 표시한다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("+ 필드 추가")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 필드 추가"));
    await user.click(screen.getByText("추가"));
    expect(toast.error).toHaveBeenCalledWith("필드 이름을 입력해 주세요.");
  });

  it("select 타입 선택 시 옵션 입력란이 나타난다", async () => {
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("+ 필드 추가")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 필드 추가"));
    expect(screen.queryByPlaceholderText("예: Dev, QA, Prod")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByDisplayValue("텍스트"), "select");
    expect(screen.getByPlaceholderText("예: Dev, QA, Prod")).toBeInTheDocument();
  });

  it("필드를 삭제할 수 있다", async () => {
    vi.mocked(customFieldsApi.list).mockResolvedValue([
      { id: 5, project_id: 1, field_name: "환경", field_type: "text", sort_order: 0, is_required: false, created_at: "2026-01-01" },
    ]);
    vi.mocked(customFieldsApi.delete).mockResolvedValue({ deleted: "환경" });
    window.confirm = vi.fn().mockReturnValue(true);
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("환경")).toBeInTheDocument();
    });
    await user.click(screen.getByText("×"));
    await waitFor(() => {
      expect(customFieldsApi.delete).toHaveBeenCalledWith(1, 5);
    });
    expect(toast.success).toHaveBeenCalledWith('"환경" 필드가 삭제되었습니다.');
  });

  it("필드 삭제 확인 취소 시 삭제하지 않는다", async () => {
    vi.mocked(customFieldsApi.list).mockResolvedValue([
      { id: 5, project_id: 1, field_name: "환경", field_type: "text", sort_order: 0, is_required: false, created_at: "2026-01-01" },
    ]);
    window.confirm = vi.fn().mockReturnValue(false);
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("환경")).toBeInTheDocument();
    });
    await user.click(screen.getByText("×"));
    expect(customFieldsApi.delete).not.toHaveBeenCalled();
  });

  it("필드 추가 API 실패 시 에러 메시지를 표시한다", async () => {
    vi.mocked(customFieldsApi.create).mockRejectedValue({ response: { data: { detail: "중복된 필드명" } } });
    const user = userEvent.setup();
    renderSettings();
    await waitFor(() => {
      expect(screen.getByText("+ 필드 추가")).toBeInTheDocument();
    });
    await user.click(screen.getByText("+ 필드 추가"));
    await user.type(screen.getByPlaceholderText("예: 환경"), "환경");
    await user.click(screen.getByText("추가"));
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("중복된 필드명");
    });
  });
});
