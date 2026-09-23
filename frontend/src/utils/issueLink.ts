/**
 * 이슈 링크 칸의 값을 이동할 주소로 바꾼다. 이동할 곳이 없으면 null.
 *
 * - http(s) 주소는 그대로 쓴다.
 * - `PROJ-123` 같은 이슈 키는 프로젝트의 이슈 관리 도구 주소에 붙인다. 도구마다
 *   이슈 주소 모양이 달라 아래 차례로 정한다.
 *   1. 주소에 `{key}` 가 있으면 그 자리에 넣는다. 어떤 도구든 이 모양으로 적으면 된다
 *   2. `/browse` 나 `/issue` 로 끝나면 그 뒤에 붙인다
 *   3. Linear(`linear.app/워크스페이스`)는 `/issue/키`
 *   4. 그 밖은 Jira 로 보고 `/browse/키`. 예전부터 Jira 주소만 받던 설정과 호환된다
 * - 그 밖의 값은 null 이다. 예전에는 `href="#"` 로 걸어서 눌러도 아무 일이 없었다.
 *
 * `javascript:` 같은 주소가 링크가 되지 않도록 http(s) 만 통과시킨다.
 */
const HTTP = /^https?:\/\//i;
const ISSUE_KEY = /^[A-Za-z][A-Za-z0-9_]*-\d+$/;

export function resolveIssueUrl(link: string | null | undefined, trackerUrl?: string | null): string | null {
  const value = (link ?? "").trim();
  if (!value) return null;
  if (HTTP.test(value)) return value;

  const base = (trackerUrl ?? "").trim();
  if (!ISSUE_KEY.test(value) || !HTTP.test(base)) return null;

  const key = encodeURIComponent(value);
  if (base.includes("{key}")) return base.split("{key}").join(key);

  const trimmed = base.replace(/\/+$/, "");
  if (/\/(browse|issue)$/i.test(trimmed)) return `${trimmed}/${key}`;
  // 팀 화면 주소(linear.app/sym/team/SYM/active)를 그대로 붙여 넣는 경우가 많다.
  // 워크스페이스 이름까지만 남기고 /issue/키 를 붙인다.
  const linear = /^(https?:\/\/(?:www\.)?linear\.app\/[^/?#]+)/i.exec(trimmed);
  if (linear) return `${linear[1]}/issue/${key}`;
  return `${trimmed}/browse/${key}`;
}
