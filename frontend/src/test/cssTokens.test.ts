import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * 정의되지 않은 CSS 변수를 폴백 없이 참조하면 그 속성은 통째로 무효가 된다.
 * background-color 라면 initial 값인 transparent 가 되므로, 흰 글씨를 얹은
 * 선택 상태 버튼이 흰 배경 위에서 사라진다(대시보드 날짜 필터 "전체" 버튼).
 * 타입 체크도 린트도 문자열 안을 보지 않아 잡지 못하므로 테스트로 막는다.
 *
 * 폴백이 있는 `var(--x, #DC2626)` 형태는 값이 살아 있으므로 대상이 아니다.
 *
 * 소스를 fs 로 읽는다. import.meta.glob 은 쓸 수 없다. vite.config.ts 가
 * test.css 를 false 로 두어 vitest 가 CSS 를 빈 모듈로 만들고, `?raw` 로 요청해도
 * 빈 문자열이 와서 선언을 하나도 못 읽는다(그래도 아래 수집 가드에는 걸린다).
 *
 * 그 대신 타입 관할을 tsconfig.node.json 으로 옮겼다. tsconfig.app.json 은
 * types 를 vite/client 와 vitest/globals 로 제한해 src 아래에 node 타입이 없어서,
 * 여기서 fs 를 쓰면 vitest 는 통과하는데 tsc -b 가 죽는다.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..");
const SOURCE_EXT = [".ts", ".tsx", ".css"];

function collectFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "__pycache__") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...collectFiles(full));
    else if (SOURCE_EXT.includes(path.extname(entry.name))) out.push(full);
  }
  return out;
}

const files = collectFiles(SRC);

/** index.css 등에서 `--토큰:` 으로 실제 선언된 이름 */
function definedTokens(): Set<string> {
  const defined = new Set<string>();
  for (const file of files.filter((f) => f.endsWith(".css"))) {
    const text = fs.readFileSync(file, "utf-8");
    for (const m of text.matchAll(/(--[A-Za-z0-9_-]+)\s*:/g)) defined.add(m[1]);
  }
  return defined;
}

/**
 * 폴백 없이 참조된 `var(--토큰)` 을 파일·줄 정보와 함께 모은다.
 * 줄 단위로 끊지 않고 파일 전체를 훑는다. 인라인 style 객체는 줄바꿈이 잦아
 * 여는 괄호와 토큰 이름이 다른 줄에 놓일 수 있고, 줄 단위 스캔은 그것을 놓친다.
 *
 * 한계: 토큰 이름을 런타임에 조립하는 참조는 정적으로 볼 수 없다.
 * 이 프로젝트는 이름을 전부 리터럴로 쓰므로 지금은 걸리는 것이 없다.
 */
function referencesWithoutFallback(): { token: string; where: string }[] {
  const refs: { token: string; where: string }[] = [];
  for (const file of files) {
    const rel = path.relative(SRC, file).replace(/\\/g, "/");
    const text = fs.readFileSync(file, "utf-8");
    for (const m of text.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*\)/g)) {
      const line = text.slice(0, m.index).split("\n").length;
      refs.push({ token: m[1], where: `${rel}:${line}` });
    }
  }
  return refs;
}

/** 폴백 유무와 무관하게 참조된 모든 `var(--토큰)` */
function allReferences(): { token: string; where: string }[] {
  const refs: { token: string; where: string }[] = [];
  for (const file of files) {
    const rel = path.relative(SRC, file).replace(/\\/g, "/");
    // 이 파일 자신의 예시 토큰은 대상이 아니다.
    if (rel.startsWith("test/")) continue;
    const text = fs.readFileSync(file, "utf-8");
    for (const m of text.matchAll(/var\(\s*(--[A-Za-z0-9_-]+)\s*[,)]/g)) {
      const line = text.slice(0, m.index).split("\n").length;
      refs.push({ token: m[1], where: `${rel}:${line}` });
    }
  }
  return refs;
}

