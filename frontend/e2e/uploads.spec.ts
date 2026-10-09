import { writeFile } from "node:fs/promises";
import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

// 스테이징 업로드 흐름: 서버가 발급한 주소에 파일을 직접 올리고(PUT) upload_id 로 처리한다.
// CI 는 프론트(5173)와 백엔드(8008)가 다른 출처라 교차 출처 PUT 까지 함께 확인된다.

const TEST_ADMIN_PASSWORD = process.env.TEST_ADMIN_PASSWORD || "test1234";

const CSV = Buffer.from(
  "﻿No,TC ID,Test Script (Step-by-Step) - Step,Expected Result\r\n1,UP-1,1. 실행,성공\r\n",
  "utf-8",
);
const JUNIT = Buffer.from(
  '<testsuites><testsuite name="a"><testcase name="UP-1 ok" time="1"/></testsuite></testsuites>',
);
// 2x2 빨간 PNG
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==",
  "base64",
);

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(TEST_ADMIN_PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

async function authHeaders(request: APIRequestContext) {
  const res = await request.post("/api/auth/login", { data: { username: "admin", password: TEST_ADMIN_PASSWORD } });
  const { access_token } = await res.json();
  return { Authorization: `Bearer ${access_token}` };
}

// 브라우저가 보낸 업로드 발급 요청 수. 같은 파일을 미리보기 뒤 가져오기에 다시 올리지 않는지 본다.
function countStagings(page: Page) {
  const counter = { n: 0 };
  page.on("request", (req) => {
    if (req.method() === "POST" && new URL(req.url()).pathname === "/api/uploads") counter.n += 1;
  });
  return counter;
}

// 실패한 API 응답과 콘솔 오류. CI 에서만 나는 실패는 화면 캡처만으로 원인을 알 수 없어
// 실패할 때 첨부로 남긴다(CI 가 test-results 를 아티팩트로 보관한다).
function recordProblems(page: Page) {
  const problems: string[] = [];
  page.on("response", async (res) => {
    if (!res.url().includes("/api/") || res.status() < 400) return;
    const body = await res.text().catch(() => "");
    problems.push(`${res.request().method()} ${new URL(res.url()).pathname} -> ${res.status()} ${body.slice(0, 200)}`);
  });
  page.on("requestfailed", (req) => problems.push(`${req.method()} ${req.url()} failed: ${req.failure()?.errorText}`));
  page.on("console", (msg) => { if (msg.type() === "error") problems.push(`console: ${msg.text().slice(0, 300)}`); });
  return problems;
}

test.describe("스테이징 업로드", () => {
  let pid: number;
  let headers: Record<string, string>;
  let problems: string[];

  test.beforeEach(async ({ page, request }) => {
    problems = recordProblems(page);
    headers = await authHeaders(request);
    const res = await request.post("/api/projects", { data: { name: `E2E_Upload_${Date.now()}` }, headers });
    pid = (await res.json()).id;
  });

  test.afterEach(async ({ request }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      const file = testInfo.outputPath("api-and-console-problems.txt");
      await writeFile(file, problems.join("\n") || "(none)", "utf-8");
      await testInfo.attach("api-and-console-problems", { path: file, contentType: "text/plain" });
    }
    await request.delete(`/api/projects/${pid}`, { headers });
  });

  test("TC 가져오기: 미리보기와 가져오기가 한 번 올린 파일을 같이 쓰고, 같은 파일을 다시 골라도 가져온다", async ({ page, request }) => {
    const stagings = countStagings(page);
    page.on("dialog", (d) => d.accept()); // 두 번째 가져오기의 덮어쓰기 확인
    await login(page);
    await page.goto(`/projects/${pid}?tab=tc`);
    // 로딩 중에는 툴바의 파일 입력이 잠깐 있다가 빈 프로젝트 화면의 입력으로 바뀐다.
    // 화면이 정해진 뒤에 고른다(사용자도 로딩이 끝난 화면에서 고른다).
    await expect(page.getByText("폴더나 시트를 추가하여 테스트 케이스를 관리하세요.")).toBeVisible();

    const input = page.locator('input[type="file"][accept*=".csv"]').first();
    await input.setInputFiles({ name: "tcs.csv", mimeType: "text/csv", buffer: CSV });
    await expect(page.getByText("1개 가져옴")).toBeVisible({ timeout: 15000 });
    expect(stagings.n).toBe(1);

    // 파일 선택마다 새 File 객체라 업로드 캐시를 타지 않는다. 같은 File 재사용은 upload-reuse.test.ts 가 본다.
    await page.locator('input[type="file"][accept*=".csv"]').first()
      .setInputFiles({ name: "tcs.csv", mimeType: "text/csv", buffer: CSV });
    await expect(page.getByText(/업데이트 1개/)).toBeVisible({ timeout: 15000 });
    expect(stagings.n).toBe(2);

    const tcs = await (await request.get(`/api/projects/${pid}/testcases`, { headers })).json();
    expect(tcs.map((t: { tc_id: string }) => t.tc_id)).toEqual(["UP-1"]);
  });

  test("결과 가져오기(미리보기 뒤 적용)와 이미지 첨부, 첨부 미리보기", async ({ page, request }) => {
    await request.post(`/api/projects/${pid}/testcases/import`, {
      headers, multipart: { file: { name: "t.csv", mimeType: "text/csv", buffer: CSV } },
    });
    const run = await (await request.post(`/api/projects/${pid}/testruns`, { data: { name: "UPRUN" }, headers })).json();

    const stagings = countStagings(page);
    await login(page);
    await page.goto(`/projects/${pid}?tab=run`);
    await page.getByRole("button", { name: "UPRUN" }).first().click();

    // 결과 가져오기: 미리보기(dry run) 뒤 적용
    await page.getByTestId("import-results").click();
    await page.locator("#result-import-file").setInputFiles({ name: "j.xml", mimeType: "text/xml", buffer: JUNIT });
    await page.getByRole("button", { name: "미리보기" }).click();
    await page.getByRole("button", { name: "1건 적용" }).click();
    await expect(page.getByText("결과 1건을 기록했습니다.")).toBeVisible({ timeout: 15000 });
    expect(stagings.n).toBe(1);

    const detail = await (await request.get(`/api/projects/${pid}/testruns/${run.id}`, { headers })).json();
    expect(detail.results[0].result).toBe("PASS");

    // 첨부: 셀의 + 버튼 -> 파일 선택 창
    const chooser = page.waitForEvent("filechooser");
    await page.getByTitle("이미지 첨부").first().click();
    await (await chooser).setFiles({ name: "shot.png", mimeType: "image/png", buffer: PNG });
    await expect(page.getByText("이미지 첨부 완료")).toBeVisible({ timeout: 15000 });
    expect(stagings.n).toBe(2);

    // 첨부 미리보기: img 가 다운로드 주소를 그대로 따라가 실제로 그려진다
    await page.getByTitle("shot.png").click();
    const img = page.locator('img[alt="shot.png"]');
    await expect(img).toBeVisible();
    await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth)).toBe(2);
  });
});
