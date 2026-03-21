/**
 * README용 스크린샷 캡처 (ymseo_test 프로젝트 기반)
 * 실행: npx playwright test e2e/capture-readme.spec.ts --retries=0
 */
import { test, expect, type Page } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename2 = fileURLToPath(import.meta.url);
const __dirname2 = path.dirname(__filename2);
const SAVE_DIR = path.join(__dirname2, "../../docs/screenshots");
const MANUAL_DIR = path.join(__dirname2, "../public/manual-images");
const PASSWORD = process.env.TEST_ADMIN_PASSWORD || "test1234";
const PROJ_ID = 23; // ymseo_test

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test("README + 매뉴얼 스크린샷 (ymseo_test)", async ({ page, request }) => {
  test.setTimeout(180000);
  await page.setViewportSize({ width: 1280, height: 800 });

  // API 토큰
  const loginRes = await request.post("/api/auth/login", {
    data: { username: "admin", password: PASSWORD },
  });
  const { access_token } = await loginRes.json();
  const h = { Authorization: `Bearer ${access_token}` };

  // 테스트 런에 결과 채우기 (대시보드용)
  const runsRes = await request.get(`/api/projects/${PROJ_ID}/testruns`, { headers: h });
  const runs = await runsRes.json();
  let runId = runs[0]?.id;

  // 결과가 비어있으면 새 런 생성 + 결과 채우기
  if (runId) {
    const detailRes = await request.get(`/api/projects/${PROJ_ID}/testruns/${runId}`, { headers: h });
    const detail = await detailRes.json();
    const results = detail.results || [];
    const hasResults = results.some((r: { result: string }) => r.result && r.result !== "N/A");
    if (!hasResults && results.length > 0) {
      const vals = ["PASS", "PASS", "PASS", "PASS", "FAIL", "PASS", "BLOCK", "PASS", "PASS", "PASS"];
      await request.post(`/api/projects/${PROJ_ID}/testruns/${runId}/results`, {
        data: results.map((r: { test_case_id: number }, i: number) => ({
          test_case_id: r.test_case_id,
          result: vals[i % vals.length],
        })),
        headers: h,
      });
    }
  }

  // ========== 캡처 시작 ==========

  // 01. 로그인 페이지
  await page.goto("/login");
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "login.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "01_login_page.png") });

  // 02. 회원가입
  await page.getByText("회원가입").click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(MANUAL_DIR, "02_register_page.png") });

  // 03. 로그인 입력 상태
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill("••••••••");
  await page.screenshot({ path: path.join(MANUAL_DIR, "03_login_filled.png") });

  // 로그인
  await login(page);
  await page.waitForTimeout(2000);

  // 04. 프로젝트 목록
  await page.screenshot({ path: path.join(SAVE_DIR, "project_list.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "04_project_list_overview.png") });

  // 05. 프로젝트 카드 (스크롤)
  await page.evaluate(() => window.scrollTo(0, 600));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(MANUAL_DIR, "05_project_list_cards.png") });
  await page.evaluate(() => window.scrollTo(0, 0));

  // 06. 프로젝트 생성 모달
  const newBtn = page.locator("button").filter({ hasText: "+ 새 프로젝트" }).first();
  if (await newBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await newBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(MANUAL_DIR, "06_project_create_modal.png") });
    await page.locator("div[style*='position: fixed']").first().click({ position: { x: 10, y: 10 } });
    await page.waitForTimeout(500);
  }

  // ymseo_test 프로젝트 진입
  await page.locator("h3").filter({ hasText: "ymseo_test" }).first().click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(3000);

  // 07. TC 관리 탭
  await page.screenshot({ path: path.join(SAVE_DIR, "tc_grid.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "07_project_detail_tc_tab.png") });

  // 19. 글로벌 검색
  const searchInput = page.getByPlaceholder("TC 검색...");
  if (await searchInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await searchInput.fill("TC-AUTH");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(MANUAL_DIR, "19_global_search.png") });
    await searchInput.fill("");
  }

  // 23. TC 툴바
  await page.screenshot({ path: path.join(MANUAL_DIR, "23_tc_toolbar.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "08_tc_grid_detail.png") });

  // 30. 시트 트리
  await page.screenshot({ path: path.join(SAVE_DIR, "sheet_tree.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "30_sheet_tree_tabs.png") });

  // 33. 고급 필터
  const filterBtn = page.locator("button").filter({ hasText: /^필터/ });
  if (await filterBtn.isVisible({ timeout: 2000 })) {
    await filterBtn.click();
    await page.waitForTimeout(300);
    await page.getByText("+ 조건 추가").click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SAVE_DIR, "filter.png") });
    await page.screenshot({ path: path.join(MANUAL_DIR, "33_advanced_filter_panel.png") });
    await page.screenshot({ path: path.join(MANUAL_DIR, "34_tc_toolbar_with_filter.png") });
    await filterBtn.click();
  }

  // 09. 테스트 수행 탭
  await page.getByRole("button", { name: "테스트 수행" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(MANUAL_DIR, "09_testrun_tab.png") });

  // 10~11. 테스트 수행 결과 — 첫 번째 런 클릭
  const runItem = page.getByText("v0.6.0 Full Test").first();
  const runItem2 = page.locator("text=v0.6.0").first();
  const anyRun = (await runItem.isVisible({ timeout: 2000 }).catch(() => false)) ? runItem : runItem2;
  if (await anyRun.isVisible({ timeout: 3000 }).catch(() => false)) {
    await anyRun.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: path.join(SAVE_DIR, "testrun.png") });
    await page.screenshot({ path: path.join(MANUAL_DIR, "10_testrun_results.png") });
    await page.screenshot({ path: path.join(MANUAL_DIR, "11_testrun_grid_detail.png") });
  }

  // 12. 비교 탭
  await page.getByRole("button", { name: "비교" }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(MANUAL_DIR, "12_compare_tab.png") });

  // 13~15. 대시보드
  await page.getByRole("button", { name: "대시보드" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "dashboard.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "13_dashboard_top.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "35_dashboard_with_plan.png") });

  await page.evaluate(() => window.scrollTo(0, 400));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(MANUAL_DIR, "14_dashboard_charts.png") });

  await page.evaluate(() => window.scrollTo(0, 800));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(MANUAL_DIR, "15_dashboard_bottom.png") });
  await page.evaluate(() => window.scrollTo(0, 0));

  // 16. 리포트
  await page.getByRole("button", { name: "리포트" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(MANUAL_DIR, "16_report_tab.png") });

  // 17~18. 설정
  await page.getByRole("button", { name: "설정" }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(MANUAL_DIR, "17_settings_tab.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "32_custom_fields_grid.png") });

  await page.evaluate(() => window.scrollTo(0, 400));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(MANUAL_DIR, "18_settings_members.png") });
  await page.evaluate(() => window.scrollTo(0, 0));

  // 20~21. 다크모드
  const themeBtn = page.getByTitle(/다크 모드|라이트 모드/);
  await themeBtn.click();
  await page.waitForTimeout(500);
  await page.goto("/projects");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(MANUAL_DIR, "20_dark_mode_project.png") });

  await page.locator("h3").filter({ hasText: "ymseo_test" }).first().click();
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: "대시보드" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "dark_mode.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "21_dark_mode_dashboard.png") });

  // 라이트모드 복구
  await themeBtn.click();
  await page.waitForTimeout(500);

  // 22, 25. Admin 페이지
  await page.goto("/admin");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(MANUAL_DIR, "22_admin_page.png") });
  await page.screenshot({ path: path.join(MANUAL_DIR, "25_admin_page_with_reset.png") });
});