describe("CSS 커스텀 프로퍼티", () => {
  it("소스가 참조하는 토큰은 모두 선언돼 있다", () => {
    const defined = definedTokens();
    const missing = referencesWithoutFallback().filter(
      (r) => !defined.has(r.token),
    );
    expect(
      missing.map((r) => `${r.where} -> ${r.token}`),
      "선언되지 않은 토큰을 폴백 없이 참조했다. 속성이 통째로 무효가 된다",
    ).toEqual([]);
  });

  it("폴백이 달려 있어도 토큰 이름은 선언돼 있다", () => {
    // ★폴백이 있으면 글자가 사라지지는 않지만, 그 값은 한 테마 전용 고정색이라
    //   다크모드에서 대비가 무너진다. 실제로 `--danger` 3곳이 라이트 전용
    //   #DC2626 으로 굳어 있었다(선언된 이름은 `--text-danger` 다).
    //   이름이 틀렸다는 사실 자체가 폴백에 가려 드러나지 않는다.
    const defined = definedTokens();
    const missing = allReferences().filter((r) => !defined.has(r.token));
    expect(
      missing.map((r) => `${r.where} -> ${r.token}`),
      "선언되지 않은 토큰이다. 폴백 값으로만 그려져 테마를 따르지 않는다",
    ).toEqual([]);
  });

  it("소스 수집이 실제로 동작한다", () => {
    // 위 단언이 빈 집합끼리 비교해 늘 통과하는 상태를 막는 가드.
    // 파일을 하나도 못 읽어도 missing 은 빈 배열이라 조용히 초록이 된다.
    expect(files.length).toBeGreaterThan(50);
    const defined = definedTokens();
    expect(defined.has("--accent")).toBe(true);
    expect(defined.has("--bg-card")).toBe(true);
    expect(referencesWithoutFallback().length).toBeGreaterThan(50);
  });
});


/**
 * 토큰 값끼리의 명암비. jsdom 은 CSS 변수를 풀어 주지 않아 axe 가 이 조합을 못 본다.
 * 그래서 index.css 를 직접 읽어 WCAG 상대휘도로 잰다.
 *
 * ★한계: 토큰 값이 `#RRGGBB` 인 것만 읽는다. 다크의 `--bg-*-light` 는 rgba() 라
 *   배경으로 쓸 수 없고, 토큰을 거치지 않고 하드코딩한 색(ag-grid 오버라이드 등)도
 *   대상 밖이다. "검사가 있으니 됐다" 고 읽지 말 것.
 *
 * 실측 2026-09-18: 다크의 선택 상태(--accent 에 --accent-text)가 4.31:1 로 일반
 * 텍스트 AA(4.5:1)에 못 미쳤고(SYM-55), 오류 문구(--text-danger)는 카드 배경에서
 * 4.42:1, 입력 배경에서 4.02:1 이었다(SYM-56). 두 이슈 모두 "검사가 없어서" 남아
 * 있었다. 값만 고치면 다음에 또 어긋나므로 여기서 막는다.
 */
const THEME_BLOCKS = {
  라이트: /:root\s*\{([\s\S]*?)\}/,
  다크: /\[data-theme="dark"\]\s*\{([\s\S]*?)\}/,
} as const;

/** 텍스트 색과 배경 색의 조합. 일반 텍스트라 4.5:1 이 기준이다. */
const TEXT_ON_BG: { fg: string; bg: string; 설명: string }[] = [
  { fg: "accent-text", bg: "accent", 설명: "선택 상태 버튼과 탭" },
  { fg: "text-danger", bg: "bg-card", 설명: "카드 위 오류 문구" },
  { fg: "text-danger", bg: "bg-input", 설명: "입력 옆 오류 문구" },
  { fg: "text-primary", bg: "bg-card", 설명: "카드 본문" },
  { fg: "text-secondary", bg: "bg-card", 설명: "카드 보조 문구" },
  // ReportView 의 결과 건수 셀(:266-276)이 이 넷을 글자색으로 쓴다.
  { fg: "color-fail", bg: "bg-card", 설명: "FAIL 건수와 위험 문구" },
  { fg: "color-fail", bg: "bg-input", 설명: "입력 영역의 FAIL 표시" },
  { fg: "color-pass", bg: "bg-card", 설명: "PASS 건수" },
  { fg: "color-block", bg: "bg-card", 설명: "BLOCK 건수" },
  { fg: "color-na", bg: "bg-card", 설명: "N/A 건수" },
  { fg: "color-ns", bg: "bg-card", 설명: "미수행 건수" },
  { fg: "color-link", bg: "bg-card", 설명: "본문 링크" },
  { fg: "text-success", bg: "bg-card", 설명: "성공 안내" },
  { fg: "text-warning", bg: "bg-card", 설명: "주의 안내" },
  { fg: "text-info", bg: "bg-card", 설명: "정보 안내" },
  { fg: "text-badge-gray", bg: "bg-card", 설명: "회색 배지 글자" },
  // 헤더는 배경이 따로다. 카드 기준으로 재면 흰 글자가 늘 미달로 나온다.
  { fg: "text-header", bg: "bg-header", 설명: "헤더 글자" },
  { fg: "text-header-secondary", bg: "bg-header", 설명: "헤더 보조 글자" },
  // TC 관리와 테스트 수행 그리드의 우선순위 칸. 행 hover·선택 상태는 아래 그리드 검사가 본다.
  { fg: "priority-critical", bg: "bg-card", 설명: "우선순위 매우 높음" },
  { fg: "priority-high", bg: "bg-card", 설명: "우선순위 높음" },
  { fg: "priority-normal", bg: "bg-card", 설명: "우선순위 보통" },
  { fg: "priority-low", bg: "bg-card", 설명: "우선순위 낮음" },
];

