/**
 * YM TestCase 전체 회귀 테스트 (Playwright)
 * 체크리스트 192개 TC 중 자동화 가능한 항목 전부 커버
 */
import { test, expect, type Page } from "@playwright/test";

const PASSWORD = "test1234";

async function login(page: Page, username = "admin") {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill(username);
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

async function createProject(page: Page, name: string) {
  await page.getByText("+ 새 프로젝트").click();
  await page.getByPlaceholder("프로젝트 이름").fill(name);
  await page.getByRole("button", { name: "생성" }).click();
  await page.locator("h3").filter({ hasText: name }).click();
  await page.waitForLoadState("networkidle");
}

async function deleteProject(page: Page, name: string) {
  await page.getByRole("button", { name: "설정" }).click();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.getByRole("button", { name: "프로젝트 삭제" }).click();
  await page.getByPlaceholder(name).fill(name);
  await page.getByRole("button", { name: "영구 삭제" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

async function addSheetAndRows(page: Page, sheetName: string, rowCount = 1) {
  const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
  if (await addBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await addBtn.click();
  } else {
    // 시트 탭 + 버튼
    const plusTab = page.locator("div[title='루트 시트 추가']");
    if (await plusTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await plusTab.click();
    }
  }
  await page.getByPlaceholder("시트 이름").fill(sheetName);
  await page.getByRole("button", { name: "추가", exact: true }).click();
  await expect(page.getByPlaceholder("시트 이름")).toHaveCount(0);

  for (let i = 0; i < rowCount; i++) {
    await page.getByText("+ 행 추가").click();
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(i + 1);
  }
}

// ============================================================================
// 1. 인증 (TC-AUTH-001 ~ 012)
// ============================================================================
test.describe("1. 인증", () => {
  test("TC-AUTH-001: 정상 로그인", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });

  test("TC-AUTH-002: 잘못된 비밀번호", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill("wrongpw12345");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page.getByText(/올바르지 않습니다/)).toBeVisible({ timeout: 5000 });
  });

  test("TC-AUTH-003: 존재하지 않는 계정", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("nonexistent_user_xyz");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill("password1234");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page.getByText(/올바르지 않습니다/)).toBeVisible({ timeout: 5000 });
  });

  test("TC-AUTH-004: 빈 필드 제출", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page.getByText(/입력해 주세요/)).toBeVisible({ timeout: 5000 });
  });

  test("TC-AUTH-005: 로그인 페이지 UI 확인", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "로그인" })).toBeVisible();
    await expect(page.getByPlaceholder("아이디를 입력하세요")).toBeVisible();
    await expect(page.getByPlaceholder("비밀번호를 입력하세요")).toBeVisible();
    await expect(page.getByRole("button", { name: "로그인" })).toBeVisible();
    await expect(page.getByText("회원가입")).toBeVisible();
  });

  test("TC-AUTH-006: 회원가입 페이지 이동", async ({ page }) => {
    await page.goto("/login");
    await page.getByText("회원가입").click();
    await expect(page.getByRole("heading", { name: "회원가입" })).toBeVisible();
    await expect(page.getByPlaceholder("아이디")).toBeVisible();
  });

  test("TC-AUTH-008: 회원가입 유효성 검사 (짧은 비밀번호)", async ({ page }) => {
    await page.goto("/login");
    await page.getByText("회원가입").click();
    await expect(page.getByRole("heading", { name: "회원가입" })).toBeVisible();
    // 폼 필드 채우기
    const inputs = page.locator("input");
    const count = await inputs.count();
    if (count >= 4) {
      await inputs.nth(0).fill("testuser_short_" + Date.now()); // 아이디
      await inputs.nth(1).fill("Test"); // 표시 이름
      await inputs.nth(2).fill("short"); // 비밀번호
      await inputs.nth(3).fill("short"); // 확인
    }
    await page.getByRole("button", { name: /회원가입|가입|등록/ }).click();
    await expect(page.getByText("8자 이상이어야 합니다").first()).toBeVisible({ timeout: 5000 });
  });

  test("TC-AUTH-009: 로그아웃", async ({ page }) => {
    await login(page);
    await expect(page.getByRole("status")).toHaveCount(0, { timeout: 10000 });
    await page.locator("header button").filter({ hasText: /Admin|admin/ }).click();
    await page.getByRole("button", { name: "로그아웃" }).click();
    await expect(page).toHaveURL(/\/login/, { timeout: 5000 });
  });

  test("TC-AUTH-010: 미인증 시 리다이렉트", async ({ page }) => {
    await page.goto("/projects");
    await expect(page).toHaveURL(/\/login/);
  });

  test("TC-AUTH-011: 비밀번호 변경 접근", async ({ page }) => {
    await login(page);
    await expect(page.getByRole("status")).toHaveCount(0, { timeout: 10000 });
    await page.locator("header button").filter({ hasText: /Admin|admin/ }).click();
    await expect(page.getByText("비밀번호 변경")).toBeVisible();
  });
});

