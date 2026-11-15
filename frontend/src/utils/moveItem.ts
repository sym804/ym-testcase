/**
 * fromId 를 toId 의 앞(after=false) 이나 뒤(after=true)로 옮긴 새 배열.
 * 자리가 그대로이거나 id 가 없으면 null 이다(저장 요청을 보내지 않으려고).
 */
export function moveItem<T extends { id: number }>(list: T[], fromId: number, toId: number, after: boolean): T[] | null {
  if (fromId === toId) return null;
  const moving = list.find((p) => p.id === fromId);
  if (!moving || !list.some((p) => p.id === toId)) return null;
  const rest = list.filter((p) => p.id !== fromId);
  const idx = rest.findIndex((p) => p.id === toId) + (after ? 1 : 0);
  const next = [...rest.slice(0, idx), moving, ...rest.slice(idx)];
  return next.every((p, i) => p.id === list[i].id) ? null : next;
}