/**
 * 글자색으로 쓰이지 않는 토큰. 여기에 없고 TEXT_ON_BG 에도 없는 `--text-*` /
 * `--color-*` 토큰이 생기면 아래 인벤토리 단언이 실패한다.
 *
 * ★목록을 손으로 관리하면 새 토큰이 조용히 검사 밖으로 빠진다. SYM-54 가 넣은
 *   미선언 토큰 검사가 "폴백 있는 참조" 를 놓쳐 SYM-56 이 살아남았고, 그 SYM-56 을
 *   고치면서도 같은 값을 쓰던 --color-fail 을 놓쳤다. 같은 실수를 세 번 하지
 *   않으려고 목록 자체를 강제한다.
 */
const NOT_TEXT_TOKENS = new Set([
  "color-ns-accent",   // 악센트 막대 전용. CSS 주석에 그렇게 적혀 있다
]);

function themeTokens(theme: keyof typeof THEME_BLOCKS): Record<string, string> {
  const css = fs.readFileSync(path.join(SRC, "index.css"), "utf-8");
  const m = css.match(THEME_BLOCKS[theme]);
  expect(m, `${theme} 테마 블록을 못 찾았다`).toBeTruthy();
  const out: Record<string, string> = {};
  for (const d of m![1].matchAll(/--([A-Za-z0-9_-]+):\s*(#[0-9A-Fa-f]{6})/g)) out[d[1]] = d[2];
  return out;
}

function relativeLuminance(hex: string): number {
  const v = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = v.map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function contrast(a: string, b: string): number {
  const [la, lb] = [relativeLuminance(a), relativeLuminance(b)];
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

describe("테마 토큰의 명암비", () => {
  it.each(Object.keys(THEME_BLOCKS) as (keyof typeof THEME_BLOCKS)[])(
    "%s 테마의 글자와 배경이 AA(4.5:1)를 넘는다",
    (theme) => {
      const t = themeTokens(theme);
      const 미달: string[] = [];

      for (const { fg, bg, 설명 } of TEXT_ON_BG) {
        const f = t[fg];
        const b = t[bg];
        expect(f, `${theme} 에 --${fg} 가 없다`).toBeTruthy();
        expect(b, `${theme} 에 --${bg} 가 없다`).toBeTruthy();
        const r = contrast(f, b);
        if (r < 4.5) 미달.push(`${설명}: --${fg} ${f} on --${bg} ${b} = ${r.toFixed(2)}:1`);
      }

      expect(미달, "AA 4.5:1 에 못 미치는 조합 - " + 미달.join(" / ")).toEqual([]);
    },
  );

  it("글자색 토큰이 검사 목록 밖으로 새지 않는다", () => {
    // 새 토큰이 늘면 사람이 목록을 고치도록 강제한다. 값이 맞는지가 아니라
    // "누가 검사 대상인지" 를 정하는 일을 잊지 않게 하는 것이 목적이다.
    const covered = new Set(TEXT_ON_BG.map((c) => c.fg));
    const 샌_것: string[] = [];

    for (const theme of Object.keys(THEME_BLOCKS) as (keyof typeof THEME_BLOCKS)[]) {
      for (const name of Object.keys(themeTokens(theme))) {
        if (!/^(text|color|priority)-/.test(name)) continue;
        if (covered.has(name) || NOT_TEXT_TOKENS.has(name)) continue;
        샌_것.push(`${theme}:--${name}`);
      }
    }

    expect(
      [...new Set(샌_것)],
      "글자색으로 쓰는 토큰이면 TEXT_ON_BG 에, 아니면 NOT_TEXT_TOKENS 에 넣어라",
    ).toEqual([]);
  });

  it.each(Object.keys(THEME_BLOCKS) as (keyof typeof THEME_BLOCKS)[])(
    "%s 테마: 그리드 행 hover·선택 상태에서도 우선순위 글자가 4.5:1 을 넘는다",
    (theme) => {
      // 그리드는 카드 배경 위에 반투명 파랑을 덧씌운다. 값은 테마별 그리드 블록의
      // --ag-row-hover-color 와 --ag-selected-row-background-color 에서 읽는다.
      // ★다크는 그리드 전용 값을 따로 둔다([data-theme="dark"] .ag-theme-alpine).
      //   파일 전체에서 첫 선언을 읽으면 다크 검사가 라이트 값을 보게 된다(QA1 지적).
      // 예전 고정색은 다크 "보통" 이 카드 위에서부터 3.22:1 이었다.
      const css = fs.readFileSync(path.join(SRC, "index.css"), "utf-8");
      const tokenBlock = css.match(THEME_BLOCKS[theme])![1];
      const GRID_BLOCKS = {
        라이트: /(?:^|\n)\.ag-theme-alpine,\s*\.ag-theme-quartz\s*\{([\s\S]*?)\}/,
        다크: /\[data-theme="dark"\]\s+\.ag-theme-alpine,\s*\[data-theme="dark"\]\s+\.ag-theme-quartz\s*\{([\s\S]*?)\}/,
      } as const;
      const gridBlock = css.match(GRID_BLOCKS[theme]);
      expect(gridBlock, `${theme} 그리드 블록을 못 찾았다`).toBeTruthy();
      const decl = (src: string, name: string) =>
        src.match(new RegExp(`--${name}:\\s*([^;]+);`))?.[1].trim();
      const rgba = (name: string) => {
        let v = decl(gridBlock![1], name);
        expect(v, `${theme} 그리드 블록에 --${name} 이 없다`).toBeTruthy();
        const ref = v!.match(/^var\(--([A-Za-z0-9_-]+)\)$/);
        if (ref) v = decl(tokenBlock, ref[1]);   // var(--primary-light) 는 테마 토큰으로 푼다
        const m = v?.match(/^rgba\(([^)]+)\)$/);
        expect(m, `--${name} 값을 rgba 로 풀지 못했다: ${v}`).toBeTruthy();
        const [r, g, b, a] = m![1].split(",").map((x) => parseFloat(x));
        return { rgb: [r, g, b], a };
      };
      const hover = rgba("ag-row-hover-color");
      const selected = rgba("ag-selected-row-background-color");
      const toHex = (c: number[]) => "#" + c.map((x) => Math.round(x).toString(16).padStart(2, "0")).join("");
      const over = (base: number[], o: { rgb: number[]; a: number }) =>
        base.map((v, i) => o.rgb[i] * o.a + v * (1 - o.a));
      const t = themeTokens(theme);
      const card = [1, 3, 5].map((i) => parseInt(t["bg-card"].slice(i, i + 2), 16));
      const backgrounds = {
        hover: toHex(over(card, hover)),
        selected: toHex(over(card, selected)),
        "selected+hover": toHex(over(over(card, selected), hover)),
      };
      const 미달: string[] = [];
      for (const fg of ["priority-critical", "priority-high", "priority-normal", "priority-low"]) {
        expect(t[fg], `${theme} 테마에 --${fg} 가 없다`).toBeTruthy();
        for (const [state, bg] of Object.entries(backgrounds)) {
          const r = contrast(t[fg], bg);
          if (r < 4.5) 미달.push(`--${fg} on ${state} ${r.toFixed(2)}`);
        }
      }
      expect(미달, "AA 4.5:1 미달 - " + 미달.join(" / ")).toEqual([]);
    },
  );

  it("검사기가 실제로 미달을 잡는다", () => {
    // 이 계산이 맞는지 확인한다. 회색 위 회색은 어느 기준으로도 미달이다.
    expect(contrast("#777777", "#888888")).toBeLessThan(4.5);
    expect(contrast("#000000", "#FFFFFF")).toBeCloseTo(21, 0);
  });
});