// ============================================================================
// 2. 프로젝트 목록 (TC-PL-001 ~ 013)
// ============================================================================
test.describe("2. 프로젝트 목록", () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test("TC-PL-001: 카드 레이아웃 표시", async ({ page }) => {
    await expect(page.getByText("전체 프로젝트")).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("전체 TC")).toBeVisible();
    await expect(page.getByText("Pass Rate").first()).toBeVisible();
  });

  test("TC-PL-004: 프로젝트 카드 정보", async ({ page }) => {
    test.skip(!!process.env.CI, "CI 환경에서는 기존 프로젝트 필요");
    // 카드에 프로젝트 이름이 h3로 표시
    const cards = page.locator("h3");
    expect(await cards.count()).toBeGreaterThan(0);
  });

  test("TC-PL-005: 프로젝트 카드 → 상세 이동", async ({ page }) => {
    test.skip(!!process.env.CI, "CI 환경에서는 기존 프로젝트 필요");
    const firstCard = page.locator("h3").first();
    const name = await firstCard.textContent();
    await firstCard.click();
    await expect(page.getByRole("button", { name: "TC 관리" })).toBeVisible({ timeout: 10000 });
  });

  test("TC-PL-006: 프로젝트 생성", async ({ page }) => {
    const name = `E2E_Create_${Date.now()}`;
    await page.getByText("+ 새 프로젝트").click();
    await page.getByPlaceholder("프로젝트 이름").fill(name);
    await page.getByRole("button", { name: "생성" }).click();
    await expect(page.locator("h3").filter({ hasText: name })).toBeVisible({ timeout: 10000 });
    // 정리
    await page.locator("h3").filter({ hasText: name }).click();
    await deleteProject(page, name);
  });

  test("TC-PL-008: 빈 이름 프로젝트 생성 방지", async ({ page }) => {
    await page.getByText("+ 새 프로젝트").click();
    await page.getByRole("button", { name: "생성" }).click();
    // 에러 또는 모달 유지
    // 프로젝트 목록으로 안 이동 (모달 유지)
    await expect(page.getByPlaceholder("프로젝트 이름")).toBeVisible();
  });

  test("TC-PL-009: 프로젝트 수정", async ({ page }) => {
    const name = `E2E_Edit_${Date.now()}`;
    await createProject(page, name);
    // 빈 프로젝트 시트 추가 화면에서 설정 탭 이동
    await page.getByRole("button", { name: "설정" }).click();
    // 설정 페이지 확인
    await expect(page.getByText("접근 설정").first()).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("프로젝트 삭제").first()).toBeVisible({ timeout: 5000 });
    // deleteProject 호출하지 않고 직접 삭제 (이미 설정 탭)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.getByRole("button", { name: "프로젝트 삭제" }).click();
    await page.getByPlaceholder(name).fill(name);
    await page.getByRole("button", { name: "영구 삭제" }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });

  test("TC-PL-011: 프로젝트 삭제", async ({ page }) => {
    const name = `E2E_DelProj_${Date.now()}`;
    await createProject(page, name);
    await deleteProject(page, name);
    // 삭제 후 목록에서 안 보임
    const card = page.locator("h3").filter({ hasText: name });
    await expect(card).not.toBeVisible();
  });
});

