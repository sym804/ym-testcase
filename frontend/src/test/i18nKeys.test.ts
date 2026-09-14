import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * `t("키")` 로 부르는데 로케일 파일에 그 키가 없으면, i18next 는 빈 문자열이
 * 아니라 **키 문자열 자체**를 돌려준다. 그래서 화면에 `saveFailed` 같은 날것이
 * 그대로 뜬다. `fallbackNS` 설정이 없어 common 으로 넘어가지도 않는다.
 *
 * 타입 체크도 린트도 문자열 안을 보지 않으므로 여기서 막는다.
 * cssTokens.test.ts 와 같은 자리, 같은 방식이다.
 *
 * 한계: 이름을 런타임에 조립하는 키(`t(`fieldType_${k}`)`)는 정적으로 볼 수 없다.
 * 그런 자리는 DYNAMIC_PREFIXES 에 접두사를 적어 두고 사람이 따로 확인한다.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..");
const I18N = path.join(SRC, "i18n");

/** 런타임에 조립하는 키의 접두사. 이 접두사로 시작하는 정의는 미사용으로 보지 않는다. */
const DYNAMIC_PREFIXES = ["fieldType_", "troubleshoot.", "tabs.", "priority.", "platform."];

function collectSources(dir: string): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "__pycache__") continue;
    if (entry.name === "i18n" || entry.name === "test") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...collectSources(full));
    else if ([".ts", ".tsx"].includes(path.extname(entry.name))) out.push(full);
  }
  return out;
}

function flatten(obj: Record<string, unknown>, prefix = ""): string[] {
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const full = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      keys.push(...flatten(v as Record<string, unknown>, full));
    } else {
      keys.push(full);
    }
  }
  return keys;
}

/** `네임스페이스:키` 형태의 정의 집합 */
function definedKeys(lang: string): Set<string> {
  const dir = path.join(I18N, lang);
  const defined = new Set<string>();
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith(".json"))) {
    const ns = file.replace(/\.json$/, "");
    const json = JSON.parse(fs.readFileSync(path.join(dir, file), "utf-8"));
    for (const key of flatten(json)) defined.add(`${ns}:${key}`);
  }
  return defined;
}

const NAMESPACES = fs
  .readdirSync(path.join(I18N, "ko"))
  .filter((f) => f.endsWith(".json"))
  .map((f) => f.replace(/\.json$/, ""));

/** 소스에서 `t("리터럴")` 호출을 파일이 선언한 네임스페이스와 함께 모은다. */
function literalCalls(): { key: string; where: string; namespaces: string[] }[] {
  const calls: { key: string; where: string; namespaces: string[] }[] = [];
  for (const file of collectSources(SRC)) {
    const rel = path.relative(SRC, file).replace(/\\/g, "/");
    const text = fs.readFileSync(file, "utf-8");

    const declared = [...text.matchAll(/useTranslation\(\s*\[?\s*["']([^"']+)["']/g)]
      .map((m) => m[1]);

    for (const m of text.matchAll(/\bt\(\s*["']([^"']+)["']/g)) {
      const line = text.slice(0, m.index).split("\n").length;
      calls.push({ key: m[1], where: `${rel}:${line}`, namespaces: declared });
    }
  }
  return calls;
}

function isDynamic(key: string): boolean {
  return DYNAMIC_PREFIXES.some((p) => key.startsWith(p));
}

function missingFor(lang: string): string[] {
  const defined = definedKeys(lang);
  const missing: string[] = [];
  for (const call of literalCalls()) {
    if (isDynamic(call.key)) continue;
    // ★그 파일이 선언한 네임스페이스에서만 찾는다. 전체 네임스페이스를 폴백으로
    //   두면 다른 화면의 같은 이름 키에 걸려 통과해 버리는데, 런타임에는
    //   useTranslation 이 건 네임스페이스만 보므로 실제로는 raw key 가 뜬다
    //   (fallbackNS 설정이 없다).
    const scope = call.namespaces.length > 0 ? call.namespaces : NAMESPACES;
    const found = call.key.includes(":")
      ? defined.has(call.key)
      : scope.some((ns) => defined.has(`${ns}:${call.key}`));
    if (!found) missing.push(`${call.where} -> ${call.key}`);
  }
  return missing;
}

describe("i18n 키", () => {
  it("소스가 부르는 키는 한국어 로케일에 있다", () => {
    expect(
      missingFor("ko"),
      "정의되지 않은 키다. 화면에 키 문자열이 그대로 노출된다",
    ).toEqual([]);
  });

  it("소스가 부르는 키는 영어 로케일에도 있다", () => {
    expect(missingFor("en")).toEqual([]);
  });

  it("한국어와 영어의 키 집합이 같다", () => {
    const ko = definedKeys("ko");
    const en = definedKeys("en");
    expect([...ko].filter((k) => !en.has(k)), "영어에 없는 키").toEqual([]);
    expect([...en].filter((k) => !ko.has(k)), "한국어에 없는 키").toEqual([]);
  });

  it("수집이 실제로 동작한다", () => {
    // 빈 집합끼리 비교해 늘 초록이 되는 상태를 막는 가드.
    expect(NAMESPACES.length).toBeGreaterThan(10);
    expect(definedKeys("ko").size).toBeGreaterThan(1000);
    expect(literalCalls().length).toBeGreaterThan(500);
  });
});
