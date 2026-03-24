const pptxgen = require("pptxgenjs");
const path = require("path");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "sym804";
pres.title = "YM TestCase Portfolio";

// ── Design Tokens (refined) ──
const C = {
  bg: "0F1117",
  bgCard: "181B25",
  surface: "1C2030",
  border: "2A3050",
  text: "D4D8E8",
  dim: "7B83A0",
  accent: "22C55E",
  blue: "5B8DEF",
  yellow: "EFAF3F",
  red: "E85555",
  purple: "A078E8",
  white: "F0F2F8",
};
const H = "Trebuchet MS";   // header — 가볍고 현대적
const B = "Calibri";         // body — 가독성
const M = "Consolas";        // mono
const SHOTS = path.join(__dirname, "..", "docs", "screenshots");

const shadow = () => ({
  type: "outer", blur: 6, offset: 2, angle: 135,
  color: "000000", opacity: 0.2
});

// ── Helpers ──
function footer(s, text) {
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.25, w: 10, h: 0.375,
    fill: { color: C.surface }
  });
  s.addText(text, {
    x: 0.6, y: 5.25, w: 8.8, h: 0.375,
    fontSize: 8, color: C.dim, fontFace: B, valign: "middle", margin: 0
  });
}

function sectionHeader(s, tag, title) {
  s.addText(tag, {
    x: 0.7, y: 0.45, w: 3, h: 0.25,
    fontSize: 9, fontFace: B, color: C.accent,
    bold: true, charSpacing: 3, margin: 0
  });
  s.addText(title, {
    x: 0.7, y: 0.7, w: 8, h: 0.5,
    fontSize: 22, fontFace: H, color: C.white,
    bold: true, margin: 0
  });
}

function card(s, x, y, w, h, accentColor) {
  s.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: C.bgCard },
    line: { color: C.border, width: 0.5 },
    shadow: shadow()
  });
  if (accentColor) {
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h: 0.04,
      fill: { color: accentColor }
    });
  }
}

// ════════════════════════════════════════
// SLIDE 1: Title
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.04,
    fill: { color: C.accent }
  });

  // Badge
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.7, y: 1.4, w: 1.9, h: 0.32,
    fill: { color: C.surface },
    line: { color: C.accent, width: 0.5 }
  });
  s.addText("AGPL-3.0 Open Source", {
    x: 0.7, y: 1.4, w: 1.9, h: 0.32,
    fontSize: 8, color: C.accent, fontFace: B,
    align: "center", valign: "middle", margin: 0
  });

  s.addText("YM TestCase", {
    x: 0.7, y: 1.9, w: 8, h: 0.9,
    fontSize: 38, fontFace: H, color: C.white,
    bold: true, valign: "middle", margin: 0
  });

  s.addText("QA 팀과 개발팀을 위한 셀프 호스팅형 테스트케이스 관리 도구", {
    x: 0.7, y: 2.8, w: 7, h: 0.5,
    fontSize: 13, fontFace: B, color: C.dim, margin: 0
  });

  // Metrics row in title
  const minis = [
    { n: "567", l: "Tests" }, { n: "100%", l: "Pass" },
    { n: "21K+", l: "LOC" }, { n: "v0.7.1", l: "Latest" }
  ];
  minis.forEach((m, i) => {
    const x = 0.7 + i * 2.0;
    s.addText(m.n, {
      x, y: 3.65, w: 1.5, h: 0.4,
      fontSize: 18, fontFace: H, color: C.accent,
      bold: true, margin: 0
    });
    s.addText(m.l, {
      x, y: 4.0, w: 1.5, h: 0.3,
      fontSize: 9, fontFace: B, color: C.dim, margin: 0
    });
  });

  s.addText("github.com/sym804/ym-testcase", {
    x: 0.7, y: 4.6, w: 5, h: 0.3,
    fontSize: 10, fontFace: M, color: C.blue, margin: 0
  });

  footer(s, "YM TestCase Portfolio · v0.7.1.0");
}

