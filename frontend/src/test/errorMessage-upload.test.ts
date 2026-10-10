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
  "이미 올린 업로드입니다.",
  "이미 올리는 중인 업로드입니다.",
  "이 배포에서는 저장소에 직접 올립니다.",
  "비밀번호는 72바이트 이하로 입력해 주세요(영문 72자, 한글 24자까지).",
  "입력값이 허용 길이나 형식을 벗어났습니다. 긴 값을 줄여 다시 시도해 주세요.",
  "날짜는 YYYY-MM-DD 형식으로 보내 주세요.",
  "API 키로는 할 수 없는 작업입니다. 로그인해서 진행해 주세요.",
  "다른 요청과 겹쳤습니다. 다시 시도해 주세요.",
  "이 작업을 수행할 권한이 없습니다.",
  "이 프로젝트에 접근 권한이 없습니다.",
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

describe("translateError: 문자열이 아닌 detail", () => {
  it("pydantic 422 배열은 문자열 문구로 바뀐다(토스트가 객체를 그리다 깨지지 않게)", () => {
    const out = translateError([{ type: "string_too_long", loc: ["body", "depth1"], msg: "String should have at most 200 characters" }]);
    expect(typeof out).toBe("string");
    expect(out.length).toBeGreaterThan(0);
  });

  it("가져오기 길이 초과 문구는 앞부분만 번역하고 행 목록은 남긴다", async () => {
    await i18n.changeLanguage("en");
    const out = translateError("허용 길이를 넘는 칸이 있어 가져오지 않았습니다. 값을 줄여 다시 올려 주세요: 기본 시트 3행 R1(14/10자)");
    expect(out.startsWith("Nothing was imported")).toBe(true);
    expect(out.endsWith("기본 시트 3행 R1(14/10자)")).toBe(true);
  });
});

