import { describe, it, expect } from "vitest";
import { translateError } from "../utils/errorMessage";
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
