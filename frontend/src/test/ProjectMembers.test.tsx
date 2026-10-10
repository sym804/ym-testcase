import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProjectMembers from "../components/ProjectMembers";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

// ★같은 객체를 돌려준다(렌더마다 새 객체면 [currentUser] effect 가 반복된다, SYM-165 와 같은 이유)
const mockAuth = vi.hoisted(() => ({ role: "user", users: new Map<string, object>() }));
vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => {
    if (!mockAuth.users.has(mockAuth.role)) {
      mockAuth.users.set(mockAuth.role, { id: 99, username: "me", display_name: "나", role: mockAuth.role,
        must_change_password: false, created_at: "2026-01-01" });
    }
    return { user: mockAuth.users.get(mockAuth.role) };
  },
}));

vi.mock("../api", () => ({
  membersApi: {
    list: vi.fn(),
    add: vi.fn(),
    updateRole: vi.fn(),
    remove: vi.fn(),
    availableUsers: vi.fn(),
  },
}));

import { membersApi } from "../api";
import toast from "react-hot-toast";
import { UserRole } from "../types";

const mockMembers = [
  { id: 1, project_id: 1, user_id: 10, role: "admin", added_at: "2026-01-01T00:00:00", display_name: "생성자", username: "creator" },
  { id: 2, project_id: 1, user_id: 20, role: "tester", added_at: "2026-01-02T00:00:00", display_name: "테스터A", username: "testerA" },
];

const mockUsers = [
  { id: 10, username: "creator", display_name: "생성자", role: UserRole.ADMIN, must_change_password: false, created_at: "2026-01-01" },
  { id: 20, username: "testerA", display_name: "테스터A", role: UserRole.USER, must_change_password: false, created_at: "2026-01-01" },
  { id: 30, username: "newUser", display_name: "신규사용자", role: UserRole.USER, must_change_password: false, created_at: "2026-01-01" },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.role = "user";
  vi.mocked(membersApi.list).mockResolvedValue(mockMembers);
  vi.mocked(membersApi.add).mockResolvedValue({} as any);
  vi.mocked(membersApi.updateRole).mockResolvedValue({} as any);
  vi.mocked(membersApi.remove).mockResolvedValue(undefined);
  vi.mocked(membersApi.availableUsers).mockResolvedValue(mockUsers);
});

describe("ProjectMembers", () => {
  it("멤버 목록을 렌더링한다", async () => {
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    await waitFor(() => {
      expect(screen.getByText("creator")).toBeInTheDocument();
      expect(screen.getByText("testerA")).toBeInTheDocument();
    });
  });

  it("생성자에 배지를 표시한다", async () => {
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    await waitFor(() => {
      // "생성자" badge is shown for the creator
      const badges = screen.getAllByText("생성자");
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("admin은 멤버 추가 행을 볼 수 있다", async () => {
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    await waitFor(() => {
      expect(screen.getByText("추가")).toBeInTheDocument();
    });
    // 미등록 사용자만 추가 가능 목록에 표시
    expect(screen.getByText(/신규사용자/)).toBeInTheDocument();
  });

  it("tester는 멤버 추가 행을 볼 수 없다", async () => {
    render(<ProjectMembers projectId={1} createdBy={10} myRole="tester" />);
    await waitFor(() => {
      expect(screen.getByText("프로젝트 멤버")).toBeInTheDocument();
    });
    expect(screen.queryByText("추가")).not.toBeInTheDocument();
  });

  it("멤버 추가가 작동한다", async () => {
    const user = userEvent.setup();
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);

    await waitFor(() => {
      expect(screen.getByText(/신규사용자/)).toBeInTheDocument();
    });

    // 사용자 선택
    const selects = screen.getAllByRole("combobox");
    await user.selectOptions(selects[0], "30");
    await user.click(screen.getByText("추가"));

    await waitFor(() => {
      expect(membersApi.add).toHaveBeenCalledWith(1, 30, "tester");
      expect(toast.success).toHaveBeenCalledWith("멤버가 추가되었습니다.");
    });
  });

  it("시스템 관리자가 아니면 생성자 X 버튼이 없다", async () => {
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    await waitFor(() => {
      expect(screen.getByText("creator")).toBeInTheDocument();
    });
    // X 버튼은 생성자가 아닌 멤버만
    const removeButtons = screen.getAllByTitle("멤버 제거");
    expect(removeButtons).toHaveLength(1); // testerA만
  });

  it("로딩 중 메시지를 표시한다", () => {
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    expect(screen.getByText("불러오는 중...")).toBeInTheDocument();
  });
});

describe("ProjectMembers 생성자 행", () => {
  const creatorRow = async () => (await screen.findByText("creator")).closest("tr")!;

  it("프로젝트 admin 이라도 시스템 역할이 user 면 생성자의 역할 변경과 제거가 없다", async () => {
    mockAuth.role = "user";
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    const row = await creatorRow();
    expect(row.querySelector("select")).toBeNull();
    expect(row.querySelector("button")).toBeNull();
  });

  it("시스템 관리자는 생성자의 역할을 바꾸고 뺄 수 있다(강등된 생성자 권한 회수)", async () => {
    mockAuth.role = "admin";
    render(<ProjectMembers projectId={1} createdBy={10} myRole="admin" />);
    const row = await creatorRow();
    expect(row.querySelector("select")).not.toBeNull();
    expect(row.querySelector("button")).not.toBeNull();
  });
});

