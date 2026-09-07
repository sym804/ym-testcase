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

test.describe("자동 저장 거부 처리", () => {
  // 저장이 409 로 거부되면 그 값이 화면에 남아서는 안 된다.
  // 남으면 자동저장이 행 전체를 보내므로 같은 행의 다음 편집도 계속 409 가 나고,
  // 사용자는 토스트를 놓치면 저장된 줄 안다.
  test("저장이 거부되면 값이 되돌아가고 같은 행의 다음 편집은 저장된다", async ({ page, request }) => {
    const pw = process.env.TEST_ADMIN_PASSWORD || "test1234";
    const auth = await request.post("/api/auth/login", {
      data: { username: "admin", password: pw },
    });
    expect(auth.ok()).toBeTruthy();
    const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };

    const projectName = `E2E_Revert_${Date.now()}`;
    const proj = await (await request.post("/api/projects", {
      headers, data: { name: projectName, description: "자동저장 거부" },
    })).json();
    await request.post(`/api/projects/${proj.id}/testcases/sheets`, {
      headers, data: { name: "기본" },
    });
    for (const [no, tcId] of [[1, "REV-001"], [2, "REV-002"]] as [number, string][]) {
      await request.post(`/api/projects/${proj.id}/testcases`, {
        headers,
        data: {
          no, tc_id: tcId, sheet_name: "기본", category: "원본",
          test_steps: "1. 한다", expected_result: "된다", priority: "P2",
        },
      });
    }

    await login(page);
    const card = page.locator("h3").filter({ hasText: projectName }).first();
    await expect(card).toBeVisible({ timeout: 15000 });
    await card.click();
    await expect(page.locator(".ag-header-cell").first()).toBeVisible({ timeout: 20000 });
    await page.waitForTimeout(1500);

    // 두 번째 행의 TC ID 를 첫 행과 같은 값으로 바꾼다 (서버가 409 로 거부한다)
    await page.locator('.ag-row[row-index="1"] [col-id="tc_id"]').dblclick();
    await page.locator(".ag-cell-inline-editing input.ag-input-field-input")
      .first().fill("REV-001");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2500);

    // 거부된 값이 화면에 남으면 안 된다
    await expect(page.locator('.ag-row[row-index="1"] [col-id="tc_id"]'))
      .toHaveText("REV-002", { timeout: 5000 });

    // 같은 행의 다른 칸 편집이 정상 저장돼야 한다
    await page.locator('.ag-row[row-index="1"] [col-id="category"]').dblclick();
    await page.locator(".ag-cell-inline-editing input.ag-input-field-input")
      .first().fill("수정됨");
    await page.keyboard.press("Enter");
    await page.waitForTimeout(2500);

    const list = await (await request.get(
      `/api/projects/${proj.id}/testcases`, { headers })).json();
    const items = list.items ?? list;
    const row2 = items.find((t: { no: number }) => t.no === 2);
    expect(row2.tc_id).toBe("REV-002");
    expect(row2.category).toBe("수정됨");

    await request.delete(`/api/projects/${proj.id}`, { headers });
  });
});

  // 셀 편집 말고 일괄 변경 경로도 같아야 한다. 이쪽은 onCellValueChanged 를
  // 타지 않고 행 데이터를 직접 바꾼 뒤 자동저장만 부른다.
  test("모두 바꾸기가 거부돼도 값이 되돌아간다", async ({ page, request }) => {
    const pw = process.env.TEST_ADMIN_PASSWORD || "test1234";
    const auth = await request.post("/api/auth/login", {
      data: { username: "admin", password: pw },
    });
    expect(auth.ok()).toBeTruthy();
    const headers = { Authorization: `Bearer ${(await auth.json()).access_token}` };

    const projectName = `E2E_Bulk_${Date.now()}`;
    const proj = await (await request.post("/api/projects", {
      headers, data: { name: projectName, description: "일괄 변경 거부" },
    })).json();
    await request.post(`/api/projects/${proj.id}/testcases/sheets`, {
      headers, data: { name: "기본" },
    });
    for (const [no, tcId] of [[1, "BLK-001"], [2, "BLK-002"]] as [number, string][]) {
      await request.post(`/api/projects/${proj.id}/testcases`, {
        headers,
        data: {
          no, tc_id: tcId, sheet_name: "기본", category: "원본",
          test_steps: "1. 한다", expected_result: "된다", priority: "P2",
        },
      });
    }

    await login(page);
    const card = page.locator("h3").filter({ hasText: projectName }).first();
    await expect(card).toBeVisible({ timeout: 15000 });
    await card.click();
    await expect(page.locator(".ag-header-cell").first()).toBeVisible({ timeout: 20000 });
    await page.waitForTimeout(1500);

    // BLK-002 를 BLK-001 로 모두 바꾼다 (서버가 409 로 거부한다)
    await page.getByPlaceholder("검색...", { exact: true }).fill("BLK-002");
    await page.getByRole("button", { name: "바꾸기" }).click();
    await page.getByPlaceholder("바꿀 내용...").fill("BLK-001");
    await page.getByRole("button", { name: "모두 바꾸기" }).click();
    await page.waitForTimeout(3000);

    const list = await (await request.get(
      `/api/projects/${proj.id}/testcases`, { headers })).json();
    const items = list.items ?? list;
    const row2 = items.find((t: { no: number }) => t.no === 2);
    expect(row2.tc_id).toBe("BLK-002");

    // 검색어가 걸린 채면 행이 걸러져 보이지 않는다. 풀고 화면 값을 본다.
    await page.getByPlaceholder("검색...", { exact: true }).fill("");
    await page.waitForTimeout(800);

    // 거부된 값이 화면에 남으면 안 된다
    await expect(page.locator('.ag-row[row-index="1"] [col-id="tc_id"]'))
      .toHaveText("BLK-002", { timeout: 5000 });

    await request.delete(`/api/projects/${proj.id}`, { headers });
  });