// ════════════════════════════════════════
// SLIDE 2: Problem & Solution
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "WHY", "왜 만들었는가");

  // Problem
  card(s, 0.5, 1.5, 4.25, 3.4, C.red);
  s.addText("기존의 문제", {
    x: 0.8, y: 1.7, w: 3.5, h: 0.35,
    fontSize: 13, fontFace: H, color: C.red, bold: true, margin: 0
  });
  s.addText([
    { text: "TestRail — 높은 라이선스 비용, SaaS 종속", options: { bullet: true, breakLine: true } },
    { text: "Excel — 협업 불가, 버전 관리 지옥", options: { bullet: true, breakLine: true } },
    { text: "Kiwi TCMS — 설치 복잡, 느린 UI", options: { bullet: true, breakLine: true } },
    { text: "자체 개발 — 수개월의 개발 기간", options: { bullet: true } },
  ], {
    x: 0.85, y: 2.2, w: 3.6, h: 2.4,
    fontSize: 11, fontFace: B, color: C.dim, valign: "top", margin: 0, paraSpaceAfter: 6
  });

  // Solution
  card(s, 5.25, 1.5, 4.25, 3.4, C.accent);
  s.addText("YM TestCase의 해결", {
    x: 5.55, y: 1.7, w: 3.5, h: 0.35,
    fontSize: 13, fontFace: H, color: C.accent, bold: true, margin: 0
  });
  s.addText([
    { text: "무료 오픈소스 (AGPL-3.0)", options: { bullet: true, breakLine: true } },
    { text: "스프레드시트 스타일 즉시 편집", options: { bullet: true, breakLine: true } },
    { text: "5분 설치, 즉시 사용 가능", options: { bullet: true, breakLine: true } },
    { text: "셀프 호스팅으로 데이터 주권 확보", options: { bullet: true } },
  ], {
    x: 5.6, y: 2.2, w: 3.6, h: 2.4,
    fontSize: 11, fontFace: B, color: C.dim, valign: "top", margin: 0, paraSpaceAfter: 6
  });

  footer(s, "YM TestCase Portfolio · Problem & Solution");
}

// ════════════════════════════════════════
// SLIDE 3: Key Metrics
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "METRICS", "핵심 지표");

  const metrics = [
    { num: "567", label: "자동화 테스트", sub: "100% PASS", col: C.accent },
    { num: "21K+", label: "Lines of Code", sub: "Backend + Frontend", col: C.blue },
    { num: "11", label: "핵심 기능", sub: "Full QA Workflow", col: C.yellow },
    { num: "10편", label: "기술 블로그", sub: "개발 과정 기록", col: C.purple },
  ];

  metrics.forEach((m, i) => {
    const x = 0.45 + i * 2.35;
    card(s, x, 1.6, 2.1, 3.0, m.col);
    s.addText(m.num, {
      x, y: 2.0, w: 2.1, h: 0.7,
      fontSize: 32, fontFace: H, color: m.col,
      bold: true, align: "center", valign: "middle", margin: 0
    });
    s.addText(m.label, {
      x, y: 2.8, w: 2.1, h: 0.35,
      fontSize: 12, fontFace: B, color: C.white,
      align: "center", valign: "middle", margin: 0
    });
    s.addText(m.sub, {
      x, y: 3.2, w: 2.1, h: 0.3,
      fontSize: 9, fontFace: B, color: C.dim,
      align: "center", valign: "top", margin: 0
    });
  });

  footer(s, "YM TestCase Portfolio · Key Metrics");
}

