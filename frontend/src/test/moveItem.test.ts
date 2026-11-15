import { describe, it, expect } from "vitest";
import { moveItem } from "../utils/moveItem";

const L = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }];
const ids = (l: { id: number }[] | null) => l?.map((x) => x.id) ?? null;

describe("moveItem (SYM-228)", () => {
  it("대상의 앞이나 뒤로 옮긴다", () => {
    expect(ids(moveItem(L, 4, 1, false))).toEqual([4, 1, 2, 3]);
    expect(ids(moveItem(L, 1, 4, true))).toEqual([2, 3, 4, 1]);
    expect(ids(moveItem(L, 1, 3, false))).toEqual([2, 1, 3, 4]);
    expect(ids(moveItem(L, 3, 1, true))).toEqual([1, 3, 2, 4]);
  });

  it("자리가 그대로면 null", () => {
    expect(moveItem(L, 2, 2, true)).toBeNull();
    expect(moveItem(L, 1, 2, false)).toBeNull();
    expect(moveItem(L, 2, 1, true)).toBeNull();
  });

  it("없는 id 면 null 이고 원본을 바꾸지 않는다", () => {
    expect(moveItem(L, 9, 1, false)).toBeNull();
    expect(moveItem(L, 1, 9, false)).toBeNull();
    expect(ids(L)).toEqual([1, 2, 3, 4]);
  });
});
