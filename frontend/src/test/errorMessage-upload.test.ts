import { describe, it, expect, beforeAll } from "vitest";
import i18n from "../i18n";
import { translateError } from "../utils/errorMessage";

// 스테이징 업로드와 잠금 대기에서 새로 생긴 서버 문구가 영어 화면에 한국어로 새지 않는지 본다.
const SERVER_DETAILS = [
  "업로드를 찾을 수 없습니다.",
  "이미 처리한 업로드입니다.",
  "같은 업로드를 처리하는 중입니다.",
  "파일이 아직 올라오지 않았습니다.",
  "다른 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요.",
  "파일 저장소에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
  "Excel 97-2003 형식(.xls)이거나 암호가 걸린 파일은 읽을 수 없습니다. 암호를 풀고 .xlsx 로 다시 저장해 올려 주세요.",
];

describe("translateError: 업로드·잠금 문구", () => {
  beforeAll(async () => {
    await i18n.changeLanguage("en");
  });

  it.each(SERVER_DETAILS)("%s 는 영어로 바뀐다", (detail) => {
    const out = translateError(detail);
    expect(out).not.toBe(detail);
    expect(out).not.toMatch(/[가-힣]/);
  });

  it("문구마다 서로 다른 번역이다", () => {
    const outs = SERVER_DETAILS.map(translateError);
    expect(new Set(outs).size).toBe(SERVER_DETAILS.length);
  });
});