// ════════════════════════════════════════
// SLIDE 4–6: Features (3 slides)
// ════════════════════════════════════════
const featureSlides = [
  {
    tag: "FEATURES 1/3", title: "TC 관리", accent: C.accent,
    items: [
      { t: "스프레드시트 편집", d: "AG Grid 기반 인라인 편집. Undo/Redo,\n찾기/바꾸기(정규식), 멀티 행 추가, 벌크 삭제" },
      { t: "시트 트리", d: "N-depth 계층형 시트로 테스트 스위트를\n폴더처럼 관리. 엑셀 스타일 탭 UI" },
      { t: "커스텀 필드", d: "6가지 필드 타입: 텍스트, 숫자, 셀렉트,\n멀티셀렉트, 체크박스, 날짜" },
    ]
  },
  {
    tag: "FEATURES 2/3", title: "테스트 실행 & 분석", accent: C.blue,
    items: [
      { t: "테스트 런", d: "P/F/B/N 키보드 단축키로 빠른 결과 기록.\n타이머, 드래그앤드롭 첨부, 스크린샷" },
      { t: "테스트 플랜", d: "마일스톤 기반 테스트 계획.\n릴리즈별 실행 추적, 커버리지 시각화" },
      { t: "대시보드 & 리포트", d: "Chart.js 시각화, 결과 분포, 라운드별 비교.\nPDF/Excel 리포트 자동 생성" },
    ]
  },
  {
    tag: "FEATURES 3/3", title: "데이터 & 보안", accent: C.yellow,
    items: [
      { t: "Import / Export", d: "Excel 멀티시트 임포트, Jira CSV 35+ 헤더 매핑.\nCP949/UTF-8 BOM 자동감지, 벌크 Upsert" },
      { t: "고급 필터", d: "AND/OR 다중 조건, 6가지 연산자.\n(=, !=, 포함, 미포함, >, <) 필터 뷰 저장" },
      { t: "인증 & RBAC", d: "JWT + httpOnly 쿠키, 시스템/프로젝트 이중 역할.\nRate Limiting, CSRF, bcrypt 암호화" },
    ]
  },
];

featureSlides.forEach(fs => {
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, fs.tag, fs.title);

  fs.items.forEach((f, i) => {
    const x = 0.45 + i * 3.1;
    card(s, x, 1.5, 2.85, 3.2, fs.accent);

    s.addText(f.t, {
      x: x + 0.2, y: 1.75, w: 2.45, h: 0.35,
      fontSize: 13, fontFace: H, color: C.white,
      bold: true, margin: 0
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x: x + 0.2, y: 2.15, w: 1.2, h: 0.015,
      fill: { color: fs.accent }
    });
    s.addText(f.d, {
      x: x + 0.2, y: 2.35, w: 2.45, h: 2.1,
      fontSize: 10, fontFace: B, color: C.dim,
      valign: "top", margin: 0
    });
  });

  footer(s, "YM TestCase Portfolio · " + fs.tag);
});

