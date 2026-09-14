/**
 * 행의 값을 컬럼 id 로 읽고 쓴다.
 *
 * 커스텀 필드 컬럼은 field 가 `cf_<이름>` 이고 실제 값은 `data.custom_fields[이름]`
 * 에 있다(컬럼 정의의 valueGetter/valueSetter). 그래서 `data[field]` 로 바로
 * 대입하면 화면 값이 바뀌지 않고, 저장 페이로드의 `cf_이름` 키는 백엔드 스키마에
 * 없어 조용히 버려진다. 그런데도 "N개 채움" 토스트는 떠서 된 줄 알게 된다.
 *
 * Ctrl+D 채우기와 undo/redo 두 곳이 각자 `data[field]` 를 쓰고 있었다.
 * 한 곳만 고치면 다른 쪽이 다시 어긋나므로 여기로 모은다.
 */

const CF_PREFIX = "cf_";

type Row = Record<string, unknown> & { custom_fields?: Record<string, unknown> | null };

/** 커스텀 필드 컬럼이면 그 필드 이름, 아니면 null */
function customFieldName(field: string): string | null {
  return field.startsWith(CF_PREFIX) ? field.slice(CF_PREFIX.length) : null;
}

export function readRowField(data: Row, field: string): unknown {
  const name = customFieldName(field);
  if (name !== null) return data.custom_fields?.[name] ?? "";
  return data[field];
}

export function writeRowField(data: Row, field: string, value: unknown): void {
  const name = customFieldName(field);
  if (name !== null) {
    if (!data.custom_fields) data.custom_fields = {};
    data.custom_fields[name] = value;
    return;
  }
  data[field] = value;
}