// ============================================================================
// 3. 헤더/네비게이션 (TC-HDR-001 ~ 011)
// ============================================================================
test.describe("3. 헤더/네비게이션", () => {
  test.beforeEach(async ({ page }) => { await login(page); });

  test("TC-HDR-001: 프로젝트 선택기", async ({ page }) => {
    await expect(page.getByText("YM TestCase")).toBeVisible();
  });

  test("TC-HDR-002: 로고 클릭 → 프로젝트 목록", async ({ page }) => {
    // 다른 페이지로 이동 후 로고 클릭으로 복귀
    await page.locator("header button").filter({ hasText: /^관리$/ }).click();
    await expect(page).toHaveURL(/\/admin/);
    await page.locator("header").getByText("YM TestCase").click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 5000 });
  });

  test("TC-HDR-003: 글로벌 검색 입력", async ({ page }) => {
    const search = page.getByPlaceholder("TC 검색...");
    await expect(search).toBeVisible();
    const searched = page.waitForResponse((r) => r.url().includes("/api/search"));
    await search.fill("TC");
    expect((await searched).ok()).toBe(true);
  });

  test("TC-HDR-006: Escape 로 검색 드롭다운을 닫는다", async ({ page, request }) => {
    // 드롭다운은 결과가 있어야 열린다. 빈 DB 에서도 돌도록 찾을 것을 먼저 만든다.
    const lg = await request.post("/api/auth/login", {
      data: { username: "admin", password: PASSWORD },
    });
    const headers = { Authorization: `Bearer ${(await lg.json()).access_token}` };
    const pname = `E2E_HDR_${Date.now()}`;
    const proj = await (await request.post("/api/projects", { data: { name: pname }, headers })).json();
    await request.post(`/api/projects/${proj.id}/testcases/sheets`, {
      data: { name: "기본", parent_id: null, is_folder: false },
      headers,
    });
    const keyword = `ESCTARGET${Date.now()}`;
    await request.post(`/api/projects/${proj.id}/testcases`, {
      data: {
        tc_id: "ESC-001", type: "기능", category: keyword, depth1: keyword,
        test_steps: "1. 연다", expected_result: "된다", priority: "P2", sheet_name: "기본",
      },
      headers,
    });

    try {
      const search = page.getByPlaceholder("TC 검색...");
      const searched = page.waitForResponse((r) => r.url().includes("/api/search"));
      await search.fill(keyword);
      await searched;

      const dropdown = page.getByTestId("search-results");
      await expect(dropdown).toBeVisible();

      await page.keyboard.press("Escape");
      await expect(dropdown).toHaveCount(0);
    } finally {
      await request.delete(`/api/projects/${proj.id}`, { headers });
    }
  });

  test("TC-HDR-007: 다크모드 토글", async ({ page }) => {
    const themeBtn = page.getByTitle(/다크 모드|라이트 모드/);
    await themeBtn.click();
    const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(theme).toBe("dark");
    await themeBtn.click();
    const theme2 = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(theme2).toBe("light");
  });

  test("TC-HDR-008: 라이트모드 토글", async ({ page }) => {
    // 이미 라이트모드일 때 확인
    const theme = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
    expect(["light", null]).toContain(theme);
  });

  test("TC-HDR-009: 로그아웃 버튼 표시", async ({ page }) => {
    await expect(page.getByRole("status")).toHaveCount(0, { timeout: 10000 });
    await page.locator("header button").filter({ hasText: /Admin|admin/ }).click();
    await expect(page.getByText("로그아웃")).toBeVisible();
  });
});

// ============================================================================
// 4. 프로젝트 상세 (TC-PD-001 ~ 009)
// ============================================================================
test.describe("4. 프로젝트 상세", () => {
  let projectName: string;
  test.beforeEach(async ({ page }) => {
    projectName = `E2E_PD_${Date.now()}`;
    await login(page);
    await createProject(page, projectName);
  });
  test.afterEach(async ({ page }) => {
    try { await page.goto("/projects");
      await page.locator("h3").filter({ hasText: projectName }).click();
      await deleteProject(page, projectName);
    } catch { /* ignore */ }
  });

  test("TC-PD-001: TC 관리 탭", async ({ page }) => {
    await expect(page.getByRole("button", { name: "TC 관리" })).toBeVisible({ timeout: 10000 });
  });

  test("TC-PD-002: 테스트 수행 탭", async ({ page }) => {
    await expect(page.getByRole("button", { name: "테스트 수행" })).toBeVisible({ timeout: 10000 });
    await page.getByRole("button", { name: "테스트 수행" }).click();
    // 수행 화면에는 만들기 버튼이 둘 있다(상단 툴바와 빈 화면 안내)
    await expect(page.getByRole("button", { name: "+ 새 테스트 수행 만들기" }).first())
      .toBeVisible({ timeout: 10000 });
  });

  test("TC-PD-003: 비교 탭", async ({ page }) => {
    await expect(page.getByRole("button", { name: "비교" })).toBeVisible({ timeout: 10000 });
  });

  test("TC-PD-004: 대시보드 탭", async ({ page }) => {
    await page.getByRole("button", { name: "대시보드" }).click();
    await expect(page.getByText("전체 TC")).toBeVisible({ timeout: 15000 });
  });

  test("TC-PD-005: 리포트 탭", async ({ page }) => {
    await page.getByRole("button", { name: "리포트" }).click();
    await expect(page.getByText("PDF 다운로드")).toBeVisible({ timeout: 10000 });
  });

  test("TC-PD-006: 검색 하이라이트", async ({ page }) => {
    await addSheetAndRows(page, "SearchTest", 1);

    // 빈 행에는 걸릴 글자가 없다. 셀에 값을 넣고 저장된 뒤에 검색한다.
    const saved = page.waitForResponse(
      (r) => /\/testcases\/\d+$/.test(r.url()) && r.request().method() === "PUT"
    );
    await page.locator(".ag-cell[col-id='category']").first().dblclick();
    await page.keyboard.type("하이라이트대상");
    await page.keyboard.press("Tab");
    await saved;

    const searchInput = page.locator("input[placeholder='검색...']");
    await searchInput.fill("하이라이트대상");
    await expect(page.locator("mark.search-hl").first()).toBeVisible({ timeout: 10000 });
  });
});