// ════════════════════════════════════════
// SLIDE 7: Screenshots (1/2) — Dashboard & TC Grid
// ════════════════════════════════════════
{
  // 원본 비율 16:10 (1280x800). 슬라이드 너비 10", 이미지 w=8.6 → h=8.6/1.6=5.375 → 꽉 차므로 적절히 조절
  const imgW = 8.6;
  const imgH = imgW / 1.6; // 5.375 → 너무 크니 여백 고려해서 조절

  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "SCREENSHOTS 1/2", "화면 미리보기");

  // Dashboard — 크게 (원본 비율, 화면 가득)
  const dw = 8.8, dh = dw / 1.6; // 8.8 x 5.5 → 좀 넘침, 사용 가능 높이: 5.25-1.3=3.95
  // 높이 기준으로 맞추기: 사용 가능 3.6 → w = 3.6*1.6 = 5.76
  const h1 = 1.75;
  const availH = 5.0 - h1; // ~3.25
  const w1 = availH * 1.6; // ~5.2

  // 2장을 나란히 배치 (좌: 대시보드, 우: TC 그리드)
  const cardW = 4.35, cardImgW = 4.15, cardImgH = cardImgW / 1.6; // 4.15 x 2.59

  // Left — Dashboard
  card(s, 0.4, 1.45, cardW + 0.1, cardImgH + 0.5);
  s.addImage({
    path: path.join(SHOTS, "dashboard.png"),
    x: 0.5, y: 1.55, w: cardImgW, h: cardImgH,
  });
  s.addText("대시보드 — 진행률, 결과 분포, 라운드별 비교 차트", {
    x: 0.4, y: 1.55 + cardImgH + 0.05, w: cardW + 0.1, h: 0.3,
    fontSize: 9, fontFace: B, color: C.dim, align: "center", margin: 0
  });

  // Right — TC Grid
  card(s, 5.15, 1.45, cardW + 0.1, cardImgH + 0.5);
  s.addImage({
    path: path.join(SHOTS, "tc_grid.png"),
    x: 5.25, y: 1.55, w: cardImgW, h: cardImgH,
  });
  s.addText("TC 관리 — AG Grid 스프레드시트 인라인 편집", {
    x: 5.15, y: 1.55 + cardImgH + 0.05, w: cardW + 0.1, h: 0.3,
    fontSize: 9, fontFace: B, color: C.dim, align: "center", margin: 0
  });

  footer(s, "YM TestCase Portfolio · Screenshots 1/2");
}

// ════════════════════════════════════════
// SLIDE 8: Screenshots (2/2) — Dark Mode & Test Run
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "SCREENSHOTS 2/2", "화면 미리보기");

  const cardW = 4.35, cardImgW = 4.15, cardImgH = cardImgW / 1.6;

  // Left — Dark Mode
  card(s, 0.4, 1.45, cardW + 0.1, cardImgH + 0.5);
  s.addImage({
    path: path.join(SHOTS, "dark_mode.png"),
    x: 0.5, y: 1.55, w: cardImgW, h: cardImgH,
  });
  s.addText("다크 모드 — 전체 UI 일관된 다크 테마 지원", {
    x: 0.4, y: 1.55 + cardImgH + 0.05, w: cardW + 0.1, h: 0.3,
    fontSize: 9, fontFace: B, color: C.dim, align: "center", margin: 0
  });

  // Right — Test Run
  card(s, 5.15, 1.45, cardW + 0.1, cardImgH + 0.5);
  s.addImage({
    path: path.join(SHOTS, "testrun.png"),
    x: 5.25, y: 1.55, w: cardImgW, h: cardImgH,
  });
  s.addText("테스트 수행 — 런 목록과 실행 결과 기록", {
    x: 5.15, y: 1.55 + cardImgH + 0.05, w: cardW + 0.1, h: 0.3,
    fontSize: 9, fontFace: B, color: C.dim, align: "center", margin: 0
  });

  footer(s, "YM TestCase Portfolio · Screenshots 2/2");
}

