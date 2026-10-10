import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AdminPage from "../pages/AdminPage";
import { UserRole } from "../types";

let mockRole: UserRole = UserRole.ADMIN;

// ★실제 AuthContext 처럼 같은 사용자 객체를 돌려준다. 렌더마다 새 객체를 주면 [currentUser] 에 걸린
//   effect 가 매번 목록을 다시 불러와, 목록 갱신을 빠뜨린 결함(초기화 뒤 등)이 테스트에서 가려진다.
const mockAuthUsers = new Map<string, object>();
const mockLogout = vi.fn();
vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => {
    if (!mockAuthUsers.has(mockRole)) {
      mockAuthUsers.set(mockRole, { id: 1, username: "admin", display_name: "관리자", role: mockRole,
        must_change_password: false, created_at: "2026-01-01" });
    }
    return { user: mockAuthUsers.get(mockRole), logout: mockLogout };
  },
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
  usersApi: {
    list: vi.fn(),
    updateRole: vi.fn(),
    resetPassword: vi.fn(),
    getAllAssignments: vi.fn(),
    assignToAllProjects: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    disable: vi.fn(),
    enable: vi.fn(),
    releaseEmail: vi.fn(),
    remove: vi.fn(),
  },
  projectsApi: { list: vi.fn() },
  membersApi: {
    list: vi.fn(),
    add: vi.fn(),
    updateRole: vi.fn(),
    remove: vi.fn(),
  },
  searchApi: { global: vi.fn() },
  authApi: { getMe: vi.fn() },
  // AdminPage 는 AccountRequestSection 을 조건 없이 렌더한다. 이 키가 없으면
  // 섹션 로더가 TypeError 를 내고 컴포넌트가 그것을 오류 상태로 삼켜서,
  // 테스트는 통과하지만 섹션은 한 줄도 검증되지 않는다.
  accountRequestsApi: {
    submit: vi.fn(),
    list: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    resetWithCode: vi.fn(),
  },
}));

import { usersApi, projectsApi, membersApi, searchApi, accountRequestsApi } from "../api";
import toast from "react-hot-toast";

const mockUsers = [
  { id: 1, username: "admin", display_name: "관리자", role: UserRole.ADMIN, must_change_password: false, created_at: "2026-01-01T00:00:00" },
  { id: 2, username: "tester1", display_name: "테스터1", role: UserRole.USER, must_change_password: false, created_at: "2026-01-02T00:00:00" },
];

const mockProjects = [
  { id: 1, name: "프로젝트A", description: "", jira_base_url: null, is_private: false, created_by: 1, created_at: "2026-01-01", updated_at: "2026-01-01" },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockRole = UserRole.ADMIN;
  vi.mocked(usersApi.list).mockResolvedValue(mockUsers);
  vi.mocked(usersApi.updateRole).mockResolvedValue({} as any);
  vi.mocked(usersApi.resetPassword).mockResolvedValue({ temp_password: "TempPass123!" });
  vi.mocked(usersApi.getAllAssignments).mockResolvedValue({});
  vi.mocked(usersApi.assignToAllProjects).mockResolvedValue({ assigned: 1, total_projects: 1 });
  vi.mocked(projectsApi.list).mockResolvedValue(mockProjects);
  vi.mocked(membersApi.list).mockResolvedValue([]);
  vi.mocked(membersApi.add).mockResolvedValue({} as any);
  vi.mocked(membersApi.updateRole).mockResolvedValue({} as any);
  vi.mocked(membersApi.remove).mockResolvedValue(undefined);
  vi.mocked(searchApi.global).mockResolvedValue([]);
  vi.mocked(accountRequestsApi.list).mockResolvedValue([]);
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminPage />
    </MemoryRouter>
  );
}

