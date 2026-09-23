import type { CellClassParams, CellStyle } from "ag-grid-community";

/**
 * 우선순위 값(DB 에 저장되는 한글)과 글자색.
 *
 * TC 관리 그리드와 테스트 수행 그리드가 같이 쓴다. 두 곳이 각자 들고 있으면 한쪽만
 * 고쳤을 때 같은 TC 가 두 화면에서 다른 색으로 보인다.
 */
// 4단계다. "매우 낮음" 은 쓰지 않는다(의미 없는 TC 라 두지 않는다).
export const PRIORITY_OPTIONS = ["매우 높음", "높음", "보통", "낮음"];

export const PRIORITY_COLORS: Record<string, string> = {
  "매우 높음": "#DC2626",
  "높음": "#EA580C",
  "보통": "#2563EB",
  "낮음": "#16A34A",
};

/** 목록에 없는 값(자유 입력으로 들어온 High, 중간 등)은 색을 입히지 않는다. */
export function priorityCellStyle(params: CellClassParams): CellStyle {
  const color = PRIORITY_COLORS[params.value as string];
  return color ? { color, fontWeight: 600 } : {};
}

/** 화면 표시 이름. 번역은 testcase 네임스페이스의 priorityDisplay 를 쓴다. */
export function priorityDisplayMap(t: (key: string, fallback: string) => string): Record<string, string> {
  return Object.fromEntries(PRIORITY_OPTIONS.map((p) => [p, t(`priorityDisplay.${p}`, p)]));
}
