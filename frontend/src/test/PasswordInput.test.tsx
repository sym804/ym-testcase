import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PasswordInput from "../components/PasswordInput";

describe("PasswordInput", () => {
  it("기본적으로 password 타입이다", () => {
    render(<PasswordInput placeholder="비밀번호" value="" onChange={() => {}} />);
    const input = screen.getByPlaceholderText("비밀번호");
    expect(input).toHaveAttribute("type", "password");
  });

  it("눈 아이콘 클릭 시 text 타입으로 변경된다", async () => {
    const user = userEvent.setup();
    render(<PasswordInput placeholder="비밀번호" value="secret" onChange={() => {}} />);

    const toggleBtn = screen.getByTitle("비밀번호 보기");
    await user.click(toggleBtn);

    const input = screen.getByPlaceholderText("비밀번호");
    expect(input).toHaveAttribute("type", "text");
  });

  it("다시 클릭하면 password 타입으로 돌아간다", async () => {
    const user = userEvent.setup();
    render(<PasswordInput placeholder="비밀번호" value="secret" onChange={() => {}} />);

    const toggleBtn = screen.getByTitle("비밀번호 보기");
    await user.click(toggleBtn);

    const hideBtn = screen.getByTitle("비밀번호 숨기기");
    await user.click(hideBtn);

    const input = screen.getByPlaceholderText("비밀번호");
    expect(input).toHaveAttribute("type", "password");
  });

  it("onChange 이벤트가 전달된다", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PasswordInput placeholder="비밀번호" value="" onChange={onChange} />);

    await user.type(screen.getByPlaceholderText("비밀번호"), "a");
    expect(onChange).toHaveBeenCalled();
  });
});
