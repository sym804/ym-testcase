import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

// 일반 사용자(시스템 역할 user)가 프로젝트를 만들고, 시트 트리의 복사 버튼으로 시트를 TC 째 복사한다.
// CI 의 E2E 백엔드는 AUTH_APPROVAL=personal 이라 이메일 가입은 승인 대기가 된다. 관리자가 승인한다.

const ADMIN_PW = process.env.TEST_ADMIN_PASSWORD || "test1234";
const PW = "Passw0rd!e2e";

async function tokenHeaders(request: APIRequestContext, username: string, password: string) {
  const res = await request.post("/api/auth/login", { data: { username, password } });
  expect(res.status(), await res.text()).toBe(200);
  const { access_token } = await res.json();
  return { Authorization: `Bearer ${access_token}` };
}

async function loginAs(page: Page, ident: string, password: string) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디 또는 이메일을 입력하세요").fill(ident);
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(password);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test("일반 사용자가 프로젝트를 만들고 시트를 TC 째 복사한다", async ({ page, request }) => {
  const stamp = Date.now();
  const email = `e2e_copy_${stamp}@example.com`;
  const reg = await request.post("/api/auth/register", { data: { email, password: PW, display_name: "E2E 복사" } });
  expect(reg.status(), await reg.text()).toBe(201);
  const userId = (await reg.json()).id as number;
  const admin = await tokenHeaders(request, "admin", ADMIN_PW);
  // 승인 정책이 꺼진 환경이면 이미 사용 중이라 승인이 거절될 수 있다. 서버 오류만 아니면 된다.
  expect((await request.post(`/api/auth/users/${userId}/approve`, { headers: admin })).status()).toBeLessThan(500);
  const me = await tokenHeaders(request, email, PW);
  expect((await (await request.get("/api/auth/me", { headers: me })).json()).role).toBe("user");

  // 만든 데이터는 실패해도 지운다. 프로젝트를 지우면 계정은 기록 없는 계정이 되어 삭제된다.
  let pid: number | null = null;
  try {
    // 1. 일반 사용자 화면에서 프로젝트 생성
    await loginAs(page, email, PW);
    const projectName = `E2E_COPY_${stamp}`;
    await page.getByText("+ 새 프로젝트").click();
    await page.getByPlaceholder("프로젝트 이름").fill(projectName);
    await page.getByRole("button", { name: "생성" }).click();
    const card = page.locator("h3").filter({ hasText: projectName });
    await expect(card).toBeVisible({ timeout: 10000 });

    // 2. 시트와 TC 는 API 로 준비한다(이 테스트가 보는 것은 복사 버튼)
    const projects = await (await request.get("/api/projects", { headers: me })).json();
    pid = projects.find((p: { name: string }) => p.name === projectName).id as number;
    expect((await request.post(`/api/projects/${pid}/testcases/sheets`, { headers: me, data: { name: "로그인" } })).status()).toBe(200);
    expect((await request.post(`/api/projects/${pid}/testcases/sheets`, { headers: me, data: { name: "결제" } })).status()).toBe(200);
    for (const id of ["LG-1", "LG-2"]) {
      const r = await request.post(`/api/projects/${pid}/testcases`, {
        headers: me, data: { tc_id: id, sheet_name: "로그인", test_steps: `${id} 절차` },
      });
      expect(r.status(), await r.text()).toBe(201);
    }

    // 3. 프로젝트에 들어가 '로그인' 시트를 복사
    await card.click();
    const sheetRow = page.locator("div").filter({ hasText: /^📄로그인2/ }).last();
    await expect(sheetRow).toBeVisible({ timeout: 15000 });
    await sheetRow.getByRole("button", { name: "시트 복사" }).click();

    // 4. 새 시트가 선택되고 복사한 TC 2건이 새 ID 로 보인다
    await expect(page.getByText("\"로그인\" 시트를 \"로그인 (복사)\"(으)로 복사했습니다. (TC 2건)")).toBeVisible({ timeout: 10000 });
    // 토스트에도 같은 글자가 있어 시트 트리 행으로 좁힌다
    await expect(page.locator("div").filter({ hasText: /^📄로그인 \(복사\)2/ }).last()).toBeVisible();
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(2, { timeout: 10000 });
    await expect(page.getByText("LG-1-copy")).toBeVisible();
    await expect(page.getByText("LG-2-copy")).toBeVisible();
    await page.screenshot({ path: test.info().outputPath("sheet-copy.png"), fullPage: false });

    // 원본은 그대로
    const sheets = await (await request.get(`/api/projects/${pid}/testcases/sheets`, { headers: me })).json();
    const byName = Object.fromEntries(sheets.map((s: { name: string; tc_count: number }) => [s.name, s.tc_count]));
    expect(byName).toMatchObject({ "로그인": 2, "로그인 (복사)": 2, "결제": 0 });
  } finally {
    if (pid !== null) await request.delete(`/api/projects/${pid}`, { headers: me });
    await request.delete(`/api/auth/users/${userId}`, { headers: admin });
  }
});
