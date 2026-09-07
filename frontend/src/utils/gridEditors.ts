/**
 * agLargeTextCellEditor 공용 파라미터.
 *
 * AG Grid 는 maxLength 를 안 주면 textarea 에 maxlength="200" 을 박는다
 * (ag-grid-community: setMaxLength(maxLength || 200)).
 * 200자를 넘기면 입력도 붙여넣기도 조용히 잘린다.
 * 백엔드 컬럼은 Text 라 길이 제한이 없으므로 편집기 쪽 제한만 풀어 준다.
 */
export const LARGE_TEXT_EDITOR_PARAMS = {
  maxLength: 100000,
  rows: 20,
  cols: 80,
} as const;
