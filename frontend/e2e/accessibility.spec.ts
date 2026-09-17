/**
 * 접근성 검사 (axe-core)
 *
 * 화면이 늘어날수록 접근성은 소급해서 붙이기 어렵다. 그래서 규칙이 아니라
 * 검사로 둔다. serious 이상만 막는다. moderate 까지 막으면 ag-grid 가 만드는
 * DOM 때문에 우리가 고칠 수 없는 항목에서 계속 빨개진다.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const PASSWORD = "test1234";
const BLOCKING = ["critical", "serious"];

/**
 * ag-grid 가 스스로 만드는 뼈대만 제외한다.
 *
 * `.ag-root-wrapper` 를 통째로 빼면 그 안에 든 우리 셀 렌더러까지 같이 빠져서
 * TC 관리 화면의 실제 결함을 놓친다. 헤더와 가상 스크롤 뼈대만 제외하고
 * 셀 내용은 검사에 남긴다. 셀 렌더러는 src/test/accessibility.test.tsx 에서
 * 컴포넌트 단위로도 본다.
 */
async function scan(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude(".ag-header")
    .exclude(".ag-body-horizontal-scroll")
    .exclude(".ag-body-vertical-scroll")
    .analyze();

  return results.violations.filter((v) => BLOCKING.includes(v.impact ?? ""));
}

/** 위반을 읽을 수 있게 편다. 규칙 이름만 나오면 어디를 고칠지 알 수 없다. */
function describe(violations: Awaited<ReturnType<typeof scan>>) {
  return violations
    .map((v) => {
      const where = v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ");
      return `[${v.impact}] ${v.id}: ${v.help}\n    ${where}`;
    })
    .join("\n");
}

async function login(page: Page) {
  await page.goto("/login");
  await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/projects/);
}

test.describe("접근성", () => {
  test("로그인 화면에 serious 이상 위반이 없다", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("button", { name: "로그인" })).toBeVisible();

    const violations = await scan(page);
    expect(violations, describe(violations)).toEqual([]);
  });

  test("프로젝트 목록에 serious 이상 위반이 없다", async ({ page }) => {
    await login(page);
    await expect(page.getByText("+ 새 프로젝트")).toBeVisible();

    const violations = await scan(page);
    expect(violations, describe(violations)).toEqual([]);
  });

  test("회원가입 화면에 serious 이상 위반이 없다", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByRole("button", { name: "회원가입" })).toBeVisible();

    const violations = await scan(page);
    expect(violations, describe(violations)).toEqual([]);
  });

  test("아이콘만 있는 버튼에 이름이 있다", async ({ page }) => {
    // 헤더는 로그인 뒤에만 뜬다
    await login(page);

    // 다크모드 토글은 아이콘뿐이라 이름이 없으면 스크린리더에서 "버튼"으로만 읽힌다
    const toggle = page.getByRole("button", { name: /다크 모드|라이트 모드|dark mode|light mode/i });
    await expect(toggle).toBeVisible();
  });

  test("TC 관리 화면에 serious 이상 위반이 없다", async ({ page, request }) => {
    // CI 는 빈 DB 로 시작한다. 기존 프로젝트에 기대지 않고 직접 만든다.
    const login = await request.post("/api/auth/login", {
      data: { username: "admin", password: PASSWORD },
    });
    const { access_token } = await login.json();
    const headers = { Authorization: `Bearer ${access_token}` };
    const name = `E2E_A11y_${Date.now()}`;
    const proj = await (await request.post("/api/projects", { data: { name }, headers })).json();
    await request.post(`/api/projects/${proj.id}/testcases/sheets`, {
      data: { name: "기본", parent_id: null, is_folder: false },
      headers,
    });
    await request.post(`/api/projects/${proj.id}/testcases`, {
      data: {
        tc_id: "A11Y-001", type: "기능", category: "접근성", depth1: "검사",
        test_steps: "1. 연다", expected_result: "위반이 없다", priority: "P2",
        sheet_name: "기본",
      },
      headers,
    });

    await page.goto("/login");
    await page.getByPlaceholder("아이디를 입력하세요").fill("admin");
    await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
    await page.getByRole("button", { name: "로그인" }).click();
    await expect(page).toHaveURL(/\/projects/);

    await page.locator("h3").filter({ hasText: name }).click();
    await expect(page.locator(".ag-header-cell").first()).toBeVisible({ timeout: 20000 });

    const violations = await scan(page);
    try {
      expect(violations, describe(violations)).toEqual([]);
    } finally {
      await request.delete(`/api/projects/${proj.id}`, { headers });
    }
  });
});
