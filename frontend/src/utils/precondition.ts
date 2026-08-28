// 사전조건 셀의 "<TC-ID> 의 사전조건 [1~N] 참조" 표기를 해석한다.
// 참조는 체인이 될 수 있어(FS-04 -> FS-02 -> FS-01 -> REC-API-01) 재귀로 펼친다.

/** 참조 문구. 셀 전체이거나 "1. " 로 시작하는 첫 항목으로 나타난다. */
const REF_RE = /^([A-Za-z][A-Za-z0-9_-]*)\s*의\s*사전조건(?:\s*1~(\d+))?\s*참조\s*$/;

export interface PreconditionRef {
  /** 참조 대상 TC ID */
  targetId: string;
  /** 1~N 의 N. 범위 표기가 없으면 undefined (대상 전체를 가리킨다) */
  upto?: number;
  /** 원문에서 참조 문구가 차지하는 구간 */
  text: string;
}

/**
 * 사전조건 원문을 번호 항목 단위로 쪼갠다.
 * 번호로 시작하지 않는 줄은 직전 항목의 이어지는 줄로 붙인다.
 * 번호 항목이 하나도 없으면 원문 전체를 항목 1개로 본다.
 */
export function splitItems(raw: string): string[] {
  const text = (raw ?? "").trim();
  if (!text) return [];
  const items: string[] = [];
  let cur: string | null = null;
  for (const line of text.split("\n")) {
    if (/^\d+\.\s/.test(line)) {
      if (cur !== null) items.push(cur);
      cur = line.replace(/^\d+\.\s*/, "");
    } else if (cur === null) {
      cur = line;
    } else {
      cur += "\n" + line;
    }
  }
  if (cur !== null) items.push(cur);
  return items;
}

/** 항목 하나가 참조 문구이면 그 정보를 돌려준다. */
export function parseRef(item: string): PreconditionRef | null {
  const m = REF_RE.exec(item.trim());
  if (!m) return null;
  return { targetId: m[1], upto: m[2] ? Number(m[2]) : undefined, text: item.trim() };
}

/** 셀 원문에 참조가 들어 있는지 (렌더 경로를 가르는 데 쓴다) */
export function hasRef(raw: string): boolean {
  return splitItems(raw).some((it) => parseRef(it) !== null);
}

/**
 * TC 의 사전조건을 참조 없는 항목 목록으로 펼친다.
 * @param index tc_id -> precondition 원문
 * @returns 펼친 항목 목록. 대상이 없거나 순환이면 안내 문구 1줄.
 */
export function resolveItems(
  tcId: string,
  index: Map<string, string>,
  seen: Set<string> = new Set(),
): string[] {
  if (seen.has(tcId)) return [`(순환 참조: ${tcId})`];
  const raw = index.get(tcId);
  if (raw === undefined) return [`(참조 대상을 찾을 수 없음: ${tcId})`];

  const next = new Set(seen);
  next.add(tcId);

  const out: string[] = [];
  for (const item of splitItems(raw)) {
    const ref = parseRef(item);
    if (!ref) {
      out.push(item);
      continue;
    }
    const resolved = resolveItems(ref.targetId, index, next);
    out.push(...(ref.upto !== undefined ? resolved.slice(0, ref.upto) : resolved));
  }
  return out;
}

/** 호버 팝업에 띄울 내용: 참조 대상의 펼친 항목과 헤더 문구 */
export function resolveRef(
  ref: PreconditionRef,
  index: Map<string, string>,
): { title: string; items: string[] } {
  const all = resolveItems(ref.targetId, index);
  const items = ref.upto !== undefined ? all.slice(0, ref.upto) : all;
  const title = ref.upto !== undefined ? `${ref.targetId} 사전조건 1~${ref.upto}` : `${ref.targetId} 사전조건`;
  return { title, items };
}