// ════════════════════════════════════════
// SLIDE 8: Tech Stack
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "TECH STACK", "기술 스택");

  // Frontend
  card(s, 0.5, 1.5, 4.25, 3.2, C.blue);
  s.addText("Frontend", {
    x: 0.75, y: 1.72, w: 3.5, h: 0.35,
    fontSize: 14, fontFace: H, color: C.blue, bold: true, margin: 0
  });
  s.addText([
    { text: "React 19 + TypeScript 5.9", options: { breakLine: true, bold: true, color: C.white } },
    { text: "Vite 7 — 빌드 도구", options: { breakLine: true, color: C.dim } },
    { text: "AG Grid Community — 스프레드시트 UI", options: { breakLine: true, color: C.dim } },
    { text: "Chart.js + react-chartjs-2 — 차트", options: { breakLine: true, color: C.dim } },
    { text: "React Router 7 · Axios · CSS", options: { color: C.dim } },
  ], {
    x: 0.75, y: 2.2, w: 3.8, h: 2.2,
    fontSize: 10, fontFace: B, valign: "top", margin: 0, paraSpaceAfter: 5
  });

  // Backend
  card(s, 5.25, 1.5, 4.25, 3.2, C.accent);
  s.addText("Backend", {
    x: 5.5, y: 1.72, w: 3.5, h: 0.35,
    fontSize: 14, fontFace: H, color: C.accent, bold: true, margin: 0
  });
  s.addText([
    { text: "Python 3.12 + FastAPI", options: { breakLine: true, bold: true, color: C.white } },
    { text: "SQLAlchemy 2 + SQLite — ORM/DB", options: { breakLine: true, color: C.dim } },
    { text: "Alembic — 마이그레이션", options: { breakLine: true, color: C.dim } },
    { text: "Pydantic 2 — 유효성 검증", options: { breakLine: true, color: C.dim } },
    { text: "JWT · bcrypt · openpyxl · fpdf2", options: { color: C.dim } },
  ], {
    x: 5.5, y: 2.2, w: 3.8, h: 2.2,
    fontSize: 10, fontFace: B, valign: "top", margin: 0, paraSpaceAfter: 5
  });

  footer(s, "YM TestCase Portfolio · Tech Stack");
}

// ════════════════════════════════════════
// SLIDE 9: Architecture
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "ARCHITECTURE", "시스템 아키텍처");

  const boxes = [
    { x: 0.5, t: "Frontend", sub: "React 19 + TypeScript\nAG Grid · Chart.js\nVite :5173", col: C.blue },
    { x: 3.75, t: "Backend", sub: "FastAPI + Uvicorn\n15 Route Modules\nJWT + RBAC :8008", col: C.accent },
    { x: 7.0, t: "Database", sub: "SQLite (default)\n13 Tables\nAlembic Migrations", col: C.yellow },
  ];

  boxes.forEach(b => {
    card(s, b.x, 1.5, 2.5, 2.2, b.col);
    s.addText(b.t, {
      x: b.x, y: 1.7, w: 2.5, h: 0.35,
      fontSize: 13, fontFace: H, color: b.col,
      bold: true, align: "center", margin: 0
    });
    s.addText(b.sub, {
      x: b.x + 0.15, y: 2.15, w: 2.2, h: 1.3,
      fontSize: 10, fontFace: B, color: C.dim,
      align: "center", margin: 0
    });
  });

  // Arrows
  s.addText("→", { x: 3.05, y: 2.2, w: 0.65, h: 0.5, fontSize: 20, color: C.dim, align: "center", valign: "middle", margin: 0, fontFace: B });
  s.addText("→", { x: 6.3, y: 2.2, w: 0.65, h: 0.5, fontSize: 20, color: C.dim, align: "center", valign: "middle", margin: 0, fontFace: B });
  s.addText("REST API", { x: 3.05, y: 2.65, w: 0.65, h: 0.25, fontSize: 7, color: C.dim, align: "center", margin: 0, fontFace: B });
  s.addText("ORM", { x: 6.3, y: 2.65, w: 0.65, h: 0.25, fontSize: 7, color: C.dim, align: "center", margin: 0, fontFace: B });

  // Testing bar
  card(s, 0.5, 4.1, 9.0, 0.65);
  s.addText([
    { text: "Testing   ", options: { bold: true, color: C.white } },
    { text: "Vitest ", options: { color: C.blue } },
    { text: "358  +  ", options: { color: C.dim } },
    { text: "Playwright ", options: { color: C.purple } },
    { text: "93  +  ", options: { color: C.dim } },
    { text: "pytest ", options: { color: C.yellow } },
    { text: "116  =  ", options: { color: C.dim } },
    { text: "567 ALL PASS", options: { bold: true, color: C.accent } },
  ], {
    x: 0.5, y: 4.1, w: 9.0, h: 0.65,
    fontSize: 11, fontFace: B,
    align: "center", valign: "middle", margin: 0
  });

  footer(s, "YM TestCase Portfolio · Architecture");
}

