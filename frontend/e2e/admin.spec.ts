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

  test("헤더 검색 입력", async ({ page }) => {
    const searchInput = page.getByPlaceholder("TC 검색...");
    await expect(searchInput).toBeVisible();
    // 1자 입력 → 결과 없음
    await searchInput.fill("a");
    await page.waitForTimeout(500);
    // 검색 드롭다운이 안 보여야 함 (2자 미만)
  });

  test("글로벌 검색 2자 이상", async ({ page }) => {
    const searchInput = page.getByPlaceholder("TC 검색...");
    await searchInput.fill("TC");
    await page.waitForTimeout(500);
    // 검색 결과가 있으면 드롭다운 표시 (TC가 있는 경우)
  });
});