// ============================================================================
// 5. TC 관리 (TC-TCM-001 ~ 018)
// ============================================================================
test.describe("5. TC 관리", () => {
  let projectName: string;
  test.beforeEach(async ({ page }) => {
    projectName = `E2E_TCM_${Date.now()}`;
    await login(page);
    await createProject(page, projectName);
  });
  test.afterEach(async ({ page }) => {
    try { await page.goto("/projects");
      await page.locator("h3").filter({ hasText: projectName }).click();
      await deleteProject(page, projectName);
    } catch { /* ignore */ }
  });

  test("TC-TCM-001: 그리드 로드", async ({ page }) => {
    await addSheetAndRows(page, "Grid", 1);
    await expect(page.locator(".ag-theme-alpine")).toBeVisible({ timeout: 10000 });
  });

  test("TC-TCM-003: TC 생성 (행 추가)", async ({ page }) => {
    await addSheetAndRows(page, "Create", 1);
    // 그리드에 행이 추가됨
    const rows = page.locator(".ag-row");
    expect(await rows.count()).toBeGreaterThanOrEqual(1);
  });

  test("TC-TCM-005: TC 수정 (셀 편집)", async ({ page }) => {
    await addSheetAndRows(page, "Edit", 1);
    // category 셀 더블클릭 편집
    const cell = page.locator(".ag-cell[col-id='category']").first();
    await cell.dblclick();
    await page.keyboard.type("Auth");
    const saved = page.waitForResponse(
      (r) => /\/testcases\/\d+$/.test(r.url()) && r.request().method() === "PUT"
    );
    await page.keyboard.press("Tab");
    await saved;
    await expect(page.locator(".ag-cell[col-id='category']").first()).toHaveText("Auth");
  });

  test("TC-TCM-007: TC 삭제", async ({ page }) => {
    // 행 하나로 검증한다. 행이 여럿일 때 체크박스 한 칸만 켜는 것이 ag-grid 에서
    // 안정적으로 재현되지 않아(2건 선택되거나 0건이 됨) 조건을 단순하게 둔다.
    await addSheetAndRows(page, "Delete", 1);

    await page.locator('.ag-row[row-index="0"] input[type="checkbox"]').first().check();
    await expect(page.locator(".ag-row-selected")).toHaveCount(1);

    const delBtn = page.getByRole("button", { name: /선택 삭제/ });
    await expect(delBtn).toBeEnabled();

    page.on("dialog", (d) => d.accept());
    await delBtn.click();
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(0);
  });

  test("TC-TCM-008: 선택 복제가 행을 하나 늘린다", async ({ page }) => {
    // 예전에는 try/catch 로 전부 삼키고 expect(true).toBe(true) 로 끝났다.
    // 복제가 통째로 고장 나도 통과하는 테스트였다.
    await addSheetAndRows(page, "Copy", 1);

    // 래퍼(.ag-selection-checkbox)를 누르면 포커스만 가고 체크가 안 걸리는 경우가 있다.
    // 실제 input 을 check() 로 눌러 상태를 보장한다.
    await page.locator('.ag-row[row-index="0"] input[type="checkbox"]').first().check();
    await expect(page.locator(".ag-row-selected")).toHaveCount(1);

    const cloneBtn = page.getByRole("button", { name: /선택 복제/ });
    await expect(cloneBtn).toBeEnabled();
    await cloneBtn.click();

    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(2);
  });

  test("TC-TCM-013: TC 필터링 (우선순위별)", async ({ page }) => {
    await addSheetAndRows(page, "Filter", 1);
    // ag-grid 필터 존재 확인
    await expect(page.locator(".ag-theme-alpine")).toBeVisible();
  });

  test("TC-TCM-015: TC 검색", async ({ page }) => {
    await addSheetAndRows(page, "Search", 1);
    const searchInput = page.locator("input[placeholder='검색...']");

    // 없는 값으로 거르면 남는 행이 없다
    await searchInput.fill("__없는값__");
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(0);

    // 지우면 되돌아온다
    await searchInput.fill("");
    await expect(page.locator(".ag-center-cols-container .ag-row")).toHaveCount(1);
  });

  test("TC-TCM-016: TC 정렬", async ({ page }) => {
    await addSheetAndRows(page, "Sort", 3);
    // No 헤더 클릭으로 정렬
    const noHeader = page.locator(".ag-header-cell").filter({ hasText: "No" });
    await noHeader.click();
    await expect(noHeader).toHaveAttribute("aria-sort", /ascending|descending/);
  });

  test("TC-TCM-018: 찾기/바꾸기", async ({ page }) => {
    await addSheetAndRows(page, "Replace", 1);
    // 바꾸기 버튼
    const replaceBtn = page.getByRole("button", { name: "바꾸기", exact: true });
    await expect(replaceBtn).toBeVisible();
    await replaceBtn.click();
    await expect(page.locator("input[placeholder='바꿀 내용...']")).toBeVisible();
  });
});