// ════════════════════════════════════════
// SLIDE 10: Quality & Testing
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "QUALITY", "품질 & 테스트");

  const tests = [
    { num: "358", label: "Frontend Unit", desc: "Vitest · 23개 파일\n컴포넌트, API, 유틸리티", col: C.blue },
    { num: "93", label: "E2E Tests", desc: "Playwright · 9개 스펙\n인증, TC, 시트, 커스텀 필드", col: C.purple },
    { num: "116", label: "Backend API", desc: "pytest · 3개 파일\n보안, 기능, 엣지 케이스", col: C.yellow },
  ];

  tests.forEach((t, i) => {
    const x = 0.45 + i * 3.1;
    card(s, x, 1.5, 2.85, 2.6, t.col);
    s.addText(t.num, {
      x, y: 1.7, w: 2.85, h: 0.6,
      fontSize: 28, fontFace: H, color: t.col,
      bold: true, align: "center", valign: "middle", margin: 0
    });
    s.addText(t.label, {
      x, y: 2.35, w: 2.85, h: 0.3,
      fontSize: 12, fontFace: H, color: C.white,
      bold: true, align: "center", margin: 0
    });
    s.addText(t.desc, {
      x: x + 0.15, y: 2.75, w: 2.55, h: 0.9,
      fontSize: 9, fontFace: B, color: C.dim,
      align: "center", margin: 0
    });
  });

  // Quality gate bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 4.4, w: 9.0, h: 0.55,
    fill: { color: "0D1A12" },
    line: { color: "1A3A25", width: 0.5 }
  });
  s.addText("품질 게이트 ALL GREEN     빌드 PASS  ·  린트 PASS  ·  테스트 567/567 PASS", {
    x: 0.5, y: 4.4, w: 9.0, h: 0.55,
    fontSize: 10, fontFace: B, color: C.accent,
    bold: true, align: "center", valign: "middle", margin: 0
  });

  footer(s, "YM TestCase Portfolio · Quality");
}

// ════════════════════════════════════════
// SLIDE 11: Version History
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "HISTORY", "버전 히스토리");

  const versions = [
    { ver: "v0.7.1.0", date: "2026-03-23", desc: "품질 게이트 올 그린 · AGPL-3.0 라이선스 · 567 ALL PASS", on: true },
    { ver: "v0.7.0.0", date: "2026-03-21", desc: "오픈소스 준비 · GitHub 레포 · YM TestCase 브랜딩", on: true },
    { ver: "v0.6.0.0", date: "2026-03-20", desc: "시트 트리 · 커스텀 필드 · 테스트 플랜 · Jira CSV · 고급 필터", on: true },
    { ver: "v0.5.0.0", date: "2026-03-19", desc: "시트 관리 · 자동 저장 · Excel Upsert · 벌크 삭제 · 312 테스트", on: true },
    { ver: "v0.1~0.4", date: "~2026-03-18", desc: "핵심 TC 관리 · 인증/RBAC · 보안 강화 · 대시보드 · 리포트", on: false },
  ];

  // Timeline line
  s.addShape(pres.shapes.LINE, {
    x: 1.6, y: 1.55, w: 0, h: 3.35,
    line: { color: C.border, width: 1.5 }
  });

  versions.forEach((v, i) => {
    const y = 1.5 + i * 0.68;
    s.addShape(pres.shapes.OVAL, {
      x: 1.48, y: y + 0.1, w: 0.22, h: 0.22,
      fill: { color: v.on ? C.accent : C.dim }
    });
    s.addText(v.ver, {
      x: 1.95, y, w: 1.1, h: 0.4,
      fontSize: 10, fontFace: M, color: v.on ? C.accent : C.dim,
      bold: true, valign: "middle", margin: 0
    });
    s.addText(v.date, {
      x: 3.1, y, w: 1.1, h: 0.4,
      fontSize: 9, fontFace: B, color: C.dim,
      valign: "middle", margin: 0
    });
    s.addText(v.desc, {
      x: 4.2, y, w: 5.3, h: 0.4,
      fontSize: 10, fontFace: B, color: C.text,
      valign: "middle", margin: 0
    });
  });

  footer(s, "YM TestCase Portfolio · Version History");
}

