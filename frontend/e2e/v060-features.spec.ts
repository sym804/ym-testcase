import { test, expect, type Page } from "@playwright/test";

const TEST_ADMIN_PASSWORD = process.env.TEST_ADMIN_PASSWORD || "test1234";

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(TEST_ADMIN_PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });
}

async function createProject(page: Page, name: string) {
  await page.getByText("+ 새 프로젝트").click();
  await page.getByPlaceholder("프로젝트 이름").fill(name);
  await page.getByRole("button", { name: "생성" }).click();
  await page.waitForTimeout(2000);
  const card = page.locator("h3").filter({ hasText: name });
  await expect(card).toBeVisible({ timeout: 10000 });
  await card.click();
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

// ============================================================================
// 1. 시트 트리 구조
// ============================================================================
test.describe("시트 트리 구조", () => {
  let projectName: string;

  test.beforeEach(async ({ page }) => {
    projectName = `E2E_Tree_${Date.now()}`;
    await login(page);
    await createProject(page, projectName);
  });

  test.afterEach(async ({ page }) => {
    try {
      // 프로젝트 목록으로 이동 후 삭제
      await page.goto("/projects");
      await page.waitForTimeout(1000);
      const card = page.locator("h3").filter({ hasText: projectName });
      if (await card.isVisible()) {
        await card.click();
        await page.waitForTimeout(1000);
        await deleteProject(page, projectName);
      }
    } catch {
      // 정리 실패 무시
    }
  });

  test("루트 시트 생성", async ({ page }) => {
    // 빈 프로젝트에서 시트 추가
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });
    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("기능");
    await page.getByRole("button", { name: "추가", exact: true }).click();

    // 시트 탭에 표시 확인
    await expect(page.getByText("기능").first()).toBeVisible({ timeout: 10000 });
  });

  test("시트 2개 생성 후 사이드바에 전체 표시", async ({ page }) => {
    // 빈 프로젝트에서 첫 시트 추가
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });

    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("기능");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // 사이드바에서 + 버튼으로 두 번째 시트 추가
    const sidebarPlus = page.locator("[title='루트 시트 추가']");
    await sidebarPlus.click();
    await page.getByPlaceholder("시트 이름").fill("UI");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // 사이드바에 전체 탭 표시
    await expect(page.getByText("전체").first()).toBeVisible({ timeout: 10000 });
  });

  test("사이드바에서 시트 삭제", async ({ page }) => {
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });
    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("삭제할시트");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await expect(page.getByText("삭제할시트").first()).toBeVisible({ timeout: 10000 });

    // 사이드바에서 삭제 (× 버튼)
    page.on("dialog", (d) => d.accept());
    const closeBtn = page.locator("[title='시트 삭제']").first();
    await closeBtn.click();
    await page.waitForTimeout(2000);
  });

  test("사이드바에서 시트 클릭으로 활성화", async ({ page }) => {
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });

    // 시트 2개 생성 (빈 프로젝트 → 첫 시트)
    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("Sheet-A");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // 사이드바에서 두 번째 시트 추가
    const sidebarPlus = page.locator("[title='루트 시트 추가']");
    await sidebarPlus.click();
    await page.getByPlaceholder("시트 이름").fill("Sheet-B");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // 사이드바에서 Sheet-A 클릭
    await page.getByText("Sheet-A").first().click();
    await page.waitForTimeout(500);

    // 사이드바에서 Sheet-B 클릭
    await page.getByText("Sheet-B").first().click();
    await page.waitForTimeout(500);
  });
});

