/**
 * 이슈 링크 칸의 값을 이동할 주소로 바꾼다. 이동할 곳이 없으면 null.
 *
 * - http(s) 주소는 그대로 쓴다.
 * - `PROJ-123` 같은 이슈 키는 프로젝트의 Jira Base URL 뒤에 `/browse/키` 로 붙인다.
 *   매뉴얼 두 곳이 Base URL 을 `/browse/` 포함과 미포함 두 모양으로 안내하고 있어
 *   둘 다 받는다.
 * - 그 밖의 값은 null 이다. 예전에는 `href="#"` 로 걸어서 눌러도 아무 일이 없었다.
 *
 * `javascript:` 같은 주소가 링크가 되지 않도록 http(s) 만 통과시킨다.
 */
const HTTP = /^https?:\/\//i;
const ISSUE_KEY = /^[A-Za-z][A-Za-z0-9_]*-\d+$/;

export function resolveIssueUrl(link: string | null | undefined, jiraBaseUrl?: string | null): string | null {
  const value = (link ?? "").trim();
  if (!value) return null;
  if (HTTP.test(value)) return value;

  const base = (jiraBaseUrl ?? "").trim();
  if (!ISSUE_KEY.test(value) || !HTTP.test(base)) return null;

  const trimmed = base.replace(/\/+$/, "");
  const prefix = /\/browse$/i.test(trimmed) ? trimmed : `${trimmed}/browse`;
  return `${prefix}/${encodeURIComponent(value)}`;
}
