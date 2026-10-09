import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

// 계정 승인 흐름. CI 의 E2E 백엔드는 AUTH_APPROVAL=personal 이라 이메일 가입은 승인 대기가 된다.
// Google 은 더미 클라이언트 ID 로 켜 두므로 버튼과 시작 주소까지만 본다(실제 Google 로그인은 하지 않는다).

const ADMIN_PW = process.env.TEST_ADMIN_PASSWORD || "test1234";
const PW = "Passw0rd!e2e";

async function adminHeaders(request: APIRequestContext) {
  const res = await request.post("/api/auth/login", { data: { username: "admin", password: ADMIN_PW } });
  const { access_token } = await res.json();
  return { Authorization: `Bearer ${access_token}` };
}

async function findUserId(request: APIRequestContext, headers: Record<string, string>, email: string) {
  const users = await (await request.get("/api/auth/users", { headers })).json();
  const found = users.find((u: { email?: string }) => u.email === email);
  expect(found, `가입한 사용자 ${email} 를 목록에서 찾지 못했다`).toBeTruthy();
  return found.id as number;
}

async function loginAs(page: Page, ident: string, password: string) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디 또는 이메일을 입력하세요").fill(ident);
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(password);
  await page.getByRole("button", { name: "로그인" }).click();
}

test.describe("계정 승인", () => {
  test("이메일 가입은 승인 대기이고, 관리자가 승인하면 로그인된다", async ({ page, request }) => {
    const email = `e2e_pending_${Date.now()}@example.com`;
    await page.goto("/register");
    await page.getByPlaceholder("이메일을 입력하세요").fill(email);
    await page.getByPlaceholder("표시될 이름을 입력하세요").fill("E2E 대기");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill(PW);
    await page.getByPlaceholder("비밀번호를 다시 입력하세요").fill(PW);
    await page.getByRole("button", { name: "회원가입" }).click();
    await expect(page.getByText("가입 신청이 접수됐습니다. 관리자 승인 후 로그인할 수 있습니다.")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);

    await loginAs(page, email, PW);
    await expect(page.getByText("관리자 승인을 기다리는 중입니다.")).toBeVisible();

    const headers = await adminHeaders(request);
    const id = await findUserId(request, headers, email);
    expect((await request.post(`/api/auth/users/${id}/approve`, { headers })).status()).toBe(200);

    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });

  test("사용 중지하면 그 사용자의 다음 화면 이동이 로그인 화면으로 간다", async ({ page, request }) => {
    const email = `e2e_disable_${Date.now()}@example.com`;
    const reg = await request.post("/api/auth/register", { data: { email, password: PW, display_name: "E2E 중지" } });
    expect(reg.status()).toBe(201);
    const headers = await adminHeaders(request);
    const id = (await reg.json()).id as number;
    await request.post(`/api/auth/users/${id}/approve`, { headers });

    await loginAs(page, email, PW);
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });

    expect((await request.post(`/api/auth/users/${id}/disable`, { headers })).status()).toBe(200);
    await page.reload();
    await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  });

  test("Google 로그인 버튼이 보이고 시작 주소는 Google 로 보낸다", async ({ page, request }) => {
    await page.goto("/login");
    await expect(page.getByRole("link", { name: "Google 로 로그인" })).toBeVisible();
    const res = await request.get("/api/auth/google/start", { maxRedirects: 0 });
    expect(res.status()).toBe(302);
    expect(res.headers()["location"]).toContain("accounts.google.com");
  });
});
