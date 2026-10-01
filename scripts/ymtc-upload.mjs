#!/usr/bin/env node
// YM TestCase 결과 업로드 CLI. 의존성 없이 Node 18+ 만으로 돈다(fetch · FormData 내장).
//
//   YMTC_API_KEY=ymtc_... node scripts/ymtc-upload.mjs --project 1 --run-name "Starfort e2e" results.json
//
// 수행 이름만 주면 서버가 같은 이름의 다음 회차를 만들어 기록한다(처음이면 R1).
// API 키는 환경변수로만 받는다. 인자로 받으면 CI 로그와 셸 이력에 남는다.
import { readFileSync, existsSync } from "node:fs";
import { basename } from "node:path";
import { parseArgs } from "node:util";

const HELP = `사용법: node scripts/ymtc-upload.mjs [옵션] <결과 파일>

결과 파일: Playwright JSON 리포트(--reporter=json) 또는 JUnit XML

필수
  --project <id>          프로젝트 id
  --run-name <이름>       수행 이름. 같은 이름의 회차에 이어 붙인다
  또는 --run-id <id>      이미 있는 수행에 바로 기록한다

선택
  --url <주소>            서버 주소 (기본: 환경변수 YMTC_URL, 없으면 http://127.0.0.1:8008)
  --round next|open       next(기본): 다음 회차를 만든다. open: 진행 중인 회차가 있으면 거기에 기록
  --version <값>          새 회차의 버전 (비우면 직전 회차를 이어받는다)
  --env <값>              새 회차의 환경 (비우면 직전 회차를 이어받는다)
  --sheets <a,b>          새 회차의 시트 범위 (주면 이어받지 않고 그 범위로 만든다)
  --label <문구>          비고 앞머리 (기본: "자동 기록 (형식)")
  --overwrite-executed    이미 기록된 결과도 NS 로 덮어쓴다 (기본은 덮지 않음)
  --dry-run               회차를 만들거나 기록하지 않고 계산 결과만 출력한다
  -h, --help              이 도움말

환경변수
  YMTC_API_KEY            API 키 (필수). 헤더 사용자 메뉴 「API 키」 에서 발급한다
  YMTC_URL                서버 주소

JUnit XML 을 올릴 때는 Playwright junit 리포터에 embedAnnotationsAsProperties: true 를 켜야
test.fail 결함 재현이 FAIL 로 구분된다.`;

function fail(msg) {
  console.error(`ymtc-upload: ${msg}`);
  process.exit(1);
}

let parsed;
try {
  parsed = parseArgs({
    allowPositionals: true,
    options: {
      url: { type: "string" },
      project: { type: "string" },
      "run-name": { type: "string" },
      "run-id": { type: "string" },
      round: { type: "string", default: "next" },
      version: { type: "string" },
      env: { type: "string" },
      sheets: { type: "string" },
      label: { type: "string" },
      "overwrite-executed": { type: "boolean", default: false },
      "dry-run": { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
  });
} catch (e) {
  fail(`${e.message}\n\n${HELP}`);
}
const { values: o, positionals } = parsed;
if (o.help) {
  console.log(HELP);
  process.exit(0);
}

const key = process.env.YMTC_API_KEY;
if (!key) fail("환경변수 YMTC_API_KEY 가 없습니다. 헤더 사용자 메뉴 「API 키」 에서 발급해 넣어 주세요.");
if (!o.project || !/^\d+$/.test(o.project)) fail("--project <id> 가 필요합니다.");
if (!o["run-name"] === !o["run-id"]) fail("--run-name 과 --run-id 중 하나만 주세요.");
if (o["run-id"] && !/^\d+$/.test(o["run-id"])) fail("--run-id 는 숫자입니다.");
if (!["next", "open"].includes(o.round)) fail("--round 는 next 또는 open 입니다.");
if (o["run-id"] && (o.version || o.env || o.sheets || o.round !== "next")) {
  fail("--run-id 와 --round · --version · --env · --sheets 는 함께 쓸 수 없습니다. 이미 있는 수행에 그대로 기록합니다.");
}
if (positionals.length !== 1) fail(`결과 파일 하나를 주세요.\n\n${HELP}`);
const file = positionals[0];
if (!existsSync(file)) fail(`파일이 없습니다: ${file}`);

const base = (o.url || process.env.YMTC_URL || "http://127.0.0.1:8008").replace(/\/+$/, "");
const params = new URLSearchParams({
  dry_run: String(o["dry-run"]),
  keep_executed: String(!o["overwrite-executed"]),
});
if (o.label) params.set("label", o.label);
let path;
if (o["run-id"]) {
  path = `/api/projects/${o.project}/testruns/${o["run-id"]}/results/import`;
} else {
  path = `/api/projects/${o.project}/testruns/import`;
  params.set("run_name", o["run-name"]);
  params.set("round", o.round);
  if (o.version !== undefined) params.set("version", o.version);
  if (o.env !== undefined) params.set("environment", o.env);
  if (o.sheets !== undefined) params.set("sheet_names", o.sheets);
}

const form = new FormData();
form.append("file", new Blob([readFileSync(file)]), basename(file));

let res;
try {
  res = await fetch(`${base}${path}?${params}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${key}` },
    body: form,
  });
} catch (e) {
  fail(`서버에 연결하지 못했습니다 (${base}): ${e.cause?.code || e.message}`);
}
const text = await res.text();
let body;
try {
  body = JSON.parse(text);
} catch {
  body = { detail: text.slice(0, 300) };
}
if (!res.ok) {
  const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
  fail(`HTTP ${res.status}: ${detail}`);
}

const r = body;
const run = r.run;
const where = run
  ? `${run.name} R${run.round}${run.id ? ` (id ${run.id})` : ""}${run.created ? (r.dry_run ? " · 새 회차 예정" : " · 새 회차") : ""}`
  : `수행 id ${r.run_id}`;
const fmt = r.format === "junit-xml" ? "JUnit XML" : "Playwright JSON";
const list = (ids) => (ids.length > 10 ? `${ids.slice(0, 10).join(", ")} 외 ${ids.length - 10}건` : ids.join(", "));

console.log(`${r.dry_run ? "[미리보기] " : ""}${where}`);
console.log(`  ${fmt} · 테스트 ${r.total_tests}건 중 ${r.matched_tests}건 매칭 · TC ${r.recorded}건 ${r.dry_run ? "기록 예정" : "기록"}`);
console.log(`  PASS ${r.counts.PASS} · FAIL ${r.counts.FAIL} · NS ${r.counts.NS}`);
if (r.known_failures) console.log(`  test.fail 결함 재현 ${r.known_failures}건`);
if (r.unexpected_failures.length) console.log(`  예상 밖 실패 ${r.unexpected_failures.length}: ${list(r.unexpected_failures)}`);
if (r.fixed_candidates.length) console.log(`  결함 해소 후보 ${r.fixed_candidates.length}: ${list(r.fixed_candidates)}`);
if (r.kept_executed.length) console.log(`  기존 결과 유지 ${r.kept_executed.length}: ${list(r.kept_executed)}`);
if (r.out_of_run.length) console.log(`  수행 범위 밖 ${r.out_of_run.length}: ${list(r.out_of_run)}`);
if (r.unmatched_count) {
  console.log(`  TC ID 를 찾지 못한 테스트 ${r.unmatched_count}건`);
  for (const t of r.unmatched.slice(0, 5)) console.log(`    - ${t}`);
  if (r.unmatched_count > 5) console.log(`    - 외 ${r.unmatched_count - 5}건`);
}
