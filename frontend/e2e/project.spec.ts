import { test, expect, type Page } from "@playwright/test";
import { projectLink } from "./nav";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디 또는 이메일을 입력하세요").fill("admin");
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
    await expect(page.getByText("활성 TC").first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "진행 중인 수행" })).toBeVisible();
    // 프로젝트가 없으면 표 대신 빈 안내가 나온다(CI 는 빈 DB 에서 시작한다). 영역 제목으로 본다
    await expect(page.getByRole("heading", { name: "프로젝트", exact: true })).toBeVisible();
  });

  // SYM-225: 메인 화면의 진행 중 수행 링크로 그 수행이 열린다
  test("진행 중 수행 링크로 그 수행이 열린다", async ({ page, request }) => {
    const login = await request.post("/api/auth/login", {
      data: { username: "admin", password: process.env.TEST_ADMIN_PASSWORD || "test1234" },
    });
    expect(login.status(), await login.text()).toBe(200);
    const h = { Authorization: `Bearer ${(await login.json()).access_token}` };
    const stamp = Date.now();
    const name = `E2E_OV_${stamp}`;
    const runName = `회귀_${stamp}`;
    const pr = await request.post("/api/projects", { headers: h, data: { name } });
    expect(pr.status(), await pr.text()).toBe(201);
    const pid = (await pr.json()).id as number;
    try {
      expect((await request.post(`/api/projects/${pid}/testcases/sheets`, { headers: h, data: { name: "S" } })).status()).toBe(200);
      for (const id of ["OV-1", "OV-2"]) {
        const r = await request.post(`/api/projects/${pid}/testcases`, { headers: h, data: { tc_id: id, sheet_name: "S", test_steps: "1" } });
        expect(r.status(), await r.text()).toBe(201);
      }
      const rr = await request.post(`/api/projects/${pid}/testruns`, {
        headers: h, data: { name: runName, version: "1.0", environment: "e2e" },
      });
      expect(rr.status(), await rr.text()).toBe(201);

      await page.reload();
      const link = page.getByRole("table", { name: "진행 중인 수행" }).getByRole("link", { name: `${runName} · 1회차` });
      await expect(link).toBeVisible({ timeout: 10000 });
      const row = page.getByRole("table", { name: "프로젝트" }).getByRole("row").filter({ hasText: name });
      await expect(row).toContainText(`${runName} · 1회차`);

      await link.click();
      // 수행을 연 뒤 주소의 run 은 지운다(새로고침 때 다시 열지 않게)
      await expect(page).toHaveURL(new RegExp(`/projects/${pid}\\?tab=run$`), { timeout: 10000 });
      // 수행을 열었을 때만 보이는 머리글(버전 · 환경)
      await expect(page.getByText(/버전: 1\.0 \| 환경: e2e/)).toBeVisible({ timeout: 10000 });
    } finally {
      // 정리가 실패하면 다음 실행에 프로젝트가 남는다
      const del = await request.delete(`/api/projects/${pid}`, { headers: h });
      expect(del.status(), await del.text()).toBeLessThan(300);
    }
  });

  test("새 프로젝트 생성 → 삭제", async ({ page }) => {
    const projectName = `E2E_Del_${Date.now()}`;

    // 생성
    await page.getByText("+ 새 프로젝트").click();
    await page.getByPlaceholder("프로젝트 이름").fill(projectName);
    await page.getByRole("button", { name: "생성" }).click();

    // 프로젝트 카드가 렌더링될 때까지 대기 후 클릭
    const card = projectLink(page, projectName);
    await expect(card).toBeVisible({ timeout: 10000 });
    await card.click();

    // 설정 탭 → 삭제
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