describe("AdminPage", () => {
  it("관리자가 아니면 권한 필요 메시지를 표시한다", async () => {
    mockRole = UserRole.USER;
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("관리자 권한이 필요합니다.")).toBeInTheDocument();
    });
  });

  it("사용자 관리 제목을 표시한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("사용자 관리")).toBeInTheDocument();
    });
  });

  it("사용자 목록을 테이블로 렌더링한다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("tester1")).toBeInTheDocument();
      expect(screen.getByText("테스터1")).toBeInTheDocument();
    });
  });

  it("역할 변경 셀렉터가 있다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("tester1")).toBeInTheDocument();
    });
    // 자기 자신 외의 사용자에 대해 역할 셀렉터가 활성화됨
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBeGreaterThan(0);
  });

  it("비밀번호 초기화 버튼이 있다", async () => {
    renderPage();
    await waitFor(() => {
      // admin 본인 외 사용자에 대해서만 초기화 버튼 있음
      expect(screen.getByText("초기화")).toBeInTheDocument();
    });
  });

  it("비밀번호 초기화 시 임시 비밀번호 모달을 표시한다", async () => {
    const user = userEvent.setup();
    // confirm을 자동 true로
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("초기화")).toBeInTheDocument();
    });

    await user.click(screen.getByText("초기화"));

    await waitFor(() => {
      expect(screen.getByText("비밀번호 초기화 완료")).toBeInTheDocument();
      expect(screen.getByText("TempPass123!")).toBeInTheDocument();
    });
  });

  it("아이디에 든 HTML 을 태그로 해석하지 않는다", async () => {
    // ★i18n 설정이 escapeValue:false 라, 사용자명을 dangerouslySetInnerHTML 에
    //   끼워 넣으면 저장형 XSS 가 된다. 아이디는 가입자가 정하고 백엔드에
    //   문자 제한이 없다. 관리자가 그 계정 비밀번호를 초기화하는 순간 관리자
    //   브라우저에서 실행된다.
    const evil = '<img src=x onerror="window.__xss=1">';
    vi.mocked(usersApi.list).mockResolvedValue([
      mockUsers[0],
      { ...mockUsers[1], username: evil },
    ]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    const { container } = renderPage();
    await waitFor(() => {
      expect(screen.getByText("초기화")).toBeInTheDocument();
    });
    await user.click(screen.getByText("초기화"));

    await waitFor(() => {
      expect(screen.getByText("비밀번호 초기화 완료")).toBeInTheDocument();
    });

    expect(container.querySelector("img"), "아이디가 HTML 로 해석됐다").toBeNull();
    // 값 자체는 글자로 보여야 한다.
    expect(container.textContent).toContain("onerror");
  });

  it("역할을 변경할 수 있다", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("tester1")).toBeInTheDocument();
    });

    // disabled가 아닌 셀렉터를 찾아서 역할 변경
    const selects = screen.getAllByRole("combobox");
    const enabledSelects = selects.filter(s => !(s as HTMLSelectElement).disabled);
    expect(enabledSelects.length).toBeGreaterThan(0);

    // tester1의 셀렉터 (일반 사용자 역할 값 "user"를 가진 것)
    const testerSelect = enabledSelects.find(s => (s as HTMLSelectElement).value === "user");
    if (testerSelect) {
      await user.selectOptions(testerSelect, "qa_manager");
      await waitFor(() => {
        expect(usersApi.updateRole).toHaveBeenCalledWith(2, "qa_manager");
      });
    }
  });

  it("계정 요청 섹션이 함께 렌더링된다", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("계정 요청")).toBeInTheDocument();
    });
    // 오류 상태가 아니라 실제 목록 응답으로 그려진 것이어야 한다
    expect(accountRequestsApi.list).toHaveBeenCalledWith("pending");
    expect(screen.getByText("대기 중인 요청이 없습니다.")).toBeInTheDocument();
    expect(screen.queryByText("처리에 실패했습니다.")).not.toBeInTheDocument();
  });

  it("프로젝트 배정 관리 버튼이 있다", async () => {
    renderPage();
    await waitFor(() => {
      // user 역할 사용자에게만 "관리" 버튼이 표시됨
      const manageButtons = screen.getAllByText("관리");
      expect(manageButtons.length).toBeGreaterThan(0);
    });
  });
});

