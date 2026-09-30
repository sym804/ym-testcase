/** 버전 묶음 키. 앞의 v 와 대소문자 · 공백을 무시한다("v1.5" 와 "1.5" 는 하나). 서버(dashboard.version_key)와 같은 규칙 */
export function versionKey(version: string | null | undefined): string {
  return (version ?? "").trim().toLowerCase().replace(/^v/, "");
}

/** 수행 목록에서 버전 묶음을 최근 수행 순으로 뽑는다. 표시는 그 묶음에서 가장 최근 수행의 표기다 */
export function versionGroups(runs: { version?: string | null; created_at: string }[]): { key: string; label: string }[] {
  const byKey = new Map<string, { label: string; latest: string }>();
  for (const r of runs) {
    const key = versionKey(r.version);
    const cur = byKey.get(key);
    if (!cur || r.created_at > cur.latest) byKey.set(key, { label: (r.version || "").trim(), latest: r.created_at });
  }
  return [...byKey.entries()]
    .sort((a, b) => (a[1].latest < b[1].latest ? 1 : -1))
    .map(([key, v]) => ({ key, label: v.label }));
}