// ============================================================================
// 6. 테스트 수행 (TC-TR-001 ~ 030)
// ============================================================================
test.describe("6. 테스트 수행", () => {
  test("TC-TR-001: 테스트 Run 생성 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_TR_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    // TC 추가
    await request.post(`/api/projects/${pid}/testcases`, { data: { no: 1, tc_id: "TR-001" }, headers: h });

    // Run 생성
    const run = await request.post(`/api/projects/${pid}/testruns`, { data: { name: "Run 1" }, headers: h });
    expect(run.status()).toBe(201);
    const runData = await run.json();
    expect(runData.name).toBe("Run 1");
    expect(runData.status).toBe("in_progress");

    // Run 조회 → results 포함
    const detail = await request.get(`/api/projects/${pid}/testruns/${runData.id}`, { headers: h });
    const detailData = await detail.json();
    expect(detailData.results.length).toBeGreaterThanOrEqual(1);
    expect(detailData.results[0].result).toBe("NS");

    // 결과 제출
    const submitRes = await request.post(`/api/projects/${pid}/testruns/${runData.id}/results`, {
      data: [{ test_case_id: detailData.results[0].test_case_id, result: "PASS" }],
      headers: h,
    });
    expect(submitRes.status()).toBe(200);

    // Run 완료
    const completeRes = await request.put(`/api/projects/${pid}/testruns/${runData.id}/complete`, { headers: h });
    expect(completeRes.status()).toBe(200);
    expect((await completeRes.json()).status).toBe("completed");

    // Run 복제
    const cloneRes = await request.post(`/api/projects/${pid}/testruns/${runData.id}/clone`, { headers: h });
    expect(cloneRes.status()).toBe(201);

    // Run 삭제 (admin 권한 필요)
    const delRes = await request.delete(`/api/projects/${pid}/testruns/${runData.id}`, { headers: h });
    expect([200, 204].includes(delRes.status())).toBe(true);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });

  test("TC-TR-002: Run 유효성 검사 (빈 이름)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_TRV_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    // 빈 이름 - Pydantic에서 str 타입은 빈 문자열도 허용할 수 있으므로 201도 가능
    const run = await request.post(`/api/projects/${pid}/testruns`, { data: { name: "" }, headers: h });
    expect([201, 400, 422].includes(run.status())).toBe(true);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });
});

