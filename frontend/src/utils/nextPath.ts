/**
 * 로그인 뒤 돌아갈 경로.
 *
 * 세션이 끊기거나 공유받은 링크로 들어오면 로그인 화면으로 보내는데, 원래 주소를 넘기지 않으면
 * 로그인 뒤 늘 프로젝트 목록으로 떨어진다. 서버의 safe_next(services/account_policy.py)와 같은
 * 규칙으로 사이트 안 경로만 받는다(열린 리디렉션 차단).
 */
const DEFAULT_NEXT = "/projects";
// eslint-disable-next-line no-control-regex
const BAD_PATH_CHARS = /[\\\x00-\x20\x7f]/;

export function safeNextPath(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || BAD_PATH_CHARS.test(raw)) return DEFAULT_NEXT;
  // 로그인 화면으로 다시 돌아가면 빙빙 돈다
  if (raw === "/login" || raw.startsWith("/login?") || raw.startsWith("/login/")) return DEFAULT_NEXT;
  return raw;
}

/** 지금 주소를 next 로 실은 로그인 주소. 목록 화면이면 붙이지 않는다. */
export function loginPathFor(pathname: string, search = "", hash = ""): string {
  const here = pathname + search + hash;
  const next = safeNextPath(here);
  if (next === DEFAULT_NEXT || pathname === "/") return "/login";
  return `/login?next=${encodeURIComponent(next)}`;
}
