/**
 * TC ID 자동 채우기의 순번 계산.
 *
 * 그리드에서 떼어내 순수 함수로 둔다. 규칙을 바꿀 때 테스트로 먼저 확인하기 위해서다.
 */

/** TC ID 는 "PREFIX-NNN" 꼴로 본다. `.+-` 가 greedy 라 "TC-2026-001" 은 prefix "TC-2026-" 로 갈린다. */
export const TC_ID_PATTERN = /^(.+-)(\d+)$/;

export interface TcIdSeed {
  prefix: string;
  startNum: number;
  numWidth: number;
  /** 선택 구간에서 몇 번째부터 채울지. 첫 행이 기준점이면 1, 아니면 0 */
  fillFrom: number;
}

/**
 * 기준점을 정한다.
 * 1순위 선택 첫 행의 TC ID (이 행은 기준이라 그대로 두고 다음 행부터 채운다)
 * 2순위 선택 구간 바로 위쪽에서 가장 가까운 TC ID
 * 3순위 시트에서 가장 많이 쓰인 접두사와 그 최대 번호
 */
export function resolveTcIdSeed(
  visibleIds: (string | null | undefined)[],
  firstSelectedIndex: number,
  /** 필터로 숨은 행까지 포함한 전체 목록. 3순위 폴백이 화면만 보고 판단하지 않도록. */
  allKnownIds: (string | null | undefined)[] = visibleIds
): TcIdSeed | null {
  const first = visibleIds[firstSelectedIndex]?.match(TC_ID_PATTERN);
  if (first) {
    return {
      prefix: first[1],
      startNum: parseInt(first[2], 10),
      numWidth: first[2].length,
      fillFrom: 1,
    };
  }

  for (let i = firstSelectedIndex - 1; i >= 0; i--) {
    const m = visibleIds[i]?.match(TC_ID_PATTERN);
    if (m) {
      return {
        prefix: m[1],
        startNum: parseInt(m[2], 10),
        numWidth: m[2].length,
        fillFrom: 0,
      };
    }
  }

  const top = dominantTcIdPrefix(allKnownIds);
  if (!top) return null;

  return { prefix: top.prefix, startNum: top.maxNum, numWidth: top.numWidth, fillFrom: 0 };
}

/**
 * 목록에서 가장 많이 쓰인 접두사와 그 최대 번호를 찾는다.
 * 새 행에 붙일 TC ID 를 정할 때도 쓴다.
 */
export function dominantTcIdPrefix(
  allIds: (string | null | undefined)[]
): { prefix: string; maxNum: number; numWidth: number } | null {
  const freq = new Map<string, { count: number; max: number; width: number }>();
  for (const id of allIds) {
    const m = id?.match(TC_ID_PATTERN);
    if (!m) continue;
    const cur = freq.get(m[1]) || { count: 0, max: 0, width: m[2].length };
    cur.count++;
    cur.max = Math.max(cur.max, parseInt(m[2], 10));
    freq.set(m[1], cur);
  }
  const top = [...freq.entries()].sort((a, b) => b[1].count - a[1].count)[0];
  if (!top) return null;
  return { prefix: top[0], maxNum: top[1].max, numWidth: top[1].width };
}

/**
 * 채울 값을 계산한다. 반환은 allIds 기준 인덱스와 새 TC ID 의 짝이고,
 * 값이 그대로인 행은 빠진다.
 */
export function planTcIdFill(
  visibleIds: (string | null | undefined)[],
  selectedIndices: number[],
  allKnownIds: (string | null | undefined)[] = visibleIds
): { index: number; tcId: string }[] | null {
  if (selectedIndices.length === 0) return [];
  const seed = resolveTcIdSeed(visibleIds, selectedIndices[0], allKnownIds);
  if (!seed) return null;

  const out: { index: number; tcId: string }[] = [];
  let num = seed.startNum;
  for (let k = seed.fillFrom; k < selectedIndices.length; k++) {
    num++;
    const idx = selectedIndices[k];
    const tcId = seed.prefix + String(num).padStart(seed.numWidth, "0");
    if (visibleIds[idx] === tcId) continue;
    out.push({ index: idx, tcId });
  }
  return out;
}

/**
 * 새로 붙일 TC ID 가 손대지 않는 행과 겹치는지 본다.
 * 필터로 숨은 행까지 넘겨야 의미가 있다. 화면에 보이는 행만 넘기면
 * 숨은 행과의 충돌을 놓친다.
 */
export function findTcIdCollisions(
  assigned: { key: string | number; tcId: string }[],
  allRows: { key: string | number; tcId?: string | null }[]
): string[] {
  const touched = new Set(assigned.map((a) => a.key));
  const outside = new Set(
    allRows.filter((r) => !touched.has(r.key)).map((r) => r.tcId).filter(Boolean)
  );
  return assigned.map((a) => a.tcId).filter((id) => outside.has(id));
}