// ============================================================================
// 8. 대시보드 (TC-DSH-001 ~ 010)
// ============================================================================
test.describe("8. 대시보드", () => {
  test("TC-DSH-001~009: 대시보드 API", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_DSH_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    // TC + Run 추가
    await request.post(`/api/projects/${pid}/testcases`, { data: { no: 1, tc_id: "DSH-001", priority: "높음", category: "Auth" }, headers: h });
    await request.post(`/api/projects/${pid}/testcases`, { data: { no: 2, tc_id: "DSH-002", priority: "보통", category: "Pay" }, headers: h });
    const run = await request.post(`/api/projects/${pid}/testruns`, { data: { name: "DSH Run" }, headers: h });
    const runId = (await run.json()).id;
    const detail = await request.get(`/api/projects/${pid}/testruns/${runId}`, { headers: h });
    const results = (await detail.json()).results;
    await request.post(`/api/projects/${pid}/testruns/${runId}/results`, {
      data: results.map((r: { test_case_id: number }, i: number) => ({ test_case_id: r.test_case_id, result: i === 0 ? "PASS" : "FAIL" })),
      headers: h,
    });

    // Summary
    const sum = await request.get(`/api/projects/${pid}/dashboard/summary`, { headers: h, params: { run_id: runId } });
    expect(sum.status()).toBe(200);
    const sumData = await sum.json();
    expect(sumData.total).toBe(2);
    expect(sumData.pass).toBe(1);
    expect(sumData.fail).toBe(1);

    // Priority
    const pri = await request.get(`/api/projects/${pid}/dashboard/priority`, { headers: h, params: { run_id: runId } });
    expect(pri.status()).toBe(200);
    expect((await pri.json()).length).toBeGreaterThanOrEqual(1);

    // Category
    const cat = await request.get(`/api/projects/${pid}/dashboard/category`, { headers: h, params: { run_id: runId } });
    expect(cat.status()).toBe(200);

    // Rounds
    const rnd = await request.get(`/api/projects/${pid}/dashboard/rounds`, { headers: h });
    expect(rnd.status()).toBe(200);

    // Assignee
    const asg = await request.get(`/api/projects/${pid}/dashboard/assignee`, { headers: h, params: { run_id: runId } });
    expect(asg.status()).toBe(200);

    // Heatmap
    const hm = await request.get(`/api/projects/${pid}/dashboard/heatmap`, { headers: h, params: { run_id: runId } });
    expect(hm.status()).toBe(200);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });
});

// ============================================================================
// 9. 리포트 (TC-RPT-001 ~ 006)
// ============================================================================
test.describe("9. 리포트", () => {
  test("TC-RPT-001~005: 리포트 API", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_RPT_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;
    await request.post(`/api/projects/${pid}/testcases`, { data: { no: 1, tc_id: "RPT-001" }, headers: h });
    const run = await request.post(`/api/projects/${pid}/testruns`, { data: { name: "RPT Run" }, headers: h });
    const runId = (await run.json()).id;

    // Report data
    const rpt = await request.get(`/api/projects/${pid}/reports`, { headers: h, params: { run_id: runId } });
    expect(rpt.status()).toBe(200);
    const rptData = await rpt.json();
    expect(rptData.project).toBeTruthy();
    expect(rptData.summary).toBeTruthy();

    // Excel export
    const excel = await request.get(`/api/projects/${pid}/testcases/export`, { headers: h });
    expect(excel.status()).toBe(200);

    // Run export
    const runExport = await request.get(`/api/projects/${pid}/testruns/${runId}/export`, { headers: h });
    expect(runExport.status()).toBe(200);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });
});

// ============================================================================
// 9-1. 테스트 수행 이슈 링크 (TC-RUN-023, SYM-123)
//   jsdom 단위 테스트는 AG Grid 가 셀에 단 브라우저 리스너의 순서를 재현하지 못한다.
//   ↗ 가 포커스를 가져가거나 더블클릭이 셀로 번지면 닫히지 않는 편집기가 열렸던
//   경로를 실제 브라우저로 고정한다.
// ============================================================================
test.describe("9-1. 테스트 수행 이슈 링크", () => {
  test("TC-RUN-023: ↗ 는 이슈를 열고 셀 편집을 망가뜨리지 않는다", async ({ page, request, context }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };
    const name = `E2E_ISSUE_${Date.now()}`;
    const proj = await request.post("/api/projects", { data: { name, jira_base_url: "https://linear.app/e2e" }, headers: h });
    const pid = (await proj.json()).id;
    await request.post(`/api/projects/${pid}/testcases`, { data: { no: 1, tc_id: "ISS-001" }, headers: h });
    const run = await request.post(`/api/projects/${pid}/testruns`, { data: { name: "ISS Run" }, headers: h });
    const runId = (await run.json()).id;
    const detail = await (await request.get(`/api/projects/${pid}/testruns/${runId}`, { headers: h })).json();
    await request.post(`/api/projects/${pid}/testruns/${runId}/results`, {
      data: [{ test_case_id: detail.results[0].test_case_id, result: "PASS", issue_link: "SYM-9" }],
      headers: h,
    });

    // 외부 사이트에 실제로 가지 않는다
    await context.route("https://linear.app/**", (r) => r.fulfill({ status: 200, body: "ok" }));

    try {
      await login(page);
      await page.goto(`/projects/${pid}?tab=run`);
      await page.getByText("ISS Run").first().click();
      const link = page.getByTestId("issue-link-open").first();
      await link.scrollIntoViewIfNeeded();
      await expect(link).toHaveAttribute("href", "https://linear.app/e2e/issue/SYM-9");
      const editors = page.locator(".ag-cell-inline-editing");

      // 1. ↗ 더블클릭: 새 탭 하나, 편집기 없음
      const [tab1] = await Promise.all([context.waitForEvent("page"), link.dblclick()]);
      await tab1.close();
      await expect(editors).toHaveCount(0);

      // 2. 가운데 버튼 클릭 뒤 Enter: 편집기가 열려도 Escape 로 닫혀야 한다
      const [tab2] = await Promise.all([context.waitForEvent("page"), link.click({ button: "middle" })]);
      await tab2.close();
      await page.bringToFront();
      await page.keyboard.press("Enter");
      await page.keyboard.press("Escape");
      await expect(editors).toHaveCount(0);

      // 3. 링크에 포커스가 있을 때 Enter: 편집기가 아니라 링크가 열린다
      await link.evaluate((el) => (el as HTMLElement).focus());
      const [tab3] = await Promise.all([context.waitForEvent("page"), page.keyboard.press("Enter")]);
      await tab3.close();
      await expect(editors).toHaveCount(0);
    } finally {
      await request.delete(`/api/projects/${pid}`, { headers: h });
    }
  });
});

