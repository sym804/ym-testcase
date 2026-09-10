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
