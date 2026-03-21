import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ProjectMembers from "../components/ProjectMembers";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  membersApi: {
    list: vi.fn(),
    add: vi.fn(),
    updateRole: vi.fn(),
    remove: vi.fn(),
  },
  usersApi: {
    list: vi.fn(),
  },
}));

import { membersApi, usersApi } from "../api";
import toast from "react-hot-toast";

const mockMembers = [
  { id: 1, project_id: 1, user_id: 10, role: "admin", added_at: "2026-01-01T00:00:00", display_name: "생성자", username: "creator" },
  { id: 2, project_id: 1, user_id: 20, role: "tester", added_at: "2026-01-02T00:00:00", display_name: "테스터A", username: "testerA" },
];

const mockUsers = [
  { id: 10, username: "creator", display_name: "생성자", role: "admin", must_change_password: false, created_at: "2026-01-01" },
  { id: 20, username: "testerA", display_name: "테스터A", role: "user", must_change_password: false, created_at: "2026-01-01" },
  { id: 30, username: "newUser", display_name: "신규사용자", role: "user", must_change_password: false, created_at: "2026-01-01" },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(membersApi.list).mockResolvedValue(mockMembers);
  vi.mocked(membersApi.add).mockResolvedValue({});
  vi.mocked(membersApi.updateRole).mockResolvedValue({});
  vi.mocked(membersApi.remove).mockResolvedValue(undefined);
  vi.mocked(usersApi.list).mockResolvedValue(mockUsers);
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

  it("생성자는 제거할 수 없다 (X 버튼 없음)", async () => {
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
