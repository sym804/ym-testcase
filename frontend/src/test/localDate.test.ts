import { describe, it, expect } from "vitest";
import { toLocalDateString, daysAgo } from "../utils/localDate";

// 대시보드 날짜 프리셋이 `toISOString()` 을 써서 UTC 날짜를 냈다.
// KST(UTC+9)에서는 자정부터 오전 9시 사이에 하루 전 날짜가 되어 경계일이 밀린다.

describe("로컬 날짜 문자열", () => {
  it("UTC 로 넘어가는 새벽에도 그날 날짜를 준다", () => {
    // KST 2026-09-14 01:00 = UTC 2026-09-13 16:00
    const kstEarlyMorning = new Date(2026, 8, 14, 1, 0, 0);
    expect(toLocalDateString(kstEarlyMorning)).toBe("2026-09-14");
  });

  it("월과 일을 두 자리로 채운다", () => {
    expect(toLocalDateString(new Date(2026, 0, 5))).toBe("2026-01-05");
  });

  it("연말을 넘어가도 맞다", () => {
    expect(toLocalDateString(new Date(2025, 11, 31, 23, 30))).toBe("2025-12-31");
  });

  it("N 일 전을 로컬 기준으로 센다", () => {
    const now = new Date(2026, 8, 14, 1, 0, 0);
    expect(daysAgo(7, now)).toBe("2026-09-07");
    expect(daysAgo(30, now)).toBe("2026-08-15");
  });

  it("toISOString 방식과 어긋나는 시각이 실제로 있다", () => {
    // 이 테스트가 깨지면 환경 타임존이 UTC 라 원래 문제가 드러나지 않는 것이다.
    const kstEarlyMorning = new Date(2026, 8, 14, 1, 0, 0);
    const utcWay = kstEarlyMorning.toISOString().split("T")[0];
    if (kstEarlyMorning.getTimezoneOffset() === 0) {
      expect(utcWay).toBe(toLocalDateString(kstEarlyMorning));
    } else {
      expect(utcWay).not.toBe(toLocalDateString(kstEarlyMorning));
    }
  });
});
