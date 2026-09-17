/**
 * 접근성 검사 (axe-core, 컴포넌트 단위)
 *
 * E2E 의 axe 검사는 실제 브라우저를 보지만 8분짜리 파이프라인 끝에 있다.
 * 여기서 컴포넌트 단위로 먼저 걸러야 고치는 사람이 빨리 안다.
 *
 * serious 이상만 막는다. 이 기준은 e2e/accessibility.spec.ts 와 같다.
 */
import axe from "axe-core";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ChangePasswordModal from "../components/ChangePasswordModal";
import type { CustomCellRendererProps } from "ag-grid-react";

import MarkdownCell from "../components/MarkdownCell";
import Header from "../components/Header";
import LoginPage from "../pages/LoginPage";
import RegisterPage from "../pages/RegisterPage";
import AccountHelpPage from "../pages/AccountHelpPage";
import { UserRole } from "../types";
import { renderWithProviders } from "./helpers";

vi.mock("react-hot-toast", () => ({
  default: { success: vi.fn(), error: vi.fn() },
  Toaster: () => null,
}));

vi.mock("../contexts/ThemeContext", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ user, logout: vi.fn() }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("../api", () => ({
  authApi: {
    login: vi.fn(),
    getMe: vi.fn(),
    checkUsername: vi.fn().mockResolvedValue({ available: true }),
    register: vi.fn(),
    changePassword: vi.fn(),
    submitAccountRequest: vi.fn(),
  },
  projectsApi: { list: vi.fn().mockResolvedValue([]) },
}));

const user = {
  id: 1,
  username: "admin",
  display_name: "관리자",
  role: UserRole.ADMIN,
  must_change_password: false,
  created_at: "2026-01-01",
};

const BLOCKING = ["critical", "serious"];

async function violationsOf(container: HTMLElement): Promise<string[]> {
  const results = await axe.run(container, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
  });
  return results.violations
    .filter((v) => BLOCKING.includes(v.impact ?? ""))
    .map((v) => {
      const where = v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ");
      return `[${v.impact}] ${v.id}: ${v.help} -> ${where}`;
    });
}

describe("접근성", () => {
  it("로그인 화면에 serious 이상 위반이 없다", async () => {
    const { container } = renderWithProviders(<LoginPage />);
    const found = await violationsOf(container);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("회원가입 화면에 serious 이상 위반이 없다", async () => {
    const { container } = renderWithProviders(<RegisterPage />);
    const found = await violationsOf(container);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("헤더에 serious 이상 위반이 없다", async () => {
    const { container } = renderWithProviders(<Header />);
    const found = await violationsOf(container);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("비밀번호 변경 모달에 serious 이상 위반이 없다", async () => {
    const { container } = renderWithProviders(<ChangePasswordModal />);
    const found = await violationsOf(container);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("계정 도움말 화면에 serious 이상 위반이 없다", async () => {
    const { container } = renderWithProviders(<AccountHelpPage />);
    const found = await violationsOf(container);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("로그인 폼의 라벨이 입력과 이어져 있다", async () => {
    // axe 는 placeholder 를 이름으로 인정해 통과시킨다. 그러나 placeholder 는
    // 입력을 시작하면 사라지므로 라벨의 대체물이 아니다. 라벨로 찾아본다.
    const { getByLabelText } = renderWithProviders(<LoginPage />);
    expect(getByLabelText("아이디")).toBeTruthy();
    expect(getByLabelText("비밀번호")).toBeTruthy();
  });

  it("비밀번호 변경 모달이 dialog 로 읽히고 제목이 연결돼 있다", async () => {
    // 역할이 없으면 스크린리더는 이것이 모달인지 모르고 뒤 배경과 구분하지 못한다.
    const u = userEvent.setup();
    const { getByRole, getByText } = renderWithProviders(<Header />);
    await u.click(getByText("관리자"));
    await u.click(getByText("비밀번호 변경"));

    const dialog = getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
  });

  it("강제 비밀번호 변경 화면의 라벨이 입력과 이어져 있다", async () => {
    const { getByLabelText } = renderWithProviders(<ChangePasswordModal />);
    expect(getByLabelText("현재 비밀번호")).toBeTruthy();
    expect(getByLabelText("새 비밀번호")).toBeTruthy();
    expect(getByLabelText("새 비밀번호 확인")).toBeTruthy();
  });

  it("그리드 셀 렌더러에 serious 이상 위반이 없다", async () => {
    // 화면 단위 검사에서 ag-grid 뼈대를 제외하므로 셀 내용은 여기서 본다
    const props = {
      value: "**굵게** 와 `코드`",
      context: { searchKeyword: "코드" },
    } as unknown as CustomCellRendererProps;
    const { container } = renderWithProviders(<MarkdownCell {...props} />);
    const found = await violationsOf(container);
    expect(found, found.join("\n")).toEqual([]);
  });

  it("검사기가 실제로 위반을 잡는다", async () => {
    // 검사가 켜져 있는지 확인한다. 통과만 보면 규칙이 꺼져 있어도 초록이다.
    const { container } = renderWithProviders(
      <div>
        <input type="text" />
      </div>
    );
    const found = await violationsOf(container);
    expect(found.some((f) => f.includes("label"))).toBe(true);
  });
});