// ============================================================================
// 2. 커스텀 필드 (API 레벨 — 그리드 컬럼은 데이터 있을 때만 표시)
// ============================================================================
test.describe("커스텀 필드", () => {
  test("커스텀 필드 생성 후 TC에 값 저장 (API)", async ({ request }) => {
    // API로 직접 테스트
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    // 프로젝트 생성
    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_CF_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    // 커스텀 필드 생성
    const cfRes = await request.post(`/api/projects/${projId}/custom-fields`, {
      data: { field_name: "환경", field_type: "select", options: ["Dev", "QA", "Prod"] },
      headers,
    });
    expect(cfRes.status()).toBe(201);
    const cf = await cfRes.json();
    expect(cf.field_name).toBe("환경");
    expect(cf.field_type).toBe("select");

    // TC 생성 with custom_fields
    const tcRes = await request.post(`/api/projects/${projId}/testcases`, {
      data: { no: 1, tc_id: "CF-E2E-001", custom_fields: { "환경": "Dev" } },
      headers,
    });
    expect(tcRes.status()).toBe(201);
    const tc = await tcRes.json();
    expect(tc.custom_fields).toBeTruthy();
    expect(tc.custom_fields["환경"]).toBe("Dev");

    // TC 조회 확인
    const listRes = await request.get(`/api/projects/${projId}/testcases`, { headers });
    const tcs = await listRes.json();
    const found = tcs.find((t: { tc_id: string }) => t.tc_id === "CF-E2E-001");
    expect(found?.custom_fields?.["환경"]).toBe("Dev");

    // 필드 삭제
    await request.delete(`/api/projects/${projId}/custom-fields/${cf.id}`, { headers });

    // 정리
    await request.delete(`/api/projects/${projId}`, { headers });
  });

  test("커스텀 필드 중복 이름 거부 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_CFDup_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    await request.post(`/api/projects/${projId}/custom-fields`, {
      data: { field_name: "중복필드", field_type: "text" },
      headers,
    });

    const dupRes = await request.post(`/api/projects/${projId}/custom-fields`, {
      data: { field_name: "중복필드", field_type: "text" },
      headers,
    });
    expect(dupRes.status()).toBe(400);

    await request.delete(`/api/projects/${projId}`, { headers });
  });
});

// ============================================================================
// 3. 테스트 플랜
// ============================================================================
test.describe("테스트 플랜", () => {
  test("플랜 CRUD + Run 연결 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_Plan_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    // TC 추가
    await request.post(`/api/projects/${projId}/testcases`, {
      data: { no: 1, tc_id: "PLAN-TC-001" },
      headers,
    });

    // 플랜 생성
    const planRes = await request.post(`/api/projects/${projId}/testplans`, {
      data: { name: "v1.0 Release", milestone: "Sprint 3" },
      headers,
    });
    expect(planRes.status()).toBe(201);
    const plan = await planRes.json();
    expect(plan.name).toBe("v1.0 Release");
    expect(plan.run_count).toBe(0);

    // TestRun 연결
    const runRes = await request.post(`/api/projects/${projId}/testruns`, {
      data: { name: "Plan Run", test_plan_id: plan.id },
      headers,
    });
    expect(runRes.status()).toBe(201);
    const run = await runRes.json();
    expect(run.test_plan_id).toBe(plan.id);

    // 플랜 조회 → run_count 확인
    const planGetRes = await request.get(`/api/projects/${projId}/testplans/${plan.id}`, { headers });
    const planGet = await planGetRes.json();
    expect(planGet.run_count).toBe(1);

    // 플랜 삭제 → Run.test_plan_id null
    await request.delete(`/api/projects/${projId}/testplans/${plan.id}`, { headers });
    const runAfter = await request.get(`/api/projects/${projId}/testruns/${run.id}`, { headers });
    expect((await runAfter.json()).test_plan_id).toBeNull();

    await request.delete(`/api/projects/${projId}`, { headers });
  });
});

