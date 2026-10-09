import type { Page } from "@playwright/test";

/**
 * 로그인 화면으로 튕길 것이 예상되는 이동. 결과는 호출한 쪽이 주소로 판정한다.
 *
 * 앱은 401 을 받으면 window.location 으로 문서를 새로 연다(src/api/client.ts).
 * goto/reload 의 기본 대기(load)는 외부 폰트까지 기다리므로, 그보다 401 이 먼저 오면
 * 그 이동이 대기 중인 탐색을 끊어 ERR_ABORTED 가 난다(SYM-169). 응답 도착(commit)까지만
 * 기다리고, 끊긴 경우는 삼킨다. 다른 오류는 그대로 던진다.
 */
export async function navigateExpectingRedirect(page: Page, go: (p: Page) => Promise<unknown>) {
  try {
    await go(page);
  } catch (e) {
    if (!String(e).includes("ERR_ABORTED")) throw e;
  }
}

export const commit = { waitUntil: "commit" } as const;