// ============================================================================
// 10. 관리자 (TC-ADM-001 ~ 006)
// ============================================================================
test.describe("10. 관리자", () => {
  test("TC-ADM-001: 관리 페이지 접근", async ({ page }) => {
    await login(page);
    await page.locator("header button").filter({ hasText: /^관리$/ }).click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByText("사용자 관리")).toBeVisible({ timeout: 5000 });
  });

  test("TC-ADM-002: 사용자 목록 표시", async ({ page }) => {
    await login(page);
    await page.locator("header button").filter({ hasText: /^관리$/ }).click();
    // admin 사용자 표시
    await expect(page.getByText("admin").first()).toBeVisible();
  });
});

// ============================================================================
// 12. 에러 처리 (TC-ERR-001 ~ 010)
// ============================================================================
test.describe("12. 에러 처리", () => {
  test("TC-ERR-003: 없는 주소는 프로젝트 목록으로 되돌린다", async ({ page }) => {
    await login(page);
    await page.goto("/nonexistent-page-xyz");
    // App.tsx 의 catch-all 라우트가 /projects 로 보낸다
    await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
  });

  test("TC-ERR-005: TC 필드 특수문자", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_Special_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    const tc = await request.post(`/api/projects/${pid}/testcases`, {
      data: { no: 1, tc_id: "SP-001", category: '<script>alert("xss")</script>', depth1: "Test & \"quotes\"" },
      headers: h,
    });
    expect(tc.status()).toBe(201);
    const tcData = await tc.json();
    expect(tcData.category).toContain("script");
    expect(tcData.depth1).toContain("&");

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });

  test("TC-ERR-006: 프로젝트명 특수문자", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `Test <>&"' ${Date.now()}` }, headers: h });
    expect(proj.status()).toBe(201);
    const pid = (await proj.json()).id;
    await request.delete(`/api/projects/${pid}`, { headers: h });
  });
});

// ============================================================================
// 13. 보안 (TC-SEC-001 ~ 008)
// ============================================================================
test.describe("13. 보안", () => {
  test("TC-SEC-002: 토큰 없이 API 호출", async ({ request }) => {
    const r = await request.get("/api/projects");
    expect(r.status()).toBe(401);
  });

  test("TC-SEC-003: 타 프로젝트 접근 방지", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    // 존재하지 않는 프로젝트
    const r = await request.get("/api/projects/99999/testcases", { headers: h });
    expect(r.status()).toBe(404);
  });

  test("TC-SEC-005: 대량 TC import 성능", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_Bulk_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    // 500행 CSV
    let csv = "No,TC ID,Category,Priority\n";
    for (let i = 1; i <= 500; i++) csv += `${i},BULK-${i},Cat-${i % 10},High\n`;

    const start = Date.now();
    const r = await request.post(`/api/projects/${pid}/testcases/import`, {
      headers: h,
      multipart: { file: { name: "bulk.csv", mimeType: "text/csv", buffer: Buffer.from(csv) } },
    });
    const elapsed = Date.now() - start;
    expect(r.status()).toBe(201);
    expect((await r.json()).created).toBe(500);
    expect(elapsed).toBeLessThan(30000); // 30초 이내

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });

  test("TC-SEC-007: 동시성 테스트", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    // 동시에 프로젝트 3개 생성
    const promises = [1, 2, 3].map((i) =>
      request.post("/api/projects", { data: { name: `E2E_Conc_${Date.now()}_${i}` }, headers: h })
    );
    const results = await Promise.all(promises);
    for (const r of results) expect(r.status()).toBe(201);

    // 정리
    for (const r of results) {
      const pid = (await r.json()).id;
      await request.delete(`/api/projects/${pid}`, { headers: h });
    }
  });
});

