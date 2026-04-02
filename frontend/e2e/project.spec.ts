import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill("test1234");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test.describe("프로젝트 관리", () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test("프로젝트 목록 표시", async ({ page }) => {
    await expect(page.getByText("전체 프로젝트")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("전체 TC")).toBeVisible();
    await expect(page.getByText("Pass Rate").first()).toBeVisible();
  });

  test("새 프로젝트 생성 → 삭제", async ({ page }) => {
    const projectName = `E2E_Del_${Date.now()}`;

    // 생성
    await page.getByText("+ 새 프로젝트").click();
    await page.getByPlaceholder("프로젝트 이름").fill(projectName);
    await page.getByRole("button", { name: "생성" }).click();
    await page.waitForTimeout(2000);

    // 프로젝트 카드가 렌더링될 때까지 대기 후 클릭
    const card = page.locator("h3").filter({ hasText: projectName });
    await expect(card).toBeVisible({ timeout: 10000 });
    await card.click();
    await page.waitForTimeout(2000);

    // 설정 탭 → 삭제
    await page.waitForTimeout(2000);
    await page.getByRole("button", { name: "설정" }).click();
    await expect(page.getByText("접근 설정")).toBeVisible({ timeout: 5000 });
    await page.getByRole("button", { name: "프로젝트 삭제" }).click();
    await page.getByPlaceholder(projectName).fill(projectName);
    await page.getByRole("button", { name: "영구 삭제" }).click();

    // 목록으로 복귀
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });

  test("프로젝트 상세 탭 전환", async ({ page }) => {
    test.skip(!!process.env.CI, "CI 환경에서는 기존 프로젝트 필요");
    // 테이블 첫 행 클릭으로 프로젝트 진입
    await page.waitForTimeout(2000);
    const firstRow = page.locator("tr[style*='cursor']").first();
    await firstRow.click();

    // 탭들 확인
    await expect(page.getByRole("button", { name: "TC 관리" })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole("button", { name: "테스트 수행" })).toBeVisible();
    await expect(page.getByRole("button", { name: "대시보드" })).toBeVisible();
    await expect(page.getByRole("button", { name: "리포트" })).toBeVisible();
    await expect(page.getByRole("button", { name: "설정" })).toBeVisible();

    // 대시보드 탭 클릭
    await page.getByRole("button", { name: "대시보드" }).click();
    await expect(page.getByText("테스트 수행:")).toBeVisible({ timeout: 10000 });

    // 리포트 탭 클릭
    await page.getByRole("button", { name: "리포트" }).click();
    await expect(page.getByText("PDF 다운로드")).toBeVisible({ timeout: 10000 });
  });

  test("헤더 네비게이션", async ({ page }) => {
    // YM TestCase 로고 클릭
    await page.getByText("YM TestCase").click();
    await expect(page).toHaveURL(/\/projects/);

    // 도움말
    await page.getByText("도움말").click();
    await expect(page).toHaveURL(/\/manual/);

    // 뒤로
    await page.goBack();

    // 관리
    await page.locator("header button").filter({ hasText: /^관리$/ }).click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByText("사용자 관리")).toBeVisible({ timeout: 5000 });
  });

  test("테마 토글", async ({ page }) => {
    // 다크모드 전환
    const themeBtn = page.getByTitle(/다크 모드|라이트 모드/);
    await themeBtn.click();

    // html data-theme 확인
    const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(theme).toBe("dark");

    // 다시 라이트로
    await themeBtn.click();
    const theme2 = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(theme2).toBe("light");
  });
});