// ============================================================================
// 4. CSV Import
// ============================================================================
test.describe("CSV Import", () => {
  test("CSV 파일 import (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_CSV_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    // CSV import
    const csvContent = "No,TC ID,Category,Priority,Test Steps,Expected Result\n1,CSV-E2E-001,Auth,High,Step1,Result1\n2,CSV-E2E-002,Pay,Medium,Step2,Result2\n";
    const importRes = await request.post(`/api/projects/${projId}/testcases/import`, {
      headers,
      multipart: {
        file: { name: "test.csv", mimeType: "text/csv", buffer: Buffer.from(csvContent, "utf-8") },
      },
    });
    expect(importRes.status()).toBe(201);
    const result = await importRes.json();
    expect(result.created).toBe(2);

    await request.delete(`/api/projects/${projId}`, { headers });
  });

  test("Jira CSV 매핑 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_Jira_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    const jiraCsv = "Issue key,Summary,Issue Type,Priority,Component/s,Description,Assignee\nJIRA-E2E-001,Login Test,Test,High,Auth,Test login,robin\n";
    const importRes = await request.post(`/api/projects/${projId}/testcases/import`, {
      headers,
      multipart: {
        file: { name: "jira.csv", mimeType: "text/csv", buffer: Buffer.from(jiraCsv, "utf-8") },
      },
    });
    expect(importRes.status()).toBe(201);

    // 매핑 확인
    const listRes = await request.get(`/api/projects/${projId}/testcases`, {
      headers,
      params: { sheet_name: "CSV Import" },
    });
    const tcs = await listRes.json();
    const jt = tcs.find((t: { tc_id: string }) => t.tc_id === "JIRA-E2E-001");
    expect(jt).toBeTruthy();
    expect(jt.depth2).toBe("Login Test");
    expect(jt.category).toBe("Auth");
    expect(jt.assignee).toBe("robin");

    await request.delete(`/api/projects/${projId}`, { headers });
  });

  test("CSV import 버튼 .csv 파일 지원 (UI)", async ({ page }) => {
    const projectName = `E2E_CSVBtn_${Date.now()}`;
    await login(page);
    await createProject(page, projectName);

    // 시트 추가 (빈 프로젝트)
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });
    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("CSVTest");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // file input이 .csv 확장자를 허용하는지 확인
    const fileInput = page.locator('input[type="file"]').first();
    const accept = await fileInput.getAttribute("accept");
    expect(accept).toContain(".csv");

    await deleteProject(page, projectName);
  });
});

// ============================================================================
// 5. 고급 필터
// ============================================================================
test.describe("고급 필터", () => {
  test("필터 API: AND/OR 적용 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_Filter_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    // TC 추가
    const tcs = [
      { no: 1, tc_id: "FLT-001", type: "Func.", priority: "높음", assignee: "robin" },
      { no: 2, tc_id: "FLT-002", type: "UI/UX", priority: "보통", assignee: "" },
      { no: 3, tc_id: "FLT-003", type: "Func.", priority: "높음", assignee: "admin" },
    ];
    for (const tc of tcs) {
      await request.post(`/api/projects/${projId}/testcases`, { data: tc, headers });
    }

    // AND 필터
    const andRes = await request.post(`/api/projects/${projId}/filters/apply`, {
      data: {
        name: "_",
        conditions: [
          { field: "type", operator: "eq", value: "Func." },
          { field: "priority", operator: "eq", value: "높음" },
        ],
        logic: "AND",
      },
      headers,
    });
    expect(andRes.status()).toBe(200);
    const andData = await andRes.json();
    expect(andData.length).toBe(2);

    // OR 필터
    const orRes = await request.post(`/api/projects/${projId}/filters/apply`, {
      data: {
        name: "_",
        conditions: [
          { field: "type", operator: "eq", value: "UI/UX" },
          { field: "assignee", operator: "eq", value: "admin" },
        ],
        logic: "OR",
      },
      headers,
    });
    expect(orRes.status()).toBe(200);
    const orData = await orRes.json();
    expect(orData.length).toBe(2);

    // empty 필터
    const emptyRes = await request.post(`/api/projects/${projId}/filters/apply`, {
      data: {
        name: "_",
        conditions: [{ field: "assignee", operator: "empty" }],
        logic: "AND",
      },
      headers,
    });
    expect(emptyRes.status()).toBe(200);
    const emptyData = await emptyRes.json();
    expect(emptyData.length).toBe(1);
    expect(emptyData[0].tc_id).toBe("FLT-002");

    await request.delete(`/api/projects/${projId}`, { headers });
  });

  test("필터 저장/불러오기/삭제 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_SaveFilter_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    // 저장
    const saveRes = await request.post(`/api/projects/${projId}/filters`, {
      data: {
        name: "High Priority",
        conditions: [{ field: "priority", operator: "eq", value: "높음" }],
        logic: "AND",
      },
      headers,
    });
    expect(saveRes.status()).toBe(201);
    const saved = await saveRes.json();
    expect(saved.name).toBe("High Priority");

    // 불러오기
    const listRes = await request.get(`/api/projects/${projId}/filters`, { headers });
    expect(listRes.status()).toBe(200);
    const filters = await listRes.json();
    expect(filters.length).toBe(1);

    // 삭제
    const delRes = await request.delete(`/api/projects/${projId}/filters/${saved.id}`, { headers });
    expect(delRes.status()).toBe(200);

    await request.delete(`/api/projects/${projId}`, { headers });
  });

  test("필터 버튼 UI 표시", async ({ page }) => {
    const projectName = `E2E_FltUI_${Date.now()}`;
    await login(page);
    await createProject(page, projectName);

    // 시트 추가 (빈 프로젝트)
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });
    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("FilterTest");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // 필터 버튼 존재 확인
    const filterBtn = page.locator("button").filter({ hasText: /^필터/ });
    await expect(filterBtn).toBeVisible({ timeout: 10000 });

    // 필터 버튼 클릭 → 패널 표시
    await filterBtn.click();
    await expect(page.getByText("필터 조건")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("+ 조건 추가")).toBeVisible();

    // 조건 추가
    await page.getByText("+ 조건 추가").click();
    await page.waitForTimeout(500);

    // 필드 선택 드롭다운, 연산자 드롭다운, 값 입력 확인
    const selects = page.locator(".ag-theme-alpine").locator("..").locator("select");
    expect(await selects.count()).toBeGreaterThanOrEqual(2);

    await deleteProject(page, projectName);
  });
});

