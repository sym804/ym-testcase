import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ApiKeyItem } from "../types";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("../api", () => ({
  authApi: { listApiKeys: vi.fn(), createApiKey: vi.fn(), revokeApiKey: vi.fn() },
}));

import toast from "react-hot-toast";
import { authApi } from "../api";
import ApiKeysModal from "../components/ApiKeysModal";

const item = (over: Partial<ApiKeyItem> = {}): ApiKeyItem => ({
  id: 1, name: "CI", prefix: "ymtc_ab12cd34", created_at: "2026-10-01T10:00:00", last_used_at: null,
  expires_at: "2026-12-30T10:00:00", revoked_at: null, status: "active", ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("API 키 모달", () => {
  it("목록을 불러와 키 앞부분과 상태를 보여 주고 원문은 없다", async () => {
    vi.mocked(authApi.listApiKeys).mockResolvedValue([
      item(),
      item({ id: 2, name: "옛 키", prefix: "ymtc_99999999", status: "revoked", revoked_at: "2026-10-01T11:00:00" }),
    ]);
    render(<ApiKeysModal onClose={vi.fn()} />);
    expect(await screen.findByText("ymtc_ab12cd34…")).toBeInTheDocument();
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByRole("button", { name: /CI/ })).toBeInTheDocument();
    expect(within(rows[2]).queryByRole("button")).toBeNull();
  });

  it("발급하면 원문을 한 번 보여 주고 목록을 다시 읽는다", async () => {
    vi.mocked(authApi.listApiKeys).mockResolvedValueOnce([]).mockResolvedValueOnce([item()]);
    vi.mocked(authApi.createApiKey).mockResolvedValue({ ...item(), key: "ymtc_ab12cd34_SECRET" });
    render(<ApiKeysModal onClose={vi.fn()} />);
    await screen.findByText(/발급한 키가 없습니다|No keys yet/);

    await userEvent.type(screen.getByPlaceholderText(/e2e/), "CI");
    await userEvent.selectOptions(screen.getByRole("combobox"), "none");
    await userEvent.click(screen.getByRole("button", { name: /^발급$|^Create$/ }));

    expect(authApi.createApiKey).toHaveBeenCalledWith("CI", null);
    const box = await screen.findByTestId("api-key-created");
    expect(box).toHaveTextContent("ymtc_ab12cd34_SECRET");
    await waitFor(() => expect(authApi.listApiKeys).toHaveBeenCalledTimes(2));
  });

  it("이름이 비면 서버를 부르지 않는다", async () => {
    vi.mocked(authApi.listApiKeys).mockResolvedValue([]);
    render(<ApiKeysModal onClose={vi.fn()} />);
    await screen.findByText(/발급한 키가 없습니다|No keys yet/);
    await userEvent.click(screen.getByRole("button", { name: /^발급$|^Create$/ }));
    expect(authApi.createApiKey).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  it("폐기는 확인을 받고 부른 뒤 목록을 다시 읽는다", async () => {
    vi.mocked(authApi.listApiKeys).mockResolvedValue([item()]);
    vi.mocked(authApi.revokeApiKey).mockResolvedValue(item({ status: "revoked" }));
    render(<ApiKeysModal onClose={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /CI/ }));
    expect(window.confirm).toHaveBeenCalled();
    expect(authApi.revokeApiKey).toHaveBeenCalledWith(1);
    await waitFor(() => expect(authApi.listApiKeys).toHaveBeenCalledTimes(2));
  });

  it("확인을 취소하면 폐기하지 않는다", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);
    vi.mocked(authApi.listApiKeys).mockResolvedValue([item()]);
    render(<ApiKeysModal onClose={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /CI/ }));
    expect(authApi.revokeApiKey).not.toHaveBeenCalled();
  });

  it("발급 한도에 걸리면 서버 사유를 보여 준다", async () => {
    vi.mocked(authApi.listApiKeys).mockResolvedValue([]);
    vi.mocked(authApi.createApiKey).mockRejectedValue({ response: { data: { detail: "사용 중인 키가 20개입니다. 쓰지 않는 키를 폐기한 뒤 만들어 주세요." } } });
    render(<ApiKeysModal onClose={vi.fn()} />);
    await screen.findByText(/발급한 키가 없습니다|No keys yet/);
    await userEvent.type(screen.getByPlaceholderText(/e2e/), "21");
    await userEvent.click(screen.getByRole("button", { name: /^발급$|^Create$/ }));
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.queryByTestId("api-key-created")).toBeNull();
  });
});
