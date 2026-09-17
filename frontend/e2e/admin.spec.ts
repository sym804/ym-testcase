import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill("test1234");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test.describe("관리자 페이지", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("관리 페이지 접근 및 사용자 목록", async ({ page }) => {
    await page.locator("header button").filter({ hasText: /^관리$/ }).click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByRole("heading", { name: "사용자 관리" })).toBeVisible({ timeout: 5000 });
  });

  test("사용자 매뉴얼 페이지", async ({ page }) => {
    await page.getByText("도움말").click();
    await expect(page).toHaveURL(/\/manual/);
    // 매뉴얼 콘텐츠
    await expect(page.getByText("YM TestCase")).toBeVisible();
  });

  test("운영 매뉴얼 페이지", async ({ page }) => {
    await page.getByText("운영 매뉴얼").click();
    await expect(page).toHaveURL(/\/admin-manual/);
  });
});

test.describe("검색 기능", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("검색어가 1자면 드롭다운이 열리지 않는다", async ({ page }) => {
    const searchInput = page.getByPlaceholder("TC 검색...");
    await expect(searchInput).toBeVisible();

    // 1자로는 서버를 부르지 않는다. 부르면 여기서 응답이 잡힌다.
    let called = false;
    page.on("response", (r) => {
      if (r.url().includes("/api/search")) called = true;
    });
    await searchInput.fill("a");
    await expect(page.getByRole("button", { name: /TC-/ })).toHaveCount(0);
    expect(called).toBe(false);
  });

  test("검색어가 2자 이상이면 서버를 부른다", async ({ page }) => {
    const searchInput = page.getByPlaceholder("TC 검색...");
    const searched = page.waitForResponse((r) => r.url().includes("/api/search"));
    await searchInput.fill("TC");
    const res = await searched;
    expect(res.ok()).toBe(true);
  });
});
