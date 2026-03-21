/**
 * v0.6.0 매뉴얼 스크린샷 캡처
 * 실행: npx playwright test e2e/capture-manual-images.spec.ts
 */
import { test, expect, type Page } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SAVE_DIR = path.join(__dirname, "../public/manual-images");
const PASSWORD = process.env.TEST_ADMIN_PASSWORD || "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

async function createProject(page: Page, name: string) {
  await page.getByText("+ 새 프로젝트").click();
  await page.getByPlaceholder("프로젝트 이름").fill(name);
  await page.getByRole("button", { name: "생성" }).click();
  await page.waitForTimeout(2000);
  await page.locator("h3").filter({ hasText: name }).click();
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(2000);
}

async function deleteProject(page: Page, name: string) {
  await page.getByRole("button", { name: "설정" }).click();
  await page.waitForTimeout(1000);
  await page.getByRole("button", { name: "프로젝트 삭제" }).click();
  await page.getByPlaceholder(name).fill(name);
  await page.getByRole("button", { name: "영구 삭제" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

test.describe("매뉴얼 스크린샷 캡처", () => {
  test("v0.6.0 기능 스크린샷", async ({ page, request }) => {
    // 뷰포트 설정
    await page.setViewportSize({ width: 1280, height: 800 });

    // API로 테스트 데이터 세팅
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    // 캡처용 프로젝트 생성
    const projRes = await request.post("/api/projects", {
      data: { name: "매뉴얼 캡처용 프로젝트" },
      headers: h,
    });
    const projId = (await projRes.json()).id;

    // 커스텀 필드 추가
    await request.post(`/api/projects/${projId}/custom-fields`, {
      data: { field_name: "환경", field_type: "select", options: ["Dev", "QA", "Staging", "Prod"] },
      headers: h,
    });
    await request.post(`/api/projects/${projId}/custom-fields`, {
      data: { field_name: "자동화 여부", field_type: "checkbox" },
      headers: h,
    });
    await request.post(`/api/projects/${projId}/custom-fields`, {
      data: { field_name: "예상 시간(분)", field_type: "number" },
      headers: h,
    });

    // 시트 트리 구조 생성
    const sheet1 = await request.post(`/api/projects/${projId}/testcases/sheets`, {
      data: { name: "기능 테스트" },
      headers: h,
    });
    const sheet1Id = (await sheet1.json()).id;

    await request.post(`/api/projects/${projId}/testcases/sheets`, {
      data: { name: "로그인", parent_id: sheet1Id },
      headers: h,
    });
    await request.post(`/api/projects/${projId}/testcases/sheets`, {
      data: { name: "결제", parent_id: sheet1Id },
      headers: h,
    });
    await request.post(`/api/projects/${projId}/testcases/sheets`, {
      data: { name: "UI 테스트" },
      headers: h,
    });

    // TC 추가 (시트별)
    const tcs = [
      { no: 1, tc_id: "TC-LOGIN-001", type: "Func.", category: "인증", depth1: "로그인", depth2: "이메일 로그인", priority: "높음", test_steps: "1. 로그인 페이지 접속\n2. 이메일/비밀번호 입력\n3. 로그인 클릭", expected_result: "메인 페이지로 이동", sheet_name: "로그인", custom_fields: { "환경": "QA", "자동화 여부": true, "예상 시간(분)": 15 } },
      { no: 2, tc_id: "TC-LOGIN-002", type: "Func.", category: "인증", depth1: "로그인", depth2: "소셜 로그인", priority: "보통", sheet_name: "로그인", custom_fields: { "환경": "Dev" } },
      { no: 3, tc_id: "TC-PAY-001", type: "Func.", category: "결제", depth1: "결제", depth2: "카드 결제", priority: "높음", sheet_name: "결제" },
      { no: 4, tc_id: "TC-PAY-002", type: "Func.", category: "결제", depth1: "결제", depth2: "계좌이체", priority: "보통", sheet_name: "결제" },
      { no: 5, tc_id: "TC-UI-001", type: "UI/UX", category: "화면", depth1: "메인", depth2: "반응형", priority: "낮음", sheet_name: "UI 테스트" },
    ];
    for (const tc of tcs) {
      await request.post(`/api/projects/${projId}/testcases`, { data: tc, headers: h });
    }

    // 테스트 플랜 생성
    const planRes = await request.post(`/api/projects/${projId}/testplans`, {
      data: { name: "v2.0 Release", milestone: "Sprint 5", description: "2차 릴리즈 전체 테스트" },
      headers: h,
    });
    const planId = (await planRes.json()).id;

    // TestRun 연결
    const runRes = await request.post(`/api/projects/${projId}/testruns`, {
      data: { name: "Release Run 1", version: "v2.0", test_plan_id: planId },
      headers: h,
    });
    const runId = (await runRes.json()).id;

    // 결과 제출
    const detailRes = await request.get(`/api/projects/${projId}/testruns/${runId}`, { headers: h });
    const detailData = await detailRes.json();
    const runResults = detailData.results || [];
    const resultValues = ["PASS", "PASS", "FAIL", "PASS", "BLOCK"];
    if (runResults.length > 0) {
      await request.post(`/api/projects/${projId}/testruns/${runId}/results`, {
        data: runResults.map((r: { test_case_id: number }, i: number) => ({
          test_case_id: r.test_case_id,
          result: resultValues[i % resultValues.length],
        })),
        headers: h,
      });
    }

    // 필터 저장
    await request.post(`/api/projects/${projId}/filters`, {
      data: {
        name: "높은 우선순위",
        conditions: [{ field: "priority", operator: "eq", value: "높음" }],
        logic: "AND",
      },
      headers: h,
    });

    // ====== 브라우저에서 캡처 시작 ======
    await login(page);
    await page.waitForTimeout(1000);

    // 프로젝트 진입
    await page.locator("h3").filter({ hasText: "매뉴얼 캡처용 프로젝트" }).click();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // --- 15. 시트 사이드바 트리 ---
    // 사이드바에서 폴더 펼침 (📁 → 📂)
    const folderIcon = page.locator("text=📁").first();
    if (await folderIcon.isVisible({ timeout: 3000 }).catch(() => false)) {
      await folderIcon.click();
      await page.waitForTimeout(500);
    }

    // 사이드바 트리 캡처
    await page.screenshot({
      path: path.join(SAVE_DIR, "30_sheet_tree_tabs.png"),
      fullPage: false,
    });

    // 하위 시트 추가 모드 캡처 (인라인 + 버튼)
    const addChildBtn = page.locator("[title*='하위']").first().or(
      page.locator("button").filter({ hasText: "+" }).first()
    );
    if (await addChildBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await addChildBtn.click();
      await page.waitForTimeout(500);
      await page.screenshot({
        path: path.join(SAVE_DIR, "31_sheet_tree_add_child.png"),
        fullPage: false,
      });
      // 취소
      await page.keyboard.press("Escape");
    }

    // --- 16. 커스텀 필드 (설정 탭 UI) ---
    // 설정 탭으로 이동
    await page.getByRole("button", { name: "설정" }).click();
    await page.waitForTimeout(1000);

    // 커스텀 필드 섹션 캡처
    await page.screenshot({
      path: path.join(SAVE_DIR, "32_custom_fields_grid.png"),
      fullPage: false,
    });

    // TC 관리 탭으로 복귀
    await page.getByRole("button", { name: "TC 관리" }).click();
    await page.waitForTimeout(1000);

    // --- 19. 고급 필터 ---
    // 필터 버튼 클릭
    const filterBtn = page.locator("button").filter({ hasText: /^필터/ });
    if (await filterBtn.isVisible({ timeout: 3000 })) {
      await filterBtn.click();
      await page.waitForTimeout(500);

      // 조건 추가
      await page.getByText("+ 조건 추가").click();
      await page.waitForTimeout(300);
      await page.getByText("+ 조건 추가").click();
      await page.waitForTimeout(300);

      await page.screenshot({
        path: path.join(SAVE_DIR, "33_advanced_filter_panel.png"),
        fullPage: false,
      });

      // 필터 닫기
      await filterBtn.click();
    }

    // --- 18. CSV Import ---
    // file input의 accept 확인 캡처는 UI에서 직접 안 보이므로 툴바 캡처
    await page.screenshot({
      path: path.join(SAVE_DIR, "34_tc_toolbar_with_filter.png"),
      fullPage: false,
    });

    // --- 대시보드로 이동 (테스트 플랜 progress 참고용) ---
    await page.getByRole("button", { name: "대시보드" }).click();
    await page.waitForTimeout(2000);
    await page.screenshot({
      path: path.join(SAVE_DIR, "35_dashboard_with_plan.png"),
      fullPage: false,
    });

    // 정리
    await request.delete(`/api/projects/${projId}`, { headers: h });
  });
});