describe("AdminPage 계정 상태 관리", () => {
  const people = [
    { id: 1, username: "admin", email: "admin@x.com", email_verified: false, display_name: "관리자", role: UserRole.ADMIN,
      must_change_password: false, created_at: "2026-01-01T00:00:00", status: "active" as const, has_password: true, google_linked: false },
    { id: 2, username: "both@x.com", email: "both@x.com", email_verified: true, display_name: "둘다", role: UserRole.USER,
      must_change_password: false, created_at: "2026-01-02T00:00:00", status: "active" as const, has_password: true, google_linked: true },
    { id: 3, username: "p@x.com", email: "p@x.com", email_verified: false, display_name: "대기", role: UserRole.USER,
      must_change_password: false, created_at: "2026-01-03T00:00:00", status: "pending" as const, has_password: true, google_linked: false },
    { id: 4, username: "off", display_name: "중지", role: UserRole.USER, must_change_password: false,
      created_at: "2026-01-04T00:00:00", status: "disabled" as const, has_password: true, google_linked: false },
  ];

  beforeEach(() => {
    vi.mocked(usersApi.list).mockResolvedValue(people as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("이메일, 로그인 방식, 상태를 보여 준다", async () => {
    renderPage();
    expect((await screen.findAllByText("both@x.com", { selector: "td" })).length).toBe(2);
    expect(screen.getByText("이메일")).toBeInTheDocument();
    expect(screen.getByText("로그인 방식")).toBeInTheDocument();
    expect(screen.getByText("비밀번호 + Google")).toBeInTheDocument();
    expect(screen.getAllByText("승인 대기").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("사용 중지됨")).toBeInTheDocument();
  });

  it("승인 대기 건수와 승인 버튼", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.approve).mockResolvedValue({} as never);
    renderPage();
    expect(await screen.findByText("승인 대기 1명")).toBeInTheDocument();
    const approve = screen.getAllByRole("button", { name: "승인" });
    expect(approve).toHaveLength(1);
    await user.click(approve[0]);
    await waitFor(() => expect(usersApi.approve).toHaveBeenCalledWith(3));
    await waitFor(() => expect(vi.mocked(usersApi.list).mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("거절은 확인을 받고 부른다", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.reject).mockResolvedValue(undefined);
    renderPage();
    await user.click(await screen.findByRole("button", { name: "거절" }));
    await waitFor(() => expect(usersApi.reject).toHaveBeenCalledWith(3));
  });

  it("사용 중지는 본인 행에 없고, 중지된 행에는 다시 사용", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.disable).mockResolvedValue({} as never);
    vi.mocked(usersApi.enable).mockResolvedValue({} as never);
    renderPage();
    await screen.findAllByText("both@x.com", { selector: "td" });
    // 사용 중지 대상: 2(사용), 3(대기). 본인(1)과 중지된 4 는 없다
    const stops = screen.getAllByRole("button", { name: "사용 중지" });
    expect(stops).toHaveLength(2);
    await user.click(stops[0]);
    await waitFor(() => expect(usersApi.disable).toHaveBeenCalledWith(2));
    await user.click(screen.getByRole("button", { name: "다시 사용" }));
    await waitFor(() => expect(usersApi.enable).toHaveBeenCalledWith(4));
  });

  it("이메일 해제는 Google 이 확인하지 않은 이메일에만", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.releaseEmail).mockResolvedValue({} as never);
    renderPage();
    await screen.findAllByText("both@x.com", { selector: "td" });
    const release = screen.getAllByRole("button", { name: "이메일 해제" });
    expect(release).toHaveLength(1);
    await user.click(release[0]);
    await waitFor(() => expect(usersApi.releaseEmail).toHaveBeenCalledWith(3));
  });

  it("서버가 거절하면 사유를 보여 준다", async () => {
    const user = userEvent.setup();
    const toast = (await import("react-hot-toast")).default;
    vi.mocked(usersApi.disable).mockRejectedValue({ response: { data: { detail: "마지막 관리자는 사용 중지할 수 없습니다." } } });
    renderPage();
    await user.click((await screen.findAllByRole("button", { name: "사용 중지" }))[0]);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("마지막 관리자는 사용 중지할 수 없습니다."));
  });
});

