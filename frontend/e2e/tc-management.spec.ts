import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill("test1234");
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test.describe("TC 관리", () => {
  test("빈 프로젝트 → 시트 추가 → 행 추가 → 삭제까지", async ({ page }) => {
    await login(page);
    const projectName = `E2E_TC_${Date.now()}`;

    // 1. 프로젝트 생성
    await page.getByText("+ 새 프로젝트").click();
    await page.getByPlaceholder("프로젝트 이름").fill(projectName);
    await page.getByRole("button", { name: "생성" }).click();
    await page.waitForTimeout(2000);

    // 2. 프로젝트 진입
    const card = page.locator("h3").filter({ hasText: projectName });
    await expect(card).toBeVisible({ timeout: 10000 });
    await card.click();

    // 3. 빈 프로젝트 시트 추가 화면
    // 페이지 로드 완료 대기
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    const addSheetBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addSheetBtn).toBeVisible({ timeout: 15000 });

    // 4. 시트 추가
    await addSheetBtn.click();
    await page.getByPlaceholder("시트 이름").fill("테스트시트");
    await page.getByRole("button", { name: "추가" }).click();
    await expect(page.getByText("테스트시트").first()).toBeVisible({ timeout: 10000 });

    // 5. 행 추가 (자동저장)
    await page.getByText("+ 행 추가").click();
    await page.waitForTimeout(2000);

    // 6. 저장 버튼 없음 확인
    const saveButtons = page.locator("button").filter({ hasText: /^저장$/ });
    await expect(saveButtons).toHaveCount(0);

    // 7. 정리: 프로젝트 삭제
    await page.getByRole("button", { name: "설정" }).click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: "프로젝트 삭제" }).click();
    await page.getByPlaceholder(projectName).fill(projectName);
    await page.getByRole("button", { name: "영구 삭제" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });

  test("Import 버튼이 빈 프로젝트에 표시됨", async ({ page }) => {
    await login(page);
    const projectName = `E2E_Imp_${Date.now()}`;

    // 프로젝트 생성 + 진입
    await page.getByText("+ 새 프로젝트").click();
    await page.getByPlaceholder("프로젝트 이름").fill(projectName);
    await page.getByRole("button", { name: "생성" }).click();
    await page.waitForTimeout(2000);
    const card = page.locator("h3").filter({ hasText: projectName });
    await expect(card).toBeVisible({ timeout: 10000 });
    await card.click();

    // Import 버튼 확인
    await expect(page.getByText("Import")).toBeVisible({ timeout: 10000 });

    // 정리
    await page.getByRole("button", { name: "설정" }).click();
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: "프로젝트 삭제" }).click();
    await page.getByPlaceholder(projectName).fill(projectName);
    await page.getByRole("button", { name: "영구 삭제" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });
});
