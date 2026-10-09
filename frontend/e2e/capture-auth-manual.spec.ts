/**
 * 매뉴얼 스크린샷: 로그인 · 가입 · 계정 연결 · 사용자 관리 · 계정 요청 (System 2.2.0.1)
 *
 * 실제 DB 를 쓰지 않는다. 빈 DB 를 따로 만들고 격리 포트로 띄운다.
 * 1. 빈 DB 를 만들고 백엔드를 8018 로 띄운다. 환경변수:
 *    DATABASE_URL=<빈 DB>, GOOGLE_CLIENT_ID=<아무 값>, GOOGLE_CLIENT_SECRET=<아무 값>,
 *    AUTH_APPROVAL=personal, AUTH_COMPANY_DOMAINS=example.com, CORS_ORIGINS=http://localhost:5183
 * 2. 프론트: npx vite --config vite.e2e-local.config.ts --port 5183 --strictPort
 * 3. 데이터(주소는 전부 예약 도메인 example.com / example.org):
 *    - 첫 관리자 username=admin, display_name=관리자, password=test1234 (가입 화면 또는 POST /api/auth/register)
 *    - 이메일 가입 kim.minji@example.com(승인), choi.hyun@example.com(승인, QA 관리자),
 *      lee.jun@example.com(승인 뒤 사용 중지), park.seoyeon@example.org(승인 대기)
 *    - SQL: admin 에 email=google_email='admin@example.com', google_sub 임의 값
 *    - SQL: Google 전용 계정 jung.yuna@example.com (password_hash NULL, google_sub, google_email 채움, active)
 * 4. 실행: CI=1 npx playwright test -c playwright.e2e-local.config.ts e2e/capture-auth-manual.spec.ts
 *
 * 계정 요청 두 건은 이 스펙이 직접 접수한다(공개 API).
 */
import { test, expect, type Page } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const SAVE_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "../public/manual-images");
const PASSWORD = process.env.TEST_ADMIN_PASSWORD || "test1234";

// 날짜 표기가 브라우저 로캘을 따른다. 한국어 매뉴얼이므로 ko-KR 로 고정한다
test.use({ locale: "ko-KR", timezoneId: "Asia/Seoul" });

async function shot(page: Page, name: string, fullPage = false) {
  await page.screenshot({ path: path.join(SAVE_DIR, name), fullPage });
}

test("인증 화면 매뉴얼 스크린샷", async ({ page, request }) => {
  test.setTimeout(60000);
  await page.setViewportSize({ width: 1280, height: 800 });

  // 01. 로그인 (Google 버튼 포함)
  await page.goto("/login");
  await expect(page.getByRole("link", { name: "Google 로 로그인" })).toBeVisible();
  await shot(page, "01_login_page.png");

  // 02. 회원가입 (이메일 가입)
  await page.goto("/register");
  await expect(page.getByLabel("이메일")).toBeVisible();
  await shot(page, "02_register_page.png");

  await page.goto("/login");
  await page.getByPlaceholder("아이디 또는 이메일을 입력하세요").fill("admin");
  await page.getByPlaceholder("비밀번호를 입력하세요").fill(PASSWORD);
  await page.getByRole("button", { name: "로그인", exact: true }).click();
  await expect(page).toHaveURL(/\/projects/, { timeout: 10000 });

  // 22, 25. 사용자 관리 (승인 대기 배너, 로그인 방식, 상태, 계정 버튼)
  await page.goto("/admin");
  await expect(page.getByText("Google: admin@example.com")).toBeVisible();
  await shot(page, "22_admin_page.png");
  await shot(page, "25_admin_page_with_reset.png");

  // 44. 계정 연결 창
  await page.goto("/projects");
  await page.getByRole("button", { name: /관리자/ }).first().click();
  await page.getByRole("button", { name: "계정 연결" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await shot(page, "44_account_link_modal.png");

  // 39, 40. 계정 요청 목록과 재설정 코드 발급
  for (const data of [
    { request_type: "find_id", claimed_display_name: "이준", contact: "사내 메신저 lee.jun", note: "아이디가 기억나지 않습니다" },
    { request_type: "reset_password", claimed_username: "kim.minji@example.com", contact: "내선 1234", note: "비밀번호 분실" },
  ]) {
    const res = await request.post("/api/auth/account-requests", { data });
    expect(res.ok()).toBeTruthy();
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto("/admin");
  const resetRow = page.getByRole("row", { name: /내선 1234/ });
  await expect(resetRow).toBeVisible();
  await shot(page, "39_admin_account_requests.png", true);

  page.on("dialog", (d) => void d.accept());
  await resetRow.getByRole("combobox").selectOption({ label: "kim.minji@example.com (김민지)" });
  await resetRow.getByRole("button", { name: "승인" }).click();
  await expect(page.getByRole("button", { name: "복사" })).toBeVisible();
  await shot(page, "40_admin_code_issued.png", true);
});