describe("AdminPage 연결된 Google 계정과 빈 계정 삭제", () => {
  const base = { must_change_password: false, created_at: "2026-01-01T00:00:00", status: "active" as const };
  const people = [
    { ...base, id: 1, username: "admin", display_name: "관리자", role: UserRole.ADMIN, has_password: true,
      google_linked: true, email: "boss@gmail.com", email_verified: true, google_email: "boss@gmail.com" },
    { ...base, id: 2, username: "old", display_name: "옛 연결", role: UserRole.USER, has_password: true,
      google_linked: true, google_email: null },
    { ...base, id: 3, username: "p@x.com", email: "p@x.com", display_name: "대기", role: UserRole.USER,
      has_password: true, google_linked: false, status: "pending" as const },
    { ...base, id: 4, username: "off", display_name: "중지", role: UserRole.USER, has_password: false,
      google_linked: true, google_email: "off@gmail.com", status: "disabled" as const },
  ];

  beforeEach(() => {
    vi.mocked(usersApi.list).mockResolvedValue(people as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("로그인 방식 칸에 연결된 Google 계정 주소를 보여 준다", async () => {
    renderPage();
    expect(await screen.findByText("Google: boss@gmail.com")).toBeInTheDocument();
    expect(screen.getByText("Google: off@gmail.com")).toBeInTheDocument();
    // 이 기능 전에 연결돼 주소가 없는 계정은 다음 Google 로그인 때 채워진다
    expect(screen.getByText("Google: 주소 미기록")).toBeInTheDocument();
  });

  it("삭제는 본인과 승인 대기 행에 없고, 확인을 받고 부른다", async () => {
    const user = userEvent.setup();
    vi.mocked(usersApi.remove).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("Google: boss@gmail.com");
    const deletes = screen.getAllByRole("button", { name: "삭제" });
    expect(deletes).toHaveLength(2);
    await user.click(deletes[1]);
    expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("작업 기록이 없는 계정만"));
    await waitFor(() => expect(usersApi.remove).toHaveBeenCalledWith(4));
    await waitFor(() => expect(vi.mocked(usersApi.list).mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it("비밀번호 초기화 뒤 목록을 다시 불러와 끊긴 Google 연결을 반영한다", async () => {
    const user = userEvent.setup();
    let resetDone = false;
    vi.mocked(usersApi.list).mockImplementation(async () =>
      (resetDone
        ? people.map((p) => (p.id === 4 ? { ...p, google_linked: false, google_email: null } : p))
        : people) as never);
    vi.mocked(usersApi.resetPassword).mockImplementation(async () => {
      resetDone = true;
      return { temp_password: "Temp1234abcd" };
    });
    renderPage();
    await screen.findByText("Google: off@gmail.com");
    // 초기화 버튼은 본인(1)을 뺀 2, 3, 4 행에 있다. 마지막이 4(off)
    const resets = screen.getAllByRole("button", { name: "초기화" });
    await user.click(resets[resets.length - 1]);
    await waitFor(() => expect(usersApi.resetPassword).toHaveBeenCalledWith(4));
    await waitFor(() => expect(screen.queryByText("Google: off@gmail.com")).not.toBeInTheDocument());
  });

  it("작업 기록이 있어 삭제가 거절되면 사유를 보여 준다", async () => {
    const user = userEvent.setup();
    const toast = (await import("react-hot-toast")).default;
    vi.mocked(usersApi.remove).mockRejectedValue(
      { response: { data: { detail: "작업 기록이 있는 계정은 삭제할 수 없습니다. 사용 중지를 쓰세요." } } });
    renderPage();
    await user.click((await screen.findAllByRole("button", { name: "삭제" }))[0]);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      "작업 기록이 있는 계정은 삭제할 수 없습니다. 사용 중지를 쓰세요."));
  });
});

describe("AdminPage 조회 실패 표시 (SYM-160)", () => {
  it("배정 조회가 실패하면 '미배정' 대신 조회 실패를 보이고 알린다", async () => {
    vi.mocked(usersApi.getAllAssignments).mockRejectedValue(new Error("422"));
    renderPage();
    expect(await screen.findByText("조회 실패")).toBeInTheDocument();
    expect(screen.queryByText("미배정")).not.toBeInTheDocument();
    expect(vi.mocked(toast.error)).toHaveBeenCalledWith("프로젝트 배정을 불러오지 못했습니다.", expect.anything());
  });

  it("프로젝트 목록 조회가 실패하면 알린다", async () => {
    vi.mocked(projectsApi.list).mockRejectedValue(new Error("500"));
    renderPage();
    await waitFor(() =>
      expect(vi.mocked(toast.error)).toHaveBeenCalledWith("프로젝트 목록을 불러오지 못했습니다.", expect.anything()));
  });

  it("배정 모달은 프로젝트마다 멤버를 부르지 않고 전체 배정 조회로 채운다", async () => {
    vi.mocked(usersApi.getAllAssignments).mockResolvedValue({
      "2": [{ id: 11, project_id: 1, project_name: "프로젝트A", role: "tester" }],
    });
    renderPage();
    await userEvent.click((await screen.findAllByText("관리")).find((el) => el.tagName === "BUTTON")!);
    expect(await screen.findByText("테스터1 프로젝트 배정")).toBeInTheDocument();
    expect(await screen.findByText("제거")).toBeInTheDocument();
    expect(membersApi.list).not.toHaveBeenCalled();
  });

  it("배정 모달 조회가 실패하면 '배정된 프로젝트가 없습니다' 대신 실패를 보인다", async () => {
    renderPage();
    const btn = (await screen.findAllByText("관리")).find((el) => el.tagName === "BUTTON")!;
    vi.mocked(usersApi.getAllAssignments).mockRejectedValue(new Error("500"));
    await userEvent.click(btn);
    expect(await screen.findByText("배정 정보를 불러오지 못했습니다. 창을 닫고 다시 열어 주세요.")).toBeInTheDocument();
    expect(screen.queryByText("배정된 프로젝트가 없습니다.")).not.toBeInTheDocument();
  });
});
