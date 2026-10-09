import { describe, it, expect } from "vitest";
import { errorText, googleErrorMessage, translateError } from "../utils/errorMessage";
import i18n from "../i18n";

// 계획 4a 의 백엔드 detail 문구표. 글자가 바뀌면 이 표가 먼저 깨진다.
const DETAILS = [
  "관리자 승인을 기다리는 중입니다.",
  "사용이 중지된 계정입니다.",
  "이메일로 가입해 주세요.",
  "이미 가입된 이메일입니다.",
  "회사 이메일로만 가입할 수 있습니다.",
  "가입 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
  "첫 관리자 토큰이 올바르지 않습니다.",
  "비밀번호가 없는 계정입니다.",
  "표시 이름을 입력해 주세요.",
  "아이디를 입력해 주세요.",
  "승인 대기 중인 계정이 아닙니다.",
  "승인 대기 중인 계정만 거절할 수 있습니다.",
  "다른 기록에 연결된 계정이라 거절할 수 없습니다. 사용 중지를 쓰세요.",
  "자기 자신은 사용 중지할 수 없습니다.",
  "이미 사용 중지된 계정입니다.",
  "마지막 관리자는 사용 중지할 수 없습니다.",
  "사용 중지된 계정이 아닙니다.",
  "Google 이 확인한 이메일은 해제할 수 없습니다.",
  "해제할 이메일이 없습니다.",
  "자기 자신의 이메일은 해제할 수 없습니다.",
  "마지막 관리자의 역할은 바꿀 수 없습니다.",
  "비밀번호가 없는 계정은 Google 연결을 해제할 수 없습니다.",
  "사용 중인 계정만 처리할 수 있습니다.",
  "자기 자신은 삭제할 수 없습니다.",
  "마지막 관리자는 삭제할 수 없습니다.",
  "작업 기록이 있는 계정은 삭제할 수 없습니다. 사용 중지를 쓰세요.",
];

describe("인증 오류 문구 번역", () => {
  it.each(DETAILS)("영어 화면에서 %s 가 번역된다", async (detail) => {
    await i18n.changeLanguage("en");
    try {
      const out = translateError(detail);
      expect(out).not.toBe(detail);
      expect(out).toMatch(/[A-Za-z]/);
    } finally {
      await i18n.changeLanguage("ko");
    }
  });
});

describe("콜백 오류 코드와 검증 오류", () => {
  it("모르는 콜백 코드는 일반 문구로 바꾼다(허용 목록)", () => {
    expect(googleErrorMessage("pending")).toBe("관리자 승인을 기다리는 중입니다.");
    expect(googleErrorMessage("__proto__")).toBe("Google 로그인에 실패했습니다. 다시 시도해 주세요.");
    expect(googleErrorMessage("googleErrors")).toBe("Google 로그인에 실패했습니다. 다시 시도해 주세요.");
  });

  it("pydantic 검증 오류 배열은 원문 대신 사용자 언어의 대체 문구를 쓴다", () => {
    const err = { response: { data: { detail: [{ msg: "String should have at most 254 characters" }] } } };
    expect(errorText(err, "회원가입에 실패했습니다.")).toBe("회원가입에 실패했습니다.");
  });
});
