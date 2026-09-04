import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountRequestSection from "../components/AccountRequestSection";
import { UserRole } from "../types";

vi.mock("../api", () => ({
  usersApi: { list: vi.fn() },
  accountRequestsApi: {
    submit: vi.fn(),
    list: vi.fn(),
    approve: vi.fn(),
    reject: vi.fn(),
    resetWithCode: vi.fn(),
  },
}));

import { usersApi, accountRequestsApi } from "../api";

const mockUsers = [
  { id: 1, username: "admin", display_name: "관리자", role: UserRole.ADMIN, must_change_password: false, created_at: "2026-01-01T00:00:00" },
  { id: 2, username: "tester1", display_name: "테스터1", role: UserRole.USER, must_change_password: false, created_at: "2026-01-02T00:00:00" },
];

const mockRequests = [
  {
    id: 11,
    request_type: "reset_password",
    status: "pending",
    claimed_username: "tester1",
    claimed_display_name: null,
    contact: "메신저 tester1",
    note: null,
    user_id: null,
    created_at: "2026-09-01T10:00:00",
    resolved_at: null,
  },
  {
    id: 12,
    request_type: "reset_password",
    status: "pending",
    claimed_username: "tester2",
    claimed_display_name: null,
    contact: "메신저 tester2",
    note: null,
    user_id: null,
    created_at: "2026-09-02T10:00:00",
    resolved_at: null,
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(usersApi.list).mockResolvedValue(mockUsers as never);
  vi.mocked(accountRequestsApi.list).mockResolvedValue(mockRequests as never);
});

/** 요청 행의 대상 계정 셀렉터에서 tester1 을 고른다. */
async function pickTarget(user: ReturnType<typeof userEvent.setup>, rowIndex: number) {
  const selects = screen.getAllByRole("combobox");
  await user.selectOptions(selects[rowIndex], "2");
}

describe("AccountRequestSection", () => {
  it("두 번째 요청을 승인해도 앞서 발급된 코드가 화면에 남는다", async () => {
    // 코드는 서버에 해시로만 남는다. 화면에서 사라지면 영구히 잃는다.
    const user = userEvent.setup();
    vi.mocked(accountRequestsApi.approve)
      .mockResolvedValueOnce({
        request_type: "reset_password",
        username: null,
        code: "FIRSTCODE111",
        code_expires_at: "2026-09-05T10:00:00",
      } as never)
      .mockResolvedValueOnce({
        request_type: "reset_password",
        username: null,
        code: "SECONDCODE22",
        code_expires_at: "2026-09-06T10:00:00",
      } as never);

    render(<AccountRequestSection />);
    await waitFor(() => expect(screen.getByText("tester1")).toBeInTheDocument());

    const approveButtons = screen.getAllByRole("button", { name: "승인" });
    await pickTarget(user, 0);
    await user.click(approveButtons[0]);
    await waitFor(() => expect(screen.getByText("FIRSTCODE111")).toBeInTheDocument());

    await pickTarget(user, 1);
    await user.click(screen.getAllByRole("button", { name: "승인" })[1]);
    await waitFor(() => expect(screen.getByText("SECONDCODE22")).toBeInTheDocument());

    // 두 코드가 동시에 보여야 한다. 하나로 덮어쓰면 첫 코드는 다시 볼 수 없다.
    expect(screen.getByText("FIRSTCODE111")).toBeInTheDocument();
    expect(screen.getByText("SECONDCODE22")).toBeInTheDocument();
  });

  it("반려 프롬프트를 취소하면 반려 API 를 호출하지 않는다", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue(null);

    render(<AccountRequestSection />);
    await waitFor(() => expect(screen.getByText("tester1")).toBeInTheDocument());

    await user.click(screen.getAllByRole("button", { name: "반려" })[0]);

    expect(window.prompt).toHaveBeenCalled();
    expect(accountRequestsApi.reject).not.toHaveBeenCalled();
  });

  it("대상 계정을 고르지 않고 승인하면 안내만 뜨고 승인 API 를 호출하지 않는다", async () => {
    const user = userEvent.setup();

    render(<AccountRequestSection />);
    await waitFor(() => expect(screen.getByText("tester1")).toBeInTheDocument());

    await user.click(screen.getAllByRole("button", { name: "승인" })[0]);

    await waitFor(() => {
      expect(screen.getByText("대상 계정을 먼저 선택해 주세요.")).toBeInTheDocument();
    });
    expect(accountRequestsApi.approve).not.toHaveBeenCalled();
  });
});
