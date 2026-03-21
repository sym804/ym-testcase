import { test, expect } from "@playwright/test";

test.describe("인증 플로우", () => {
  test("로그인 페이지 렌더링", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "로그인" })).toBeVisible();
    await expect(page.getByPlaceholder("아이디를 입력하세요")).toBeVisible();
    await expect(page.getByPlaceholder("비밀번호를 입력하세요")).toBeVisible();
  });

  test("빈 필드 제출 시 에러 표시", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page.getByText("아이디와 비밀번호를 입력해 주세요.")).toBeVisible();
  });

  test("잘못된 비밀번호로 로그인 실패", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill("wrongpassword");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page.getByText(/올바르지 않습니다|실패/)).toBeVisible({ timeout: 5000 });
  });

  test("정상 로그인 → 프로젝트 목록 이동", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill("test1234");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
    await expect(page.getByText("YM TestCase")).toBeVisible();
  });

  test("비인증 상태에서 /projects 접근 시 /login 리다이렉트", async ({ page }) => {
    await page.goto("/projects");
    await expect(page).toHaveURL(/\/login/);
  });

  test("로그아웃", async ({ page }) => {
    // 로그인
    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill("test1234");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });

    // 사용자 메뉴 → 로그아웃
    // 토스트가 사라질 때까지 대기
    await page.waitForTimeout(3500);
    await page.locator("header button").filter({ hasText: "Admin" }).click();
    await page.getByRole("button", { name: "로그아웃" }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test("회원가입 페이지 이동", async ({ page }) => {
    await page.goto("/login");
    await page.getByText("회원가입").click();
    await expect(page.getByRole("heading", { name: "회원가입" })).toBeVisible();
  });
});