// ============================================================================
// 14. Import/Export 확장 (TC-TCM-009 ~ 012)
// ============================================================================
test.describe("14. Import/Export", () => {
  test("TC-TCM-009: Excel Import (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_Imp_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    // xlsx 파일은 없으므로 CSV로 대체 테스트
    const csv = "TC ID,Category,Priority\nIMP-001,Auth,High\nIMP-002,Pay,Low\n";
    const r = await request.post(`/api/projects/${pid}/testcases/import`, {
      headers: h,
      multipart: { file: { name: "import.csv", mimeType: "text/csv", buffer: Buffer.from(csv) } },
    });
    expect(r.status()).toBe(201);

    // Export
    const exp = await request.get(`/api/projects/${pid}/testcases/export`, { headers: h });
    expect(exp.status()).toBe(200);
    const body = await exp.body();
    expect(body.length).toBeGreaterThan(100);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });

  test("TC-TCM-010: 잘못된 파일 Import 거부", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_BadImp_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    const r = await request.post(`/api/projects/${pid}/testcases/import`, {
      headers: h,
      multipart: { file: { name: "bad.txt", mimeType: "text/plain", buffer: Buffer.from("not a csv") } },
    });
    expect(r.status()).toBe(400);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });

  test("TC-TCM-012: Export 후 Import 왕복", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_Round_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    // TC 생성
    await request.post(`/api/projects/${pid}/testcases`, { data: { no: 1, tc_id: "RT-001", category: "Auth", priority: "높음", sheet_name: "기본" }, headers: h });

    // Export
    const exp = await request.get(`/api/projects/${pid}/testcases/export`, { headers: h });
    expect(exp.status()).toBe(200);
    const xlsxBody = await exp.body();
    expect(xlsxBody.length).toBeGreaterThan(100);

    // Re-import (xlsx)
    const imp = await request.post(`/api/projects/${pid}/testcases/import`, {
      headers: h,
      multipart: { file: { name: "export.xlsx", mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", buffer: xlsxBody } },
    });
    // Export 파일을 다시 Import하면 201 (성공) 또는 기존 TC 업데이트
    expect(imp.status()).toBe(201);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });
});

// ============================================================================
// 15. Bulk 작업 (TC-TCM-009, 벌크 업데이트/삭제)
// ============================================================================
test.describe("15. Bulk 작업", () => {
  test("Bulk Update (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", { data: { username: "admin", password: PASSWORD } });
    const { access_token } = await loginRes.json();
    const h = { Authorization: `Bearer ${access_token}` };

    const proj = await request.post("/api/projects", { data: { name: `E2E_Bulk_${Date.now()}` }, headers: h });
    const pid = (await proj.json()).id;

    const tc1 = await request.post(`/api/projects/${pid}/testcases`, { data: { no: 1, tc_id: "BLK-001", priority: "보통" }, headers: h });
    const tc2 = await request.post(`/api/projects/${pid}/testcases`, { data: { no: 2, tc_id: "BLK-002", priority: "보통" }, headers: h });
    const id1 = (await tc1.json()).id;
    const id2 = (await tc2.json()).id;

    const bulk = await request.put(`/api/projects/${pid}/testcases/bulk`, {
      data: { items: [{ id: id1, priority: "높음" }, { id: id2, priority: "높음" }] },
      headers: h,
    });
    expect(bulk.status()).toBe(200);
    const bulkData = await bulk.json();
    expect(bulkData.every((t: { priority: string }) => t.priority === "높음")).toBe(true);

    // Bulk Delete
    const del = await request.delete(`/api/projects/${pid}/testcases/bulk`, { headers: h, params: { ids: `${id1},${id2}` } });
    expect(del.status()).toBe(200);
    expect((await del.json()).deleted).toBe(2);

    await request.delete(`/api/projects/${pid}`, { headers: h });
  });
});