// ════════════════════════════════════════
// SLIDE 12: Blog Series
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  sectionHeader(s, "BLOG", "개발 블로그 10편");

  s.addText("설계 결정, 기술 선택, 보안 강화, 오픈소스 공개까지 — 전 과정을 기록한 기술 블로그", {
    x: 0.7, y: 1.15, w: 8, h: 0.3,
    fontSize: 9, fontFace: B, color: C.dim, margin: 0
  });

  const blogs = [
    "왜 직접 만들었나", "기술 스택 선택기", "TC 관리 핵심 기능",
    "테스트 실행 & 대시보드", "인증 & RBAC", "보안 강화",
    "UI/UX 자동화", "고급 기능 (v0.6)", "오픈소스 공개기", "회고 & 교훈",
  ];

  blogs.forEach((b, i) => {
    const col = i < 5 ? 0 : 1;
    const row = i % 5;
    const x = 0.45 + col * 4.65;
    const y = 1.65 + row * 0.62;

    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.35, h: 0.48,
      fill: { color: C.bgCard },
      line: { color: C.border, width: 0.5 }
    });
    s.addText(String(i + 1).padStart(2, "0"), {
      x: x + 0.1, y, w: 0.5, h: 0.48,
      fontSize: 13, fontFace: H, color: C.accent,
      bold: true, valign: "middle", align: "center", margin: 0
    });
    // Separator line
    s.addShape(pres.shapes.LINE, {
      x: x + 0.65, y: y + 0.1, w: 0, h: 0.28,
      line: { color: C.border, width: 0.5 }
    });
    s.addText(b, {
      x: x + 0.75, y, w: 3.4, h: 0.48,
      fontSize: 10, fontFace: B, color: C.text,
      valign: "middle", margin: 0
    });
  });

  footer(s, "YM TestCase Portfolio · Blog Series");
}

// ════════════════════════════════════════
// SLIDE 13: Thank You
// ════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };

  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.04,
    fill: { color: C.accent }
  });

  s.addText("Thank You", {
    x: 0.7, y: 1.5, w: 8, h: 0.6,
    fontSize: 32, fontFace: H, color: C.white,
    bold: true, margin: 0
  });

  s.addText("YM TestCase", {
    x: 0.7, y: 2.2, w: 8, h: 0.45,
    fontSize: 18, fontFace: H, color: C.accent,
    bold: true, margin: 0
  });
  s.addText("Your Method, Your Test Case Manager", {
    x: 0.7, y: 2.65, w: 8, h: 0.35,
    fontSize: 11, fontFace: B, color: C.dim,
    italic: true, margin: 0
  });

  const items = [
    { label: "GitHub", value: "github.com/sym804/ym-testcase" },
    { label: "License", value: "AGPL-3.0" },
    { label: "Developer", value: "sym804" },
    { label: "Version", value: "v0.7.1.0" },
  ];

  items.forEach((item, i) => {
    const y = 3.35 + i * 0.38;
    s.addText(item.label, {
      x: 0.7, y, w: 1.3, h: 0.3,
      fontSize: 10, fontFace: B, color: C.dim, bold: true, margin: 0
    });
    s.addText(item.value, {
      x: 2.0, y, w: 5, h: 0.3,
      fontSize: 10, fontFace: M, color: C.accent, margin: 0
    });
  });

  footer(s, "YM TestCase Portfolio");
}

// ── Save ──
const out = path.join(__dirname, "YM_TestCase_Portfolio.pptx");
pres.writeFile({ fileName: out }).then(() => {
  console.log("Created: " + out);
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
