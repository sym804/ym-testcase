/**
 * 매뉴얼 스크린샷 전체 재캡처
 * 실행: npx playwright test e2e/capture-all-manual.spec.ts --retries=0
 */
import { test, expect, type Page } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename2 = fileURLToPath(import.meta.url);
const __dirname2 = path.dirname(__filename2);
const SAVE_DIR = path.join(__dirname2, "../public/manual-images");
const PASSWORD = process.env.TEST_ADMIN_PASSWORD || "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test("전체 매뉴얼 스크린샷 재캡처", async ({ page, request }) => {
  test.setTimeout(120000);
  await page.setViewportSize({ width: 1280, height: 800 });

  // API 세팅
  const loginRes = await request.post("/api/auth/login", {
    data: { username: "admin", password: PASSWORD },
  });
  const { access_token } = await loginRes.json();
  const h = { Authorization: `Bearer ${access_token}` };

  // 캡처용 프로젝트 생성
  const projRes = await request.post("/api/projects", {
    data: { name: `MC_Screenshot_${Date.now()}`, description: "매뉴얼 스크린샷을 위한 샘플 프로젝트" },
    headers: h,
  });
  const projId = (await projRes.json()).id;

  // 시트 트리 생성
  const sheet1 = await request.post(`/api/projects/${projId}/testcases/sheets`, { data: { name: "기능 테스트" }, headers: h });
  const sheet1Id = (await sheet1.json()).id;
  await request.post(`/api/projects/${projId}/testcases/sheets`, { data: { name: "로그인", parent_id: sheet1Id }, headers: h });
  await request.post(`/api/projects/${projId}/testcases/sheets`, { data: { name: "결제", parent_id: sheet1Id }, headers: h });
  await request.post(`/api/projects/${projId}/testcases/sheets`, { data: { name: "UI 테스트" }, headers: h });

  // 커스텀 필드
  await request.post(`/api/projects/${projId}/custom-fields`, {
    data: { field_name: "환경", field_type: "select", options: ["Dev", "QA", "Staging", "Prod"] }, headers: h,
  });
  await request.post(`/api/projects/${projId}/custom-fields`, {
    data: { field_name: "자동화", field_type: "checkbox" }, headers: h,
  });

  // TC 추가
  const tcs = [
    { no: 1, tc_id: "TC-LOGIN-001", type: "Func.", category: "인증", depth1: "로그인", depth2: "이메일 로그인", priority: "높음", test_steps: "1. 로그인 페이지 접속\n2. 이메일/비밀번호 입력", expected_result: "메인 페이지로 이동", sheet_name: "로그인", custom_fields: { "환경": "QA", "자동화": true } },
    { no: 2, tc_id: "TC-LOGIN-002", type: "Func.", category: "인증", depth1: "로그인", depth2: "소셜 로그인", priority: "보통", sheet_name: "로그인" },
    { no: 3, tc_id: "TC-PAY-001", type: "Func.", category: "결제", depth1: "결제", depth2: "카드 결제", priority: "높음", sheet_name: "결제" },
    { no: 4, tc_id: "TC-PAY-002", type: "Func.", category: "결제", depth1: "결제", depth2: "무통장", priority: "보통", sheet_name: "결제" },
    { no: 5, tc_id: "TC-UI-001", type: "UI/UX", category: "화면", depth1: "메인", depth2: "반응형", priority: "낮음", sheet_name: "UI 테스트" },
    { no: 6, tc_id: "TC-UI-002", type: "UI/UX", category: "화면", depth1: "메인", depth2: "다크모드", priority: "보통", sheet_name: "UI 테스트" },
  ];
  for (const tc of tcs) {
    await request.post(`/api/projects/${projId}/testcases`, { data: tc, headers: h });
  }

  // TestRun + 결과
  const runRes = await request.post(`/api/projects/${projId}/testruns`, {
    data: { name: "R1 스모크 테스트", version: "v1.0" }, headers: h,
  });
  const runId = (await runRes.json()).id;
  const detailRes = await request.get(`/api/projects/${projId}/testruns/${runId}`, { headers: h });
  const runResults = (await detailRes.json()).results || [];
  const vals = ["PASS", "PASS", "FAIL", "PASS", "BLOCK", "PASS"];
  if (runResults.length > 0) {
    await request.post(`/api/projects/${projId}/testruns/${runId}/results`, {
      data: runResults.map((r: { test_case_id: number }, i: number) => ({
        test_case_id: r.test_case_id, result: vals[i % vals.length],
      })), headers: h,
    });
  }

  // 필터 저장
  await request.post(`/api/projects/${projId}/filters`, {
    data: { name: "높은 우선순위", conditions: [{ field: "priority", operator: "eq", value: "높음" }], logic: "AND" },
    headers: h,
  });

  // ========== 캡처 시작 ==========

  // 01. 로그인 페이지
  await page.goto("/login");
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "01_login_page.png") });

  // 02. 회원가입 페이지
  await page.getByText("회원가입").click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "02_register_page.png") });

  // 03. 로그인 (입력 상태)
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill("••••••••");
  await page.screenshot({ path: path.join(SAVE_DIR, "03_login_filled.png") });

  // 로그인 실행
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  await page.waitForTimeout(2000);

  // 04. 프로젝트 목록 - 전체 현황
  await page.screenshot({ path: path.join(SAVE_DIR, "04_project_list_overview.png") });

  // 05. 프로젝트 카드 (스크롤 다운)
  await page.evaluate(() => window.scrollTo(0, 600));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "05_project_list_cards.png") });
  await page.evaluate(() => window.scrollTo(0, 0));

  // 06. 프로젝트 생성 모달
  const newBtn = page.locator("button").filter({ hasText: "+ 새 프로젝트" }).first();
  if (await newBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await newBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SAVE_DIR, "06_project_create_modal.png") });
    // 모달 닫기: overlay 클릭
    await page.locator("div[style*='position: fixed']").first().click({ position: { x: 10, y: 10 } });
    await page.waitForTimeout(500);
  }

  // 프로젝트 진입
  await page.locator("h3").filter({ hasText: /MC_Screenshot/ }).first().click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(3000);

  // 07. 프로젝트 상세 - TC 탭
  await page.screenshot({ path: path.join(SAVE_DIR, "07_project_detail_tc_tab.png") });

  // 19. 글로벌 검색
  const searchInput = page.getByPlaceholder("TC 검색...");
  if (await searchInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await searchInput.fill("TC-LOGIN");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SAVE_DIR, "19_global_search.png") });
    await searchInput.fill("");
  }

  // 23. TC 툴바
  await page.screenshot({ path: path.join(SAVE_DIR, "23_tc_toolbar.png") });

  // 08. TC 그리드 상세
  await page.screenshot({ path: path.join(SAVE_DIR, "08_tc_grid_detail.png") });

  // 30. 시트 사이드바 트리 (펼침)
  const folderIcon = page.locator("text=📁").first();
  if (await folderIcon.isVisible({ timeout: 2000 }).catch(() => false)) {
    await folderIcon.click();
    await page.waitForTimeout(500);
  }
  await page.screenshot({ path: path.join(SAVE_DIR, "30_sheet_tree_tabs.png") });

  // 31. 하위 시트 추가
  const addChildBtn = page.locator("[title*='하위 시트 추가']").first();
  if (await addChildBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await addChildBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SAVE_DIR, "31_sheet_tree_add_child.png") });
    await page.keyboard.press("Escape");
  }

  // 33. 고급 필터 패널
  const filterBtn = page.locator("button").filter({ hasText: /^필터/ });
  if (await filterBtn.isVisible({ timeout: 2000 })) {
    await filterBtn.click();
    await page.waitForTimeout(300);
    await page.getByText("+ 조건 추가").click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SAVE_DIR, "33_advanced_filter_panel.png") });
    await filterBtn.click(); // 닫기
  }

  // 34. TC 툴바 (필터 포함)
  await page.screenshot({ path: path.join(SAVE_DIR, "34_tc_toolbar_with_filter.png") });

  // 09. 테스트 수행 탭
  await page.getByRole("button", { name: "테스트 수행" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "09_testrun_tab.png") });

  // 10. 테스트 수행 결과 (런 클릭)
  const runItem = page.locator("text=R1 스모크 테스트").first();
  if (await runItem.isVisible({ timeout: 3000 }).catch(() => false)) {
    await runItem.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SAVE_DIR, "10_testrun_results.png") });
    await page.screenshot({ path: path.join(SAVE_DIR, "11_testrun_grid_detail.png") });
  }

  // 12. 비교 탭
  await page.getByRole("button", { name: "비교" }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SAVE_DIR, "12_compare_tab.png") });

  // 13~15. 대시보드
  await page.getByRole("button", { name: "대시보드" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "13_dashboard_top.png") });
  await page.screenshot({ path: path.join(SAVE_DIR, "35_dashboard_with_plan.png") });

  await page.evaluate(() => window.scrollTo(0, 400));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "14_dashboard_charts.png") });

  await page.evaluate(() => window.scrollTo(0, 800));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "15_dashboard_bottom.png") });
  await page.evaluate(() => window.scrollTo(0, 0));

  // 16. 리포트
  await page.getByRole("button", { name: "리포트" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "16_report_tab.png") });

  // 17~18. 설정
  await page.getByRole("button", { name: "설정" }).click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(SAVE_DIR, "17_settings_tab.png") });

  // 32. 커스텀 필드 설정 UI
  await page.screenshot({ path: path.join(SAVE_DIR, "32_custom_fields_grid.png") });

  await page.evaluate(() => window.scrollTo(0, 400));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SAVE_DIR, "18_settings_members.png") });
  await page.evaluate(() => window.scrollTo(0, 0));

  // 20~21. 다크모드
  const themeBtn = page.getByTitle(/다크 모드|라이트 모드/);
  await themeBtn.click();
  await page.waitForTimeout(500);
  await page.goto(`/projects`);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "20_dark_mode_project.png") });

  // 다크모드 대시보드
  await page.locator("h3").filter({ hasText: /MC_Screenshot/ }).first().click();
  await page.waitForTimeout(2000);
  await page.getByRole("button", { name: "대시보드" }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "21_dark_mode_dashboard.png") });

  // 라이트모드 복구
  await themeBtn.click();
  await page.waitForTimeout(500);

  // 22. Admin 페이지 (사용자 관리)
  await page.goto("/admin");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SAVE_DIR, "22_admin_page.png") });

  // 25. Admin 페이지 (비밀번호 초기화 버튼 포함)
  await page.screenshot({ path: path.join(SAVE_DIR, "25_admin_page_with_reset.png") });

  // 정리
  await request.delete(`/api/projects/${projId}`, { headers: h });
});
