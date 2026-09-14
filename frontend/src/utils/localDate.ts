/**
 * 브라우저 로컬 기준의 `YYYY-MM-DD`.
 *
 * ★`toISOString().split("T")[0]` 을 쓰면 UTC 날짜가 나온다. KST(UTC+9)에서는
 *   자정부터 오전 9시 사이에 하루 전 날짜가 되어, 대시보드 날짜 프리셋의
 *   경계일이 밀린다. 백엔드는 이 값을 그대로 로컬 시각으로 읽으므로
 *   (`datetime.fromisoformat`) 화면과 같은 기준이어야 한다.
 */
export function toLocalDateString(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** 오늘로부터 `days` 일 전의 로컬 날짜 */
export function daysAgo(days: number, now: Date = new Date()): string {
  const d = new Date(now.getTime() - days * 86400000);
  return toLocalDateString(d);
}