// ============================================================================
// 6. 테스트 런 Reopen (다시 수행)
// ============================================================================
test.describe("테스트 런 Reopen", () => {
  test("완료된 런을 다시 수행 (API)", async ({ request }) => {
    const loginRes = await request.post("/api/auth/login", {
      data: { username: "admin", password: TEST_ADMIN_PASSWORD },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    // 프로젝트 생성
    const projRes = await request.post("/api/projects", {
      data: { name: `E2E_Reopen_${Date.now()}` },
      headers,
    });
    const projId = (await projRes.json()).id;

    // TC 추가
    await request.post(`/api/projects/${projId}/testcases`, {
      data: { no: 1, tc_id: "REOPEN-TC-001" },
      headers,
    });

    // 테스트 런 생성
    const runRes = await request.post(`/api/projects/${projId}/testruns`, {
      data: { name: "Reopen Test Run" },
      headers,
    });
    const run = await runRes.json();
    expect(runRes.status()).toBe(201);

    // 런 완료
    const completeRes = await request.put(
      `/api/projects/${projId}/testruns/${run.id}/complete`,
      { headers }
    );
    expect(completeRes.status()).toBe(200);

    // 런 상태 확인 (완료)
    const detailRes1 = await request.get(
      `/api/projects/${projId}/testruns/${run.id}`,
      { headers }
    );
    const detail1 = await detailRes1.json();
    expect(detail1.status).toBe("completed");

    // Reopen
    const reopenRes = await request.put(
      `/api/projects/${projId}/testruns/${run.id}/reopen`,
      { headers }
    );
    expect(reopenRes.status()).toBe(200);

    // 런 상태 확인 (진행중)
    const detailRes2 = await request.get(
      `/api/projects/${projId}/testruns/${run.id}`,
      { headers }
    );
    const detail2 = await detailRes2.json();
    expect(detail2.status).toBe("in_progress");

    // 정리
    await request.delete(`/api/projects/${projId}`, { headers });
  });
});

// ============================================================================
// 7. 다중 행 추가
// ============================================================================
test.describe("다중 행 추가", () => {
  test("다중 행 추가 드롭다운 표시 (UI)", async ({ page }) => {
    const projectName = `E2E_MultiRow_${Date.now()}`;
    await login(page);
    await createProject(page, projectName);

    // 시트 추가 (빈 프로젝트)
    const addBtn = page.locator("button").filter({ hasText: "시트 추가" }).first();
    await expect(addBtn).toBeVisible({ timeout: 15000 });
    await addBtn.click();
    await page.getByPlaceholder("시트 이름").fill("MultiRowTest");
    await page.getByRole("button", { name: "추가", exact: true }).click();
    await page.waitForTimeout(1000);

    // 다중 추가 드롭다운 버튼 확인 (▼ 또는 드롭다운 트리거)
    const multiAddBtn = page.locator("button").filter({ hasText: /행 추가|다중/ }).first();
    await expect(multiAddBtn).toBeVisible({ timeout: 10000 });

    await deleteProject(page, projectName);
  });
});
