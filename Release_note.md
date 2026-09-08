# YM TestCase Release Notes

## 버전 체계

### 형식: `system.feature.major.minor`

| 자리 | 의미 | 변경 기준 |
|---|---|---|
| **system** | 시스템 구조 변경 | 대규모 리팩토링, 아키텍처 변경, 하위 호환 불가 |
| **feature** | 기능 변경 | 신규 기능 추가, 기존 기능 대규모 수정 |
| **major** | 중요 버그 수정 | 빌드 실패, 데이터 정합성, 보안 취약점 등 |
| **minor** | 사소한 버그 수정 | UI 텍스트, 스타일, 미미한 동작 수정 |

### 컴포넌트별 버전 관리

YM TestCase는 3개 컴포넌트로 구성되며, 각각 독립적으로 버전을 관리합니다.

| 컴포넌트 | 설명 | 버전 변경 시점 |
|---|---|---|
| **Frontend** | React + TypeScript + Vite | UI/UX 변경, 페이지 추가, 컴포넌트 수정 |
| **Backend** | FastAPI + SQLAlchemy | API 변경, 비즈니스 로직, 보안 수정 |
| **Database** | SQLite (SQLAlchemy 모델) | 테이블/컬럼 추가·변경·삭제, 마이그레이션 |

**System Version**은 전체 릴리즈 단위의 태그 역할이며, 컴포넌트 중 하나라도 변경되면 함께 올립니다.

### 버전 변경 규칙

| 변경 대상 | 올리는 버전 |
|---|---|
| Frontend만 수정 | Frontend + System |
| Backend만 수정 | Backend + System |
| DB 스키마 변경 | Database + Backend + System |
| 전체 변경 | Frontend + Backend + Database(해당 시) + System |

---

## 현재 버전

```
YM TestCase System  v1.4.0.1  (2026-09-08)
├── Frontend       v1.4.0.0
├── Backend        v1.4.0.0
└── Database       v0.8.0.0
```

---

## v1.4.0.1 (2026-09-08) - [docs] 버전 자리 판정 기준 정합

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.4.0.0 | **1.4.0.1** | patch +1 |

### 변경

- `rules/versioning.md` 를 전역 규칙의 A.B.C.D 판정에 맞췄다. 리팩토링은 B, 기능 추가는 규모로 B 와 C 를 가른다
- 릴리즈 노트 항목 분량 상한을 올린 자리에 매어 명시했다(A 1600 / B 1200 / C 900 / D 5줄)
- 상한을 넘던 v1.3.4.0(922자), v1.4.0.0(1254자) 절을 줄였다

### 영향

- 없음. 문서만 바뀌었다

---

## v1.4.0.0 (2026-09-08) - [feat] 시트를 골라 테스트 수행 만들기

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.4.0 | **1.4.0.0** | feature +1 |
| Frontend | 1.3.3.0 | **1.4.0.0** | feature +1 |
| Backend | 1.3.3.0 | **1.4.0.0** | feature +1 |
| Database | 0.7.3.0 | **0.8.0.0** | feature +1 |

### 이슈

- SYM-37 테스트 수행을 시트 단위로 만들 수 없다 (enhancement/major/frontend)
- SYM-38 대시보드가 프로젝트 전체 TC 를 분모로 써서 일부 시트만 담은 수행의 진행률이 틀리다 (bug/major/backend)
- SYM-40 테스트 수행에서 결과 저장이 거부돼도 이유를 알 수 없고 화면 값이 그대로 남는다 (bug/major/frontend)

### 변경

- 새 테스트 수행 모달에 "포함할 시트" 추가. 기본은 전체 선택이고 체크를 풀어 줄인다
- 고른 범위를 `test_runs.sheet_names` 에 저장한다. 생성 시점의 필터가 아니라 수행의 범위라서, 진행 중 수행이 새 TC 를 흡수할 때도 같은 조건을 건다
- 전부 고르면 범위를 저장하지 않는다. 범위 없음은 프로젝트 전체다
- 복제하면 범위도 따라간다. 폴더와 없는 시트는 받지 않고, 범위 밖 TC 의 결과 제출은 400 으로 거부한다
- 시트 이름을 바꾸거나 지우면 그 시트를 담은 수행의 범위도 함께 고친다
- 대시보드 분모를 수행이 담은 TC 수로 바꿨다. summary, priority, category, rounds, 전역 개요. 분자도 같은 기준으로 좁힌다
- 결과 저장이 거부되면 서버가 준 사유를 띄우고 화면을 되돌린다
- 수행 상세의 시트 탭이 그 수행의 범위만 보여 준다

### 영향

- 기존 수행은 `sheet_names` 가 NULL 이라 동작이 달라지지 않는다
- 일부 시트만 담은 수행의 대시보드 수치가 달라진다. 4건을 전부 PASS 한 수행이 36.4% 에서 100% 로 정정된다
- 전역 개요의 총계가 최신 수행이 담은 수로 바뀐다

### 조치

- 없음. 마이그레이션은 서버 기동 시 자동 적용된다

---

## v1.3.4.0 (2026-09-08) - [fix] 첨부파일이 있어도 셀을 눌러야 보이던 문제

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.3.0 | **1.3.4.0** | fix +1 |
| Frontend | 1.3.2.0 | **1.3.3.0** | fix +1 |
| Backend | 1.3.2.1 | **1.3.3.0** | fix +1 |
| Database | 0.7.2.0 | **0.7.3.0** | fix +1 |

### 이슈

- SYM-36 테스트 수행 그리드에서 첨부파일이 있어도 셀을 눌러야 보인다 (bug/major/frontend)

### 변경

- 런 상세를 열 때 첨부를 런 단위로 한 번에 받는다. `GET /api/attachments/by-run/{run_id}` 추가
- 첨부 맵을 갈아끼우지 않고 병합한다. 조회 중 올리거나 지운 첨부가 되돌아가지 않는다
- 런 상세 요청에 세대 번호를 붙여 늦게 온 이전 런의 응답을 버린다
- 시트 탭만 바꿀 때는 첨부를 다시 받지 않는다
- `attachments.test_result_id` 인덱스 추가. 조회가 첨부 테이블 전체 스캔을 탔다(query plan `SCAN a`)
- 테스트 11건 추가. 공용 ag-grid 모킹이 rowData 길이만 출력해 셀 렌더러가 실행되지 않았고, 이 결함이 통과 415건 안에서 지나갔다

### 영향

- 런을 열면 첨부가 있는 행에 파일명이 바로 보인다. 첨부 유무를 보려고 행을 눌러 볼 필요가 없다
- 런 하나를 여는 동안 첨부 조회가 행 수만큼에서 1회로 줄었다

### 조치

- 없음. 인덱스 마이그레이션은 서버 기동 시 자동 적용된다

---

## v1.3.3.0 (2026-09-07) - [fix] 저장이 거부된 값이 화면에 남던 문제

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.2.1 | **1.3.3.0** | fix +1 |
| Frontend | 1.3.1.0 | **1.3.2.0** | fix +1 |

### 이슈

- SYM-35 자동저장이 거부된 값이 그리드에 남아 그 행의 이후 편집이 전부 실패한다 (bug/major/frontend)

### 변경

- 행마다 서버가 확정한 마지막 상태를 들고 있다가, 저장이 거부되면 그 상태로 되돌린다
- 되돌리기를 편집 지점이 아니라 자동저장 한 곳에 둔다. 자동저장을 부르는 경로는 여섯인데(셀 편집, 찾기/바꾸기, 일괄 변경, TC ID 자동채우기, Ctrl+D 채우기, undo/redo) 다섯은 `node.data` 를 직접 고쳐 셀 편집 이벤트를 타지 않는다
- E2E 2건 추가. 셀 편집과 모두 바꾸기 각각의 거부 경로를 덮는다

### 영향

- 저장이 거부되면 입력한 값이 화면에서 사라지고 서버 값으로 돌아간다. 무엇이 거부됐는지는 토스트가 알려 준다
- 거부 직후 같은 행의 다른 칸을 고치면 정상 저장된다. 새로고침이 필요 없다

---

## v1.3.2.1 (2026-09-07) - [fix] 테스트가 개발용 DB 에 붙던 문제

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.2.0 | **1.3.2.1** | patch +1 |
| Backend | 1.3.2.0 | **1.3.2.1** | patch +1 |

### 이슈

- SYM-34 pytest 수집 단계에서 engine 이 개발용 DB 에 묶여 CI 백엔드 잡이 전부 실패한다 (bug/critical/db)

### 변경

- `conftest.py` 임포트 시점에 임시 DB 를 `DATABASE_URL` 에 박는다. 픽스처는 수집 이후라 늦다
- 셸에 개발 DB 가 박혀 있어도 임시 DB 로 돌린다. 일부러 쓰려면 `ALLOW_DEV_DB=1`
- 서버가 이미 떠 있으면 건드리지 않는다. HTTP 와 in-process engine 이 갈라지는 것을 막는다
- `test_db_isolation.py` 5건 추가. 서브프로세스로 임포트 순서를 재현해 수집 순서에 기대지 않는다

### 영향

- 제품 런타임 동작은 바뀌지 않는다. 테스트와 CI 만 바뀐다
- 백엔드 스위트 249 passed / 1 skipped (수정 전 223 errors)

---

## v1.3.2.0 (2026-09-07) - [fix] TC ID 유일성, 그리드 편집기 제한 해제, 마이그레이션 체인 복구

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.1.0 | **1.3.2.0** | fix +1 |
| Frontend | 1.3.0.0 | **1.3.1.0** | fix +1 |
| Backend | 1.3.1.0 | **1.3.2.0** | fix +1 |
| Database | 0.7.1.0 | **0.7.2.0** | fix +1 |

### 이슈

- SYM-23 TC ID 가 프로젝트 안에서 중복돼 사전조건 참조가 엉뚱한 TC 를 가리킨다 (bug/critical/db)
- SYM-24 Expected Result 가 경고 없이 200자에서 잘린다 (bug/major/frontend)
- SYM-25 Remarks 를 편집하면 줄바꿈이 사라진 채 저장된다 (bug/major/frontend)
- SYM-26 TC ID 자동채우기가 한 행도 채우지 않는데 완료 토스트가 뜬다 (bug/major/frontend)
- SYM-27 행을 여러 개 추가하면 전부 같은 순번과 TC ID 를 받는다 (bug/major/frontend)
- SYM-28 시트가 하나인 프로젝트에서 행을 추가하면 `기본` 시트가 조용히 생긴다 (bug/minor/frontend)
- SYM-29 자동 저장이 실패해도 이유를 알려주지 않는다 (bug/minor/frontend)
- SYM-30 그리드 헤더의 필터 버튼이 배경과 대비가 없어 보이지 않는다 (bug/minor/frontend)
- SYM-31 alembic head 가 둘로 갈라져 앱이 기동하지 못한다 (bug/blocker/db)
- SYM-32 로컬 자격증명 파일과 QA 스크래치 스크립트가 gitignore 에 없다 (bug/minor/security)
- SYM-33 package-lock 버전이 package.json 과 어긋난다 (bug/trivial/etc)

### 변경

- 마이그레이션 `b7d3c9a1e450`: `(project_id, tc_id)` 부분 유니크 인덱스(체인 맨 뒤). 임포트·복제·복원 세 경로 수정, 중복 시도는 409
- 대용량 텍스트 편집기 `maxLength` 명시, Remarks 에 동일 편집기 적용
- TC ID 순번 계산을 `utils/tcId.ts` 로 분리, 대량 추가는 `addRows(count)` 로 통합
- 시트 자동 선택 조건 수정, `전체` 보기에서 행 추가 차단
- 헤더 필터 버튼 대비 개선 (1.1:1 -> 13.35:1)
- `.gitignore` 에 로컬 자격증명과 `frontend/_*.mjs` 추가

### 영향

- 기존 DB 의 중복 TC ID 는 첫 기동 시 정리. 먼저 만든 행이 원래 ID 를 지키고 나머지에 `-2`, `-3`
- Expected Result 와 Remarks 의 입력 제한 해제. 이미 잘려 저장된 값은 복구 불가
- 같은 TC ID 저장 시도는 409

### 조치

- 배포 전 DB 백업. 첫 기동 로그에서 TC ID 재부여 WARNING 확인

---

## v1.3.1.0 (2026-09-05) - 한 런에서 한 TC 의 결과 행은 하나 (유니크 제약)

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.0.1 | **1.3.1.0** | fix +1 |
| Frontend | 1.3.0.0 | 1.3.0.0 | 변경 없음 |
| Backend | 1.3.0.1 | **1.3.1.0** | fix +1 |
| Database | 0.7.0.0 | **0.7.1.0** | fix +1 |

### 배경

`test_results` 에 `(test_run_id, test_case_id)` 유니크 제약이 없었다. 결과 행을 만드는
경로가 셋인데(런 생성, 런 동기화, 결과 제출) 셋 다 "없는 것을 조회한 뒤 넣는" 모양이라
동시 요청에서 같은 쌍이 두 번 들어갈 수 있었다. 특히 런 동기화는 런 상세를 열 때마다
호출되므로 두 사람이 동시에 열면 양쪽이 같은 집합을 넣는다.

운영 DB 에 실제로 하나 있었다(run=25, case=5345, 행 id 3070/3071).
중복이 있으면 리포트 집계가 `func.count(TestResult.id)` 라 total 이 부풀려지고,
`submit_results` 의 `existing_map` 은 마지막 행만 잡아 나머지가 고아 NS 로 남는다.

### 변경

- 마이그레이션 `a1c4e7b9d2f0`: 중복 병합 후 유니크 인덱스 생성. SQLite 는 기존
  테이블에 UNIQUE 제약을 붙이려면 테이블을 다시 만들어야 해서 인덱스를 썼다
- 병합은 삭제가 아니다. 실측한 두 행이 서로 다른 측정값을 갖고 있었다. 텍스트를
  잇고, 실행 메타데이터(실행자·시각·소요시간)는 **실제 결과가 있는 행** 것을 따르며,
  첨부는 남길 행으로 옮긴다. 결과가 서로 다르면 그 사실을 비고에 남긴다
- `models.py` 에 같은 이름의 유니크 인덱스 추가
- 런 동기화가 방언에 맞는 `on_conflict_do_nothing` 으로 넣는다. 예외로 처리하면
  세션이 죽어 나머지 행까지 못 들어간다
- 런 복제가 원본에 중복이 있어도 TC 기준 한 번만 복사한다
- 결과 제출이 유니크 위반에 한해 500 대신 409 와 재시도 안내를 낸다

### 영향

- 운영 DB: 4,338행 -> 4,337행. 병합된 행에 두 측정값이 모두 남았다
- 리포트 total 이 실제 TC 수와 일치한다
- 같은 TC 결과를 동시에 저장하면 한쪽이 409 를 받는다. 새로고침 후 재시도한다

### 테스트

`backend/test_result_uniqueness.py` 14건 신규. 마이그레이션 병합 규칙과 실제 SQLite
동작까지 검증한다. 전체 224건 통과(이전 210건). 회귀 체크리스트에 TC-RUN-021 추가.
QA 2인(Codex 읽기전용 + 리뷰 에이전트) 통과.

### 이슈

- SYM-5 test_results 에 (test_run_id, test_case_id) 유니크 제약 추가 (enhancement/major/db)

---

## v1.3.0.1 (2026-09-05) - 백엔드 테스트 51배 단축, 폐기 예정 API 정리

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.3.0.0 | **1.3.0.1** | minor +1 |
| Frontend | 1.3.0.0 | 1.3.0.0 | 변경 없음 |
| Backend | 1.3.0.0 | **1.3.0.1** | minor +1 |
| Database | 0.7.0.0 | 0.7.0.0 | 변경 없음 |

### 배경

backend 테스트 210건이 18분 39초 걸렸다. 그만큼 느리면 평소에 안 돌리게 되고,
회귀는 늦게 발견된다. 처음에는 비밀번호 해싱을 의심했으나 실측이 아니었다.

`--durations` 로 보니 거의 모든 테스트가 정확히 2.03초로 균일했다. 해싱 같은 가변
작업이면 편차가 있어야 한다. 요청 4개짜리는 9.02초, 2개짜리는 4.12초로 요청 수에
정확히 비례했다. 요청당 고정 2초라는 뜻이다. 서버를 띄우고 두 주소를 비교했다.

    http://localhost:8009/    2046ms, 2037ms, 2047ms
    http://127.0.0.1:8009/       2ms,    2ms,    2ms

Windows 에서 `localhost` 는 `::1` 과 `127.0.0.1` 둘 다로 풀리는데 conftest 가 띄우는
uvicorn 은 IPv4 로만 듣는다. 매 요청이 IPv6 시도에서 2초를 버리고 폴백했다.
bcrypt 는 해싱 158ms 로 정상이었다.

### 변경

- 테스트 대상 주소를 `localhost` 에서 `127.0.0.1` 로. `conftest.py` 와 테스트 파일 7개
- `conftest.py` 에서 `requests.Session.request` 를 감싸 기본 타임아웃 30초를 건다.
  전에는 354개 호출에 타임아웃이 하나도 없어 서버가 굳으면 스위트가 무한 대기했다.
  `TEST_HTTP_TIMEOUT` 으로 조절한다
- `routes/history.py` 의 `.subquery()` 를 `.scalar_subquery()` 로. `IN()` 자동 변환은
  없어질 예정이라 명시적으로 넘긴다
- `routes/reports.py` 의 `add_font(..., uni=True)` 에서 `uni` 제거. fpdf2 2.5.1 부터
  폐기됐고 TTF 는 기본 유니코드라 동작이 같다

### 영향

- 백엔드 동작은 바뀌지 않는다. 위 두 곳은 같은 결과를 내는 표현 변경이다
- 보안은 낮추지 않았다. bcrypt 라운드는 그대로다

### 테스트

210건 통과, 1건 스킵. 18분 39초 -> 21.79초. 경고 7건 -> 3건(남은 3건은 uvicorn 내부).
QA 2인(Codex 읽기전용 + 리뷰 에이전트) 통과.

### 이슈

- SYM-8 백엔드 테스트가 요청마다 2초를 버려 스위트가 18분 39초 걸린다 (bug/major/etc)
- SYM-9 테스트의 HTTP 호출에 타임아웃이 없어 서버가 굳으면 무한 대기한다 (bug/major/etc)
- SYM-10 폐기 예정 API 두 곳 정리 (enhancement/minor/backend)

---

## v1.3.0.0 (2026-09-04) - 계정 복구 (아이디 찾기, 비밀번호 재설정)

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.2.3.0 | **1.3.0.0** | feature +1 |
| Frontend | 1.2.2.0 | **1.3.0.0** | feature +1 |
| Backend | 1.2.3.0 | **1.3.0.0** | feature +1 |
| Database | 0.6.0.0 | **0.7.0.0** | feature +1 |

### 배경

여러 사람이 쓰기 시작하면서 계정을 잃은 사용자를 되돌릴 경로가 필요해졌다.
아이디 찾기는 아예 없었고 비밀번호는 관리자만 초기화할 수 있었다.
User 모델에 연락 수단이 없고 SMTP 설정도 없어 메일 기반 셀프 서비스는 불가능했다.

### 변경

- 계정 복구 요청 큐 신설. 아이디 찾기와 비밀번호 재설정을 같은 큐에서 관리한다
- 관리자가 대상 계정을 확정해 승인한다. 아이디 찾기는 아이디를 돌려주고,
  비밀번호 재설정은 24시간 유효한 1회용 코드를 발급한다
- 사용자가 그 코드로 새 비밀번호를 직접 정한다. 비밀번호는 관리자 손을 거치지 않는다
- 로그인 화면의 안내 문구를 '계정 도움 요청' 링크로 바꿨다
- 화면 하단 버전 표기가 v1.0.0.0 에 멈춰 있던 것을 실제 버전으로 맞췄다

### 보안

- 계정 열거 방지: 계정 복구 엔드포인트는 없는 아이디로 요청해도 응답이 동일해 계정 존재 여부를 드러내지 않는다.
  단, 이는 시스템 전체의 보장은 아니다. 회원가입 화면의 아이디 중복 확인(`check-username`)과 가입 처리는
  설계상 아이디 사용 여부를 그대로 노출한다
- 코드는 해시로만 저장하고 평문은 승인 응답 1회로 끝난다
- 코드는 한 번 쓰면 죽는다. 사용 즉시 code_hash 를 지운다
- 코드 대입은 기존 로그인 rate limit(5분 10회)으로, 요청 접수는 IP 기준 1시간 10회로 막는다

### 테스트

backend/test_account_requests.py 20건 신규. 기존 테스트 회귀 확인.

---

## v1.2.3.0 (2026-08-27) - 신규 clone 셋업 실패 수정

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.2.2.0 | **1.2.3.0** | fix +1 |
| Frontend | 1.2.2.0 | 1.2.2.0 | 변경 없음 |
| Backend | 1.2.2.0 | **1.2.3.0** | fix +1 |
| Database | 0.6.0.0 | 0.6.0.0 | 변경 없음 |

### 배경

GitHub 레포를 처음 clone 한 사용자가 README 대로 따라가도 셋업이 되지 않는다는 제보가 있었다.
신규 clone 을 실제로 만들어 README 를 글자 그대로 따라간 결과 세 가지가 확인됐다.

- Python 3.14 에서 `pip install -r requirements.txt` 가 통째로 실패했다
- `backend/.env` 를 만들어도 아무 설정이 적용되지 않았다
- README 의 테스트 절차가 첫 명령부터 실패했다

### 주요 변경

**Python 3.14 설치 실패 수정 (Block)**

`pydantic[email]==2.11.7` 이 `pydantic-core==2.33.2` 를 정확히 고정하는데, 이 버전은 휠 98개를
배포하면서 cp314 휠은 하나도 내지 않았다. 그래서 Python 3.14 에서는 pip 이 소스 빌드로 넘어가고,
pydantic-core 는 Rust 로 작성돼 있어 cargo 가 필요하다. 일반 사용자 PC 에 Rust 는 없으므로
`maturin failed` 로 설치가 중단되고, fastapi 와 uvicorn 을 포함한 나머지 패키지도 하나도 깔리지
않아 백엔드가 아예 뜨지 않았다.

`pydantic-core` 가 cp314 휠을 처음 낸 버전은 2.35.0 이다. `pydantic[email]==2.13.4`
(pydantic-core 2.46.4) 로 올려 해결했다. 나머지 바이너리 의존성(bcrypt, cryptography, greenlet,
httptools, watchfiles, PyYAML, psycopg2-binary)은 전부 cp314 휠이 있어 pydantic 단독 원인이었다.

**.env 파일이 전혀 읽히지 않던 문제 수정 (Critical)**

레포 어디에도 `.env` 를 읽는 코드가 없었다. `load_dotenv()` 호출이 0건이고
`run_dev.bat`, `run_dev.sh`, `playwright.config.ts`, CI 어느 것도 `--env-file` 을 주지 않았다.
그래서 `auth.py` 의 `os.getenv("SECRET_KEY", "")` 는 항상 빈 값을 받았고, 매 기동마다 랜덤 키가
생성되어 서버를 재시작할 때마다 모든 로그인 세션이 끊겼다. README 가 "기본값 그대로 두면 로그인이
풀립니다" 라고 경고한 바로 그 증상이, 시키는 대로 해도 그대로 발생한 것이다.
`ENV`, `CORS_ORIGINS`, `TOKEN_EXPIRE_HOURS`, `DATABASE_URL` 도 같이 무시됐고,
`ENV=production` 으로 지정해도 절대 production 으로 동작하지 않았다.

`backend/env_setup.py` 를 신설해 `auth.py`, `database.py`, `main.py`, `alembic/env.py` 최상단에서
임포트한다. `override=False` 라서 실제 환경변수와 `conftest.py` 가 임시 DB 격리를 위해 미리 지정하는
`DATABASE_URL` 이 항상 `.env` 보다 우선하므로 테스트 격리는 그대로 유지된다.
`ENV_FILE` 로 다른 경로를 지정할 수도 있다.

**테스트 의존성 분리 (Major)**

`pytest` 와 `requests`(conftest.py 가 임포트한다)가 어느 requirements 에도 없어서
README 의 `python -m pytest -v` 는 `No module named pytest` 로 즉시 실패했다.
CI 만 `pip install -r requirements.txt pytest requests` 로 인라인으로 채워 통과하고 있었다.
`backend/requirements-dev.txt` 를 신설하고 CI 도 이를 쓰도록 바꿨다.

**CI 게이트 보강**

- `pytest test_security.py` 로 파일을 명시하면 `pytest.ini` 의 `testpaths` 가 무시되어
  신규 테스트 파일이 영영 수집되지 않았다(실측: 파일 지정 169건, 무인자 173건).
  무인자 `pytest -q` 로 바꿔 이번에 추가한 회귀 테스트가 게이트에 들어가게 했다
- Python 3.12 / 3.14 설치 검증 매트릭스 job 을 추가했다.
  `pip install --only-binary=:all:` 로 소스 빌드 폴백 자체를 금지한다.
  GitHub 러너에는 Rust 가 설치돼 있어 일반 설치로는 이번 사고를 잡지 못하기 때문이다.
  옛 핀(2.11.7)으로 되돌려 확인한 결과 `No matching distribution found for pydantic-core==2.33.2`
  로 실패하는 것을 확인했다
- pip 캐시 키가 `requirements.txt` 만 보고 있어 `requirements-dev.txt` 도 포함시켰다

**문서 수정**

- README 사전 요구사항을 "Python 3.11+"(상한 없음)에서 "Python 3.11 ~ 3.14" 로 바꿨다.
  상한이 없어 최신 파이썬을 받은 사용자가 자동으로 설치 실패에 부딪혔다
- 기술 스택 표의 "Python 3.12" 도 같은 범위로 통일했다(문서끼리 어긋나 있었다)
- README 테스트 절에 `requirements-dev.txt` 설치와 `npx playwright install chromium` 을 추가했다.
  브라우저 설치는 CI 에만 있고 README 에는 없었다
- CONTRIBUTING 개발 환경 설정과 PR 체크리스트도 동일하게 갱신했다.
  체크리스트의 "116+ 테스트" 는 실제 169건과 어긋나 있어 바로잡았다
- `.gitignore` 의 `.env.example` 을 `/.env.example` 로 바꿨다.
  기존 패턴은 하위 경로까지 매칭돼 `backend/.env.example` 을 가릴 수 있는 지뢰였다

### 테스트

- 백엔드 pytest 174 passed / 1 skipped (수정 전 기준선 169 passed)
- 신규 `backend/test_env_loading.py` 5건.
  `env_setup` 임포트를 3개 파일에서 모두 제거하면 3건이 실패하는 것을 확인해 이빨을 검증했다
- 프론트 Vitest 360 passed (프론트 코드 변경 없음)
- E2E Playwright auth 7 passed
- Python 3.14.6 실환경에서 설치, 마이그레이션, 가입, 로그인, 프로젝트 생성, openapi 생성까지 확인
- 재시작 후 세션 유지: 수정 전 401, 수정 후 200

### 알려진 제한

- `env_setup` 임포트를 한 파일에서만 지우면 `auth -> database -> env_setup` 임포트 체인이
  대신 보장하므로 테스트가 잡지 못한다. 동작은 유지되므로 결함은 아니다.
  메커니즘 자체가 사라지는 경우(전부 제거)는 잡힌다
- `ENV_FILE` 로 임의 경로를 읽게 할 수 있다. 다만 환경변수를 통제할 수 있는 주체는 이미
  `SECRET_KEY` 와 `DATABASE_URL` 을 직접 통제할 수 있어 권한 상승은 없다

### 변경 파일

- `backend/env_setup.py` (신규)
- `backend/requirements-dev.txt` (신규)
- `backend/test_env_loading.py` (신규)
- `backend/requirements.txt`
- `backend/auth.py`
- `backend/database.py`
- `backend/main.py`
- `backend/alembic/env.py`
- `.github/workflows/ci.yml`
- `.gitignore`
- `README.md`
- `CONTRIBUTING.md`

---

## v1.2.2.0 (2026-07-20) - 런 생성 이후 추가된 TC 누락 수정

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.2.1.0 | **1.2.2.0** | fix +1 |
| Frontend | 1.2.1.0 | **1.2.2.0** | fix +1 |
| Backend | 1.2.1.0 | **1.2.2.0** | fix +1 |
| Database | 0.6.0.0 | 0.6.0.0 | 변경 없음 |

### 배경

테스트 수행 화면에서 시트 탭 배지가 5로 표시되는데 클릭하면 그리드가 비어 있고, 그 순간
시트 탭 바 자체가 사라져 다른 시트로 되돌아갈 수 없는 문제가 보고됐다. 원인은 세 가지였다.

- 결과 행(`test_results`)이 런 생성 시점에만 만들어져, 이후 추가된 TC는 결과 행이 영영 없었다
- 시트 탭 바 렌더 조건에 `results.length > 0`이 있어 결과 0건 시트를 고르면 탭 바가 사라졌다
- 탭 배지는 TC 라이브러리 기준, 그리드는 런 스냅샷 기준이라 숫자가 어긋났다

### 주요 변경

**런과 TC 목록 동기화 (신규 `services/run_sync_service.py`)**

- 진행 중(`in_progress`)인 런은 누락된 TC의 결과 행(NS)을 자동으로 흡수한다
- 완료(`completed`)된 런은 과거 기록의 무결성을 위해 생성 당시 스냅샷을 유지한다
- TC가 생기는 모든 경로(생성/복원/복제/일괄복제/엑셀·CSV·마크다운 임포트)에서 동기화하므로,
  런 상세를 열지 않아도 대시보드·리포트가 같은 숫자를 본다
- 런 상세 조회에도 보정을 두어 이 수정 이전에 만들어진 런을 복구한다.
  단 viewer는 읽기 전용 역할이므로 tester 이상에서만 보정한다
  (공개 프로젝트는 비멤버도 viewer로 취급되기 때문)
- `reopen` 시점에도 보정해, 완료 기간에 추가된 TC가 상세를 열지 않고 완료해도 누락되지 않게 했다

**결과 정렬 보장**

결과 행은 런에 편입된 순서로 저장되므로, 기존 TC 사이에 끼는 번호로 추가하면 화면 맨 뒤로
밀렸다(실측: `[1, 3, 2]`). 런 상세 API, 리포트 엑셀, 그리드 세 곳에서 TC 번호 순을 보장한다.

**시트 탭**

- 결과 0건 시트를 선택해도 탭 바가 유지된다 (막다른 길 제거)
- 배지를 TC 라이브러리가 아니라 해당 런의 결과 수로 표시한다.
  완료된 런에서도 배지와 그리드 행 수가 항상 일치한다

**DB 안전성**

- `PRAGMA busy_timeout=30000` 추가. 다중 요청 동시 쓰기에서 즉시 실패하지 않고 대기한다

### 테스트

- 백엔드 신규 10건 (`backend/test_run_tc_sync.py`), 프론트 신규 2건
- 각 테스트는 가드 로직을 제거하는 뮤테이션으로 실제 결함을 잡는지 검증했다
- 기존 회귀: 백엔드 `test_security.py` 169건, 프론트 360건 통과

신규 백엔드 테스트는 개발 서버(8008)의 실 DB를 오염시키지 않도록 가드를 두었다.
격리 포트를 지정해 실행한다.

```
cd backend
TEST_PORT=8009 TEST_BASE_URL=http://localhost:8009 python -m pytest test_run_tc_sync.py
```

### 알려진 제한

`test_results`에 `(test_run_id, test_case_id)` 유니크 제약이 없어 동시 요청에서 중복 행이
생길 수 있다. 운영 DB에 이미 중복 1건이 존재한다(런 25 / TC 5345, 2026-04-09 발생).
스키마 변경이 필요해 별건으로 분리했다 (이슈 #111).

### 변경 파일

- `backend/services/run_sync_service.py` (신규)
- `backend/routes/testruns.py`
- `backend/routes/testcases.py`
- `backend/routes/reports.py`
- `backend/database.py`
- `backend/test_run_tc_sync.py` (신규)
- `frontend/src/components/TestRunManager.tsx`
- `frontend/src/test/TestRunManager.test.tsx`

---

## v1.2.1.0 (2026-04-10) - 코드 구조 개선, Alembic 마이그레이션, pytest 재현성

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.2.0.0 | **1.2.1.0** | fix +1 |
| Frontend | 1.2.0.0 | **1.2.1.0** | fix +1 |
| Backend | 1.2.0.0 | **1.2.1.0** | fix +1 |
| Database | 0.5.0.0 | **0.6.0.0** | feature +1 (Alembic 도입, notifications 제거) |

### 주요 변경

#### Backend - 구조 개선 (ENH-044 ~ ENH-047)

- **pytest 원커맨드 재현성 (ENH-044)**: conftest.py에 임시 DB + admin 자동 시드 추가. `pytest -q`만으로 전체 테스트 통과 가능
- **testcases.py 분리 (ENH-045)**: 1722줄 → 571줄. 시트 CRUD → `routes/sheets.py`, import 파싱 → `services/import_service.py`, export → `services/export_service.py` 분리
- **Alembic 마이그레이션 도입 (ENH-046)**: 수동 ALTER TABLE 4개 제거, initial schema + sync migration 생성. 기존 DB 자동 감지 + stamp
- **CI 개선 (ENH-047)**: backend pytest timeout 20분 상향, conftest 자동 서버 시작으로 CI 수동 curl 제거

#### Frontend - 접근성/훅 추출 (ENH-048 ~ ENH-050)

- **TestCaseGrid 훅 추출 (ENH-048)**: 2274줄 → 1972줄. `useUndoRedo` 훅 + `SheetTreeSidebar` 컴포넌트 분리
- **TestRunManager 훅 추출 (ENH-049)**: 1776줄 → 1607줄. `useTestTimer`, `useAttachments`, `useResultFilters` 훅 분리
- **접근성(a11y) 개선 (ENH-050)**: Header/ProjectListPage에 role="button", tabIndex, onKeyDown 추가. 체크박스 이벤트 핸들러 수정. 삭제 버튼 `<button>` 태그 전환

#### Database - Alembic 도입

- **Alembic 마이그레이션 도입**: SQLAlchemy 모델 기반 자동 스키마 관리
- **notifications 테이블 제거**: v1.1.0에서 모델 삭제된 잔여 테이블 정리
- **batch mode 설정**: SQLite ALTER TABLE 제약 대응

### 변경 파일 (주요)

| 영역 | 파일 | 변경 |
|---|---|---|
| Backend | `routes/testcases.py` | 1722줄 → 571줄 (분리) |
| Backend | `routes/sheets.py` | 신규 (345줄, 시트 CRUD) |
| Backend | `services/import_service.py` | 신규 (719줄, import 파싱) |
| Backend | `services/export_service.py` | 신규 (126줄, export) |
| Backend | `conftest.py` | 임시 DB + admin seed 자동화 |
| Backend | `main.py` | 수동 마이그레이션 제거, Alembic 연동 |
| Backend | `alembic/` | Alembic 설정 + 2 migration revisions |
| Frontend | `hooks/useUndoRedo.ts` | 신규 (96줄) |
| Frontend | `hooks/useTestTimer.ts` | 신규 (75줄) |
| Frontend | `hooks/useAttachments.ts` | 신규 (96줄) |
| Frontend | `hooks/useResultFilters.ts` | 신규 (95줄) |
| Frontend | `components/SheetTreeSidebar.tsx` | 신규 (306줄) |
| Frontend | `components/TestCaseGrid.tsx` | 2274줄 → 1972줄 |
| Frontend | `components/TestRunManager.tsx` | 1776줄 → 1607줄 |
| Frontend | `components/Header.tsx` | a11y 개선 |
| Frontend | `pages/ProjectListPage.tsx` | a11y + 체크박스 수정 |
| CI | `.github/workflows/ci.yml` | timeout 상향, 자동 서버 시작 |

---

## v1.2.0.0 (2026-04-08) - 엑셀 Export 옵션, 필드 정리, UI 개선

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.1.0.1 | **1.2.0.0** | feature +1 |
| Frontend | 1.1.0.1 | **1.2.0.0** | feature +1 |
| Backend | 1.1.0.1 | **1.2.0.0** | feature +1 |
| Database | 0.4.0.0 | **0.5.0.0** | feature +1 (컬럼 삭제) |

### 주요 변경

#### Backend - 기능 (ENH-036 ~ ENH-039)

- **엑셀 Export 시트 분리 옵션**: `split_sheets=true` 쿼리 파라미터로 sheet_name 기준 엑셀 탭 분리 내보내기 지원
- **issue_link/assignee 컬럼 제거**: TC 모델에서 미사용 컬럼 삭제, 임포트(Excel/CSV/MD/Jira) 매핑을 `_skip` 처리
- **프로젝트 이름/설명 수정 API**: 기존 프로젝트 설정 업데이트 경로에서 name/description 변경 지원

#### Frontend - UI 개선 (ENH-040 ~ ENH-043)

- **Excel Export 옵션 모달**: 통합(단일 시트) / 분리(시트별 탭) 선택 라디오 UI 추가
- **프로젝트 설정 - 이름/설명 편집**: admin 권한 시 프로젝트 이름/설명 인라인 수정 가능
- **TestRunManager result `<select>` 전환**: AG Grid 셀 에디터 → 네이티브 select 위젯으로 변경 (직관적 결과 입력)
- **컬럼 flex 레이아웃**: test_steps/expected_result에 `minWidth + flex:2` 적용, 화면 크기에 따라 자동 확장

#### Database - 스키마 변경

- **issue_link, assignee 컬럼 삭제**: TestCase 테이블에서 미사용 컬럼 제거

### 변경 파일 (주요)

| 영역 | 파일 | 변경 |
|---|---|---|
| Backend | `routes/testcases.py` | Export split_sheets, 컬럼 제거, 임포트 매핑 |
| Backend | `models.py`, `schemas.py` | issue_link/assignee 컬럼·스키마 삭제 |
| Frontend | `TestCaseGrid.tsx` | Export 모달, 컬럼 제거, flex 레이아웃 |
| Frontend | `TestRunManager.tsx` | result select 위젯, Shift+클릭 개선 |
| Frontend | `ProjectSettings.tsx` | 프로젝트 이름/설명 편집 UI |
| Frontend | `api/index.ts` | exportExcel splitSheets 파라미터 |
| Frontend | `i18n/ko,en/settings.json` | 프로젝트 정보 관련 i18n 키 추가 |

---

## v1.1.0.1 (2026-04-06) - 성능 최적화

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.1.0.0 | **1.1.0.1** | patch +1 |
| Frontend | 1.1.0.0 | **1.1.0.1** | patch +1 |
| Backend | 1.1.0.0 | **1.1.0.1** | patch +1 |
| Database | 0.4.0.0 | 0.4.0.0 | 변경 없음 |

### 주요 변경

#### Backend - 성능 (PERF-003 ~ PERF-010)

- **대시보드 SQL 집계 전환**: summary/priority/category/assignee/rounds/heatmap 6개 엔드포인트를 ORM 전체 로드 → SQL CASE+GROUP BY 집계로 전면 전환 (최대 43x 개선)
- **Overview SQL 집계 전환**: Python 카운팅 → SQL 서브쿼리 3회 집계 (12x 개선)
- **TestPlan N+1 제거**: 플랜별 개별 조회 → `_bulk_plan_stats` SQL 2회 고정 (쿼리 170→6)
- **TestRun 생성/복제 bulk insert**: row-by-row `db.add()` → `bulk_insert_mappings` (5000건 기준 ~7s → ~0.5s)
- **결과 제출 N+1 제거**: per-item `.first()` → IN 쿼리 1회 prefetch
- **리포트 SQL 집계**: `_summary_sql`/`_category_summary_sql`/`_failed_items` 헬퍼 추가, Excel 이중 로드 제거 (JSON 3.2x, Excel 1.3x 개선)
- **SQLite WAL 모드**: `PRAGMA journal_mode=WAL` 추가 (동시 읽기/쓰기 성능 향상)
- **시트 트리 순회 최적화**: `_collect_descendant_names` 재귀 N+1 → 전체 1회 fetch + 메모리 DFS
- **TestRun 상세 조회**: `joinedload` → `subqueryload` 전환 (cartesian product 방지)
- **assignee 필터**: `func.trim` 적용 (공백만 있는 값 제외)

#### Frontend - 번들 최적화 (ENH-034 ~ ENH-035)

- **ProjectPage 탭 lazy 분리**: 6개 탭 컴포넌트를 `React.lazy` + `Suspense`로 분리 (ProjectPage 청크 195KB → 3.77KB)
- **번들 chunk 세분화**: charts/i18n/utils 별도 chunk 분리 (index 638KB → 356KB, 경고 해소)

### 성능 개선 수치 (6,800 TC / 26,800 results 기준)

| 엔드포인트 | Before | After | 개선율 |
|-----------|--------|-------|--------|
| overview | 117ms | 9.9ms | **12x** |
| dashboard summary | 50.5ms | 14ms | **3.6x** |
| dashboard priority | 164ms | 18ms | **9x** |
| dashboard category | 145ms | 18ms | **8x** |
| dashboard assignee | 134ms | 19ms | **7x** |
| dashboard rounds | 324ms | 7.5ms | **43x** |
| testplans list | 38ms/170쿼리 | 13ms/6쿼리 | **3x/28x** |
| reports JSON | 146ms | 46ms | **3.2x** |
| reports Excel | 2045ms | 1611ms | **1.3x** |
| index bundle | 638KB | 356KB | **44% 절감** |

### 변경 파일

- `backend/database.py` - WAL 모드 추가
- `backend/routes/dashboard.py` - SQL CASE+GROUP BY 전면 전환
- `backend/routes/overview.py` - SQL 서브쿼리 집계 전환
- `backend/routes/testplans.py` - `_bulk_plan_stats` N+1 제거
- `backend/routes/testruns.py` - bulk insert, subqueryload, IN prefetch
- `backend/routes/testcases.py` - `_collect_descendant_names` 1회 조회
- `backend/routes/reports.py` - SQL 집계 + 이중 로드 제거
- `frontend/src/pages/ProjectPage.tsx` - 탭 lazy import
- `frontend/src/test/ProjectPage.test.tsx` - lazy에 맞게 waitFor 추가
- `frontend/vite.config.ts` - chunk 세분화

### 이슈

- PERF-003 ~ PERF-010 (8건), ENH-034 ~ ENH-035 (2건) - 전체 완료

---

## v1.1.0.0 (2026-04-04) - 다국어 지원 (영문)

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 |
|---|---|---|---|
| System | 1.0.3.0 | **1.1.0.0** | feature +1 |
| Frontend | 1.0.3.0 | **1.1.0.0** | feature +1 |
| Backend | 1.0.3.0 | **1.1.0.0** | feature +1 |
| Database | 0.4.0.0 | 0.4.0.0 | 변경 없음 |

### 주요 변경

- react-i18next 기반 i18n 시스템 구축
- 한/영 로케일 파일 28개 (UI 12 + 매뉴얼 2 x 2언어, 650+ 번역 키)
- 전체 UI 컴포넌트 17개 + 매뉴얼 2개 i18n 변환
- Header에 EN/KO 언어 전환 버튼 (localStorage 저장)
- AG Grid 로케일 자동 전환
- 백엔드 에러 메시지 프론트 번역 매핑 (translateError, 25개)
- TC Grid: priority/platform enum 표시 번역 (DB 값 유지, refData+valueFormatter)
- 알림(notification) 기능 제거

### 테스트 결과

- Frontend: 358 PASS / 0 FAIL
- Codex 검증 3회 → 시스템 UI 한글 누출 0건

---

## v1.0.3.0 (2026-04-03) - 신규 기능 5개 + Codex 검증 수정

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 1.0.2.0 | **1.0.3.0** | 신규 기능 5개 추가 |
| Frontend | 1.0.2.0 | **1.0.3.0** | TC 복제/결과이력/드래그정렬 UI, 대시보드 날짜필터, 인앱 알림 벨 |
| Backend | 1.0.2.0 | **1.0.3.0** | Clone/ResultHistory/Reorder/DateFilter/Notification API, 완료 런 수정 차단 |
| Database | 0.3.0.0 | **0.4.0.0** | notifications 테이블 추가 |

### 신규 기능

| # | 기능 | 설명 |
|---|------|------|
| 1 | TC 복제 | 단건/벌크 복제 API + 선택 복제 버튼 (tc_id에 -copy 접미사) |
| 2 | TC 결과 히스토리 | TC별 런별 수행 결과 타임라인 모달 (📊 결과이력 버튼) |
| 3 | 대시보드 날짜 필터 | 프리셋(전체/7일/30일/90일) + 커스텀 날짜 범위 필터 |
| 4 | TC 드래그 정렬 | AG-Grid rowDrag로 No 컬럼 드래그 → 순서 자동 저장 |
| 5 | 인앱 알림 | 테스트 런 완료 시 멤버 전원 알림, 🔔 벨 아이콘 + 드롭다운 |

### Codex 검증 지적사항 수정 (4건)

| 심각도 | 내용 | 수정 |
|--------|------|------|
| 높음 | 완료된 테스트 런 결과 수정 가능 | submit_results에 completed 상태 체크 추가 |
| 중간 | 알림 링크 탭 키 불일치 | tab=testrun → tab=run |
| 중간 | pytest 수집 시 test_v103 import 오류 | conftest.py collect_ignore에 추가 |
| 낮음 | available-users가 기존 멤버 포함 | 기존 멤버 user_id 필터링 |

### 테스트

- Frontend: 358/358 PASS
- Backend API: 45/45 PASS
- TypeScript: 에러 없음

---

## v1.0.2.0 (2026-04-01) - 보안 검수 지적사항 13건 수정

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 1.0.1.0 | **1.0.2.0** | 보안 취약점 13건 수정 |
| Frontend | 1.0.1.0 | **1.0.2.0** | 전체 시트 보기 no 오염 방지, 테스트런 권한 가드, 멤버 관리 API 변경 |
| Backend | 1.0.1.0 | **1.0.2.0** | TC 이력 권한 체크, 프로젝트 삭제 파일 정리, 첨부파일 권한 fallback 등 9건 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 보안 수정 (치명 1건 + 높음 4건 + 중간 4건)

- **[치명] TC 이력 API 접근권한 누락**: `GET /api/history/testcase/{id}`에 프로젝트 멤버 권한 체크 추가
- **[높음] 프로젝트 삭제 시 첨부파일 미삭제**: cascade DB 삭제 외에 실파일도 함께 삭제
- **[높음] 첨부파일 권한 fallback ValueError**: 시스템 역할→프로젝트 역할 매핑으로 500 에러 방지
- **[높음] 테스트런 test_plan_id 미검증**: 같은 프로젝트 플랜인지 검증, 크로스 프로젝트 연결 차단
- **[높음] 전체 시트 보기 no 값 오염**: 원본 no 보존(`_originalNo`), autoSave 시 복원 전송
- **[중간] 프로젝트 admin 사용자 목록 조회**: `/available-users` 엔드포인트 신규 추가
- **[중간] 멤버 추가 역할 리셋값**: `"viewer"` → `"tester"`로 수정
- **[중간] TC 수정 시 시트 무결성 검사**: update/bulk_update에도 폴더·존재 여부 검증 적용
- **[중간] 대시보드 heatmap 집계 불일치**: 전체 모드를 TC별 최신 런 결과 기준으로 변경

### 재검증 수정 (3건)

- 신규 프로젝트 첫 TC 생성 회귀 수정 (기본 시트 자동 생성)
- 빈 상태 placeholder 새 실행 버튼 권한 가드 추가
- 테스트런 삭제 버튼 admin 전용(`canDeleteRun`) 분리

### 추가 수정

- 리포트 카테고리 요약에 NA/NS 집계 추가
- E2E/매뉴얼 "Excel Import" → "Import" 동기화

### 테스트

- 보안 수정 대상 TC **28건 신규 추가** (9개 클래스)
- 프론트 단위 테스트 동기화 (ProjectMembers, TestRunManager)
- **최종 결과**: vitest 358 passed, backend pytest 144 passed, E2E 93 passed

---

## v1.0.1.0 (2026-04-01) - 로그인 유지 기능 및 토큰 만료 개선

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 1.0.0.1 | **1.0.1.0** | 로그인 유지 기능 추가 |
| Frontend | 1.0.0.1 | **1.0.1.0** | 로그인 유지 체크박스 추가, 매뉴얼 스크린샷 갱신 |
| Backend | 1.0.0.0 | **1.0.1.0** | remember_me 파라미터, 토큰 만료 기본값 변경 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 버그 수정
- **로그인 유지 기능 부재**: "로그인 유지" 체크박스 추가, 체크 시 서버 재시작 전까지 로그인 무기한 유지
- **토큰 만료 시간 과소**: 기본 만료 시간 2시간 → 72시간(3일)으로 변경

### 문서
- **사용자 매뉴얼**: 로그인 유지 기능 설명 추가, 로그인 페이지 스크린샷 갱신

---

## v1.0.0.1 (2026-03-31) - 설치 가이드 개선 및 체크박스 수정

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 1.0.0.0 | **1.0.0.1** | Frontend patch |
| Frontend | 1.0.0.0 | **1.0.0.1** | 테스트 수행 체크박스 수정 |
| Backend | 1.0.0.0 | 1.0.0.0 | 변경 없음 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 버그 수정
- **테스트 수행 전체 선택 체크박스 누락**: rowSelection 설정 충돌로 헤더 전체 선택 체크박스가 표시되지 않던 문제 수정
- **Mac 체크박스 더블클릭 이슈**: singleClickEdit과 체크박스 이벤트 충돌 방지 (suppressRowClickSelection 추가)

### 개선
- **테스트 수행 빈 상태 UX**: 수행 목록이 없을 때 화면 가운데에 안내 문구 + 생성 버튼 표시
- **+ New Test Run 버튼 개선**: 영문 → 한글("새 테스트 수행 만들기"), dashed 스타일 → accent 색상 통일
- **빈 상태 문구 통일**: 사이드바/메인 영역 모두 "등록된 테스트 수행이 없습니다."로 일치

### 문서
- **README 설치 가이드 재구성**: 단계별(1~4) 구성, SECRET_KEY 변경 전/후 예시 추가
- **Python 요구사항 수정**: 3.12+ → 3.11+ (실제 테스트 환경 기준)
- **.env.example 상세화**: 전체 환경변수 5개 + 한글 설명/예시 추가
- **AI Agent 설치 팁 추가**: README에 AI Agent 활용 안내 문구 추가

---

## v1.0.0.0 (2026-03-24) - 오픈소스 정식 공개

### 컴포넌트 버전

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.7.1.0 | **1.0.0.0** | 정식 공개 릴리즈 |
| Frontend | 0.7.1.0 | **1.0.0.0** | MD Import, 매뉴얼 재구성, Import 버튼 |
| Backend | 0.7.1.0 | **1.0.0.0** | Markdown Import 파서, 엔드포인트 확장 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 신규 기능
- **Markdown(.md) Import**: # 헤딩 → 시트명, 표준 Markdown 테이블 파싱, HEADER_MAP 자동 매핑, 이스케이프 파이프 지원
- **포트폴리오**: HTML 단일 파일 + PPTX 14슬라이드 (portfolio/)

### 개선
- **이슈 관리 체계 개편**
  - 심각도 4단계 → 5단계 (Block / Critical / Major / Minor / Trivial)
  - 영역 5가지 (Frontend / Backend / DB / 보안 / 기타)
  - 버그/개선 작성 양식 표준화 (94건 전체 설명 입력 완료)
  - 컴포넌트 버전 기록, 발생/수정 버전 분리
  - Issue_list.xlsx 전면 재구성 (컬러 코딩, 자동 필터)
- **GitHub Issues 동기화**: 94건 엑셀 ↔ GitHub 1:1, 라벨 체계 통일 (분류+영역+심각도)
- **GitHub Issue Template**: 버그/개선/보안 3종 (.md 형식)
- **Import 버튼**: "Excel Import" → "Import" (Excel/CSV/MD 통합)

### 문서
- **사용자 매뉴얼**: 섹션 순서 재구성 (20개 → 18개), 번호 체계 정비, Import 통합 섹션
- **운영 매뉴얼**: 버전/기술 스택 최신화, Docker 제거, CSRF/AGPL-3.0 추가
- **CONTRIBUTING.md**: 기여 가이드 신규 작성
- **rules/**: 5개 규칙 파일 전체 최신화 (심각도, 영역, 릴리즈 플로우)
- **skills/**: 15개 Claude Code 스킬 점검 및 업데이트

### 테스트
- Frontend Unit (Vitest): 358/358 PASS
- E2E (Playwright): 93/93 PASS
- Backend API (pytest): 116/116 PASS
- **합계: 567/567 ALL PASS**

---

## v0.7.1.0 (2026-03-23) - 품질 게이트 수정 + 라이선스 변경 + README 정비

> 빌드/린트/테스트 전체 통과 + AGPL-3.0 전환 + README 정확성 개선 + 전체 테스트 567건 PASS

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.7.0.0 | **0.7.1.0** | 품질 게이트 수정, 라이선스 변경 |
| Frontend | 0.7.0.0 | **0.7.1.0** | 빌드 타입 오류 수정, lint 정리, 대시보드 차트 색상 수정, E2E 셀렉터 수정 |
| Backend | 0.7.0.0 | **0.7.1.0** | pytest 수집 오류 해결, 마이그레이션 로깅 추가, .env.example 생성 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 버그 수정

- **BUG-056**: 프론트 빌드 실패 - 테스트 파일 타입 오류 9개 수정 (잘못된 필드명, 누락 프로퍼티, 미사용 import)
- **BUG-057**: vite.config.ts writeHead 타입 오류 수정
- **BUG-058**: 대시보드 차트 색상 전부 검은색 - Chart.js가 CSS 변수 미지원, 라이트/다크 hex 값으로 분리
- **BUG-059**: ESLint가 coverage/e2e 디렉토리까지 검사 - globalIgnores 추가
- **BUG-060**: 소스 파일 lint 에러 7개 (빈 블록, 삼항식을 표현식으로 사용)
- **BUG-061**: backend pytest 수집 단계 실패 - 독립 스크립트(test_v060_*.py)가 모듈 레벨에서 login() 호출, collect_ignore 추가
- **BUG-062**: 마이그레이션 예외를 삼키고 로그 없음 - logger.warning/debug 추가
- **BUG-063**: E2E 시트 트리 테스트 2개 실패 - 셀렉터 `루트 시트 추가` → `시트 추가` 수정

### 개선

- **ENH-014**: 라이선스 MIT → AGPL-3.0 변경 (웹앱 SaaS 무임승차 방어)
- **ENH-015**: README 섹션명 개선 (왜 이 도구인가 → 기존 도구와의 비교, 빠른 시작 → 환경설정 방법)
- **ENH-016**: README 비교 테이블 HTML 전환 (YM TestCase 열 파란색)
- **ENH-017**: README SECRET_KEY 설명 보강 (용도, 미설정 시 영향)
- **ENH-018**: README 사전 요구사항 추가 (Python 3.12+, Node.js 18+, Git)
- **ENH-019**: README에서 존재하지 않는 Docker 관련 내용 제거
- **ENH-020**: backend/.env.example 생성
- **ENH-021**: .gitignore에 coverage 추가
- **ENH-022**: 테스트 파일에 any/react-refresh lint 룰 완화

### 문서

- 대시보드 스크린샷 5장 재촬영 (라이트 + 다크모드)
- README 디렉토리 구조 정확성 수정

### 테스트

- Frontend (Vitest): 358/358 PASS
- E2E (Playwright): 93/93 PASS
- Backend (pytest): 116/116 PASS
- 합계: **567/567 ALL PASS**

---

## v0.7.0.0 (2026-03-21) - Git 관리 + GitHub 공개 + 브랜딩

> 브랜딩 변경 (TC Manager → YM TestCase) + Git 공개 준비 + 테스트 293건 PASS

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.6.0.0 | **0.7.0.0** | Git 공개 준비, 브랜딩 통합 |
| Frontend | 0.6.0.0 | **0.7.0.0** | YM TestCase 브랜딩, children 방어 코드, 테스트 수정 |
| Backend | 0.6.0.0 | **0.7.0.0** | API 타이틀 변경, 크레덴셜 환경변수화 |
| Database | 0.3.0.0 | 0.3.0.0 | 변경 없음 |

### 변경 내역

- **브랜딩**: TC Manager → YM TestCase (Your Method, Your Test Case Manager)
- **.gitignore**: DB, 캐시, 개인 파일 제외
- **.env.example**: 환경변수 문서화
- **크레덴셜 제거**: 하드코딩 비밀번호 → 환경변수 전환
- **Docker Compose**: 포트 매핑 수정 (8008:8000)
- **README.md**: 설치 가이드 + 스크린샷 7장
- **MIT LICENSE** 추가
- **run_dev.sh**: Mac/Linux 지원
- **테스트 수정**: 트리 구조 변경 반영 (children 방어, 셀렉터 수정)

### 테스트

- Frontend (Vitest): 177/177 PASS
- Backend (pytest): 116/116 PASS
- 합계: **293/293 ALL PASS**

---

## v0.6.0.0 (2026-03-20) - 시트 트리, 커스텀 필드, 테스트 플랜, Jira CSV, 고급 필터

> TC 관리 본질 기능 5개 구현 + 326건 PASS

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.5.0.0 | **0.6.0.0** | 5대 기능 추가 |
| Frontend | 0.5.0.0 | **0.6.0.0** | 시트 트리 사이드바, 커스텀 필드 UI, 필터 패널, 테스트 플랜 |
| Backend | 0.5.0.0 | **0.6.0.0** | 시트 트리 API, 커스텀 필드, 테스트 플랜, CSV Import, 필터 API |
| Database | 0.3.0.0 | 0.3.0.0 | parent_id, custom_fields, test_plan_id 컬럼 추가 (마이그레이션) |

### 주요 기능

1. **시트 트리 구조** - N-depth 계층, VS Code 사이드바 UI
2. **커스텀 필드** - 6타입 (text, number, select, multiselect, checkbox, date)
3. **테스트 플랜/마일스톤** - 릴리즈 단위 수행 관리
4. **Jira CSV Import** - 35+ 헤더 매핑, CP949/UTF-8 BOM 자동 감지
5. **고급 필터 + 저장된 뷰** - AND/OR 다중 조건, 6개 연산자

### 테스트

- Python API: 139/139 PASS
- 엣지케이스: 116/116 PASS
- Playwright E2E: 71/71 PASS
- 합계: **326/326 ALL PASS**

---

## v0.5.0.0 (2026-03-19) - 시트 관리, 자동저장, 테스트 자동화 312건

> 신규 기능 5개 + DB 스키마 변경 + 테스트 0개 → 312개 구축

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.4.1.0 | **0.5.0.0** | 대규모 신규 기능 + 테스트 자동화 |
| Frontend | 0.4.1.0 | **0.5.0.0** | 시트 UI, 자동저장, 벌크 삭제, 임포트 개선, 매뉴얼 업데이트 |
| Backend | 0.4.1.0 | **0.5.0.0** | 시트 CRUD API, 벌크 삭제 API, 임포트 덮어쓰기, deleted_at 필터 |
| Database | 0.2.0.0 | **0.3.0.0** | test_case_sheets 테이블 신설, test_cases.sheet_name 컬럼 추가 |

### 신규 기능

**1. 시트 관리**
- 프로젝트 내 TC를 시트 단위로 분류 (엑셀 시트 탭과 동일)
- 빈 프로젝트에서 "시트 추가" 또는 "Excel Import"로 시작
- 하단 탭 바: 시트 전환, 전체 보기 (2개+ 시트), + 버튼으로 새 시트 추가
- 시트 삭제 (× 버튼, TC 소프트 삭제)
- 시트별 No 1부터 시작, 전체 보기에서 시트 순서대로 연속 번호
- "기본" 시트 1개뿐이면 탭 바 숨김
- TC 관리 + 테스트 수행 양쪽에 시트 탭 적용

**2. 자동저장 (Google Sheets 방식)**
- 저장 버튼 제거, modifiedIds 상태 제거
- 셀 편집 → 디바운스 300ms → API 자동 호출
- 행 추가 → 즉시 API 생성
- Undo/Redo, 찾기/바꾸기, 일괄 변경, Ctrl+D, TC ID 자동채우기 모두 자동저장 연동

**3. Excel Import 개선**
- 멀티시트 임포트: 시트 선택 모달 (체크박스)
- 동일 TC ID 덮어쓰기 (upsert): 기존 TC 보존, 변경분만 업데이트
- 중복 시 사전 알림: "기존 N개 덮어쓰기" 팝업
- 섹션 헤더 행 자동 필터링 (머지 셀 감지)
- 시트 레코드 자동 생성 (import 시 TestCaseSheet 테이블에 등록)
- Import Preview API: 시트 목록 + TC 수 + 기존 중복 수 반환
- HEADER_MAP 한국어 확장: 사전조건/테스트 가이드, 심각도, 버그/이슈, 결과, 자동화

**4. 벌크 삭제**
- TC 벌크 삭제 API: `DELETE /testcases/bulk?ids=1,2,3` (237개 280ms)
- 프로젝트 목록 일괄 삭제: 테이블 체크박스 + 전체 선택 + "N개 삭제" 버튼

**5. 테스트 자동화 (0 → 312개)**
- Vitest 177개: 21개 파일 (컴포넌트 단위 + API 함수 + 시트 탭 + 자동저장)
- Playwright E2E 19개: 4개 파일 (인증, 프로젝트, TC 관리, 관리자)
- pytest 116개: 백엔드 통합 테스트 (기존 70 + 신규 46)
- 자동화 커버율: 65% (237개 체크리스트 중 155개)

### Backend 변경사항

**신규 API (7개)**
- `GET /api/projects/{id}/testcases/sheets` - 시트 목록 (TC 수 포함)
- `POST /api/projects/{id}/testcases/sheets` - 시트 생성
- `DELETE /api/projects/{id}/testcases/sheets/{name}` - 시트 삭제
- `POST /api/projects/{id}/testcases/import/preview` - Import 미리보기
- `DELETE /api/projects/{id}/testcases/bulk` - TC 벌크 삭제
- Import API 개선: `sheet_names` 파라미터, upsert 로직

**버그 수정 (4건)**
- `overview.py` - deleted_at 필터 누락 → TC 카운트 부풀림
- `dashboard.py` - deleted_at 필터 누락 → 라운드 비교 부정확
- `testruns.py` - deleted_at 필터 누락 → 삭제된 TC가 TestResult에 포함
- `schemas.py` - ProjectCreate에 `name: min_length=1` 추가 (빈 이름 방어)

**코드 리팩토링**
- `_parse_sheet()` 함수 분리 (임포트 로직 재사용)
- `_detect_header_row()`, `_count_tc_rows()` 유틸 함수 분리
- 섹션 헤더 감지: depth3 병합 전 unique_vals 검사

### Frontend 변경사항

**TC 관리 (TestCaseGrid.tsx)**
- 시트 탭 바 (하단), 시트 추가/삭제 UI
- 빈 프로젝트 시트 추가 화면
- 자동저장: autoSaveRow (디바운스 300ms), autoSaveRowRef (TDZ 버그 수정)
- 행 추가 즉시 API 호출, 저장 버튼 제거
- ag-grid rowSelection v35 API 전환 (multiRow + checkboxes + headerCheckbox)
- Import: 시트 선택 모달, 중복 경고, 시트 자동 전환

**테스트 수행 (TestRunManager.tsx)**
- 시트 탭 바 (우측 패널 하단)
- 시트별 결과 필터링
- 전체 보기 시 시트 순서대로 연속 번호
- 첨부파일 lazy load (행 포커스 시만 로드, 기존: 전체 동시 API 호출)

**프로젝트 목록 (ProjectListPage.tsx)**
- 테이블 행 체크박스 + 전체 선택 + 일괄 삭제 버튼

**매뉴얼 (UserManualPage.tsx)**
- 6-2. 시트 관리 섹션 신규
- 3-4. 프로젝트 일괄 삭제 섹션 추가
- 자동저장 안내로 변경 (저장 버튼 설명 제거)
- Excel Import 설명 업데이트
- 상단 바/테이블 헤더 색상 수정 (라이트 모드 가시성)

**운영 매뉴얼 (AdminManualPage.tsx)**
- API 엔드포인트 6개 추가

**대시보드 (Dashboard.tsx)**
- 카드/차트/테이블에 border 추가 (라이트 모드 가시성)
- 도넛 차트 borderColor: transparent 추가

### Database 변경사항

**신규 테이블**
- `test_case_sheets`: 프로젝트별 시트 관리
  - `id`, `project_id`, `name`, `sort_order`, `created_at`

**컬럼 추가**
- `test_cases.sheet_name`: VARCHAR(100), DEFAULT '기본', NOT NULL

### 변경 파일 목록

**Backend (10개)**
- `models.py`, `schemas.py`
- `routes/testcases.py`, `routes/overview.py`, `routes/dashboard.py`, `routes/testruns.py`
- `test_security.py`

**Frontend (15개)**
- `api/index.ts`, `types/index.ts`
- `components/TestCaseGrid.tsx`, `components/TestRunManager.tsx`, `components/Dashboard.tsx`
- `pages/ProjectListPage.tsx`, `pages/UserManualPage.tsx`, `pages/AdminManualPage.tsx`
- `vite.config.ts`, `package.json`, `playwright.config.ts`
- `src/test/` (21개 파일), `e2e/` (4개 파일)

---

## v0.4.1.0 (2026-03-18) - 전수 검증 27건 수정 (보안+안정성)

> Backend 14건 + Frontend 13건 버그/보안 수정

### Backend (14건)

**심각 (3건)**
- `routes/history.py` - 이력 조회 프로젝트 멤버 권한 체크 추가
- `routes/attachments.py` - ROLE_HIERARCHY에서 모델에 없는 "editor" 제거
- `auth.py` - user_id 파싱 ValueError/TypeError 예외 처리 추가 (500→401)

**높음 (4건)**
- `routes/dashboard.py` - not_started를 실제 "NS" 결과 건수로 카운트 (기존: total에서 빼기)
- `routes/testruns.py` - 엑셀 열 26개 초과 시 get_column_letter() 사용
- `routes/search.py` - 프라이빗 프로젝트 검색 필터 추가 (is_private + 멤버 체크)
- `routes/reports.py` - PDF 한글 폰트 탐색 경로에 NanumGothic 추가 + 미발견 시 경고 로그

**중간 (4건)**
- `routes/members.py` - joinedload()로 N+1 쿼리 해소
- `routes/dashboard.py` - 미사용 매개변수 total_tc 제거
- `routes/dashboard.py` - 메모리 로드 최적화 TODO 주석
- `routes/auth.py` - 레이트리밋 O(n) 탐색 TODO 주석

**낮음 (3건)**
- `routes/search.py` - limit 매개변수화 (기본 100, 최대 500)
- `routes/testcases.py` - depth3 병합 로직 의도 주석

### Frontend (13건)

**심각 (2건)**
- `MarkdownCell.tsx` - DOMPurify 이미 적용 확인 (수정 불필요)
- `api/client.ts` - localStorage JWT + CSRF 미적용 TODO 주석 추가

**높음 (5건)**
- 5개 컴포넌트 catch 블록에 에러 로깅 추가 (TestCaseGrid 8곳, Dashboard 1곳, ReportView 3곳, CompareView 1곳, AdminPage 7곳, ProjectListPage 2곳)
- `Header.tsx` - searchTimer useEffect cleanup 추가
- `Header.tsx` - catch ignore → console.warn 변경

**중간 (4건)**
- `TestCaseGrid.tsx` - 경쟁 조건 TODO 주석
- `ProjectListPage.tsx` - 프로젝트 이름 100자 제한
- `TestCaseGrid.tsx` - 낙관적 업데이트 TODO 주석
- `ProjectListPage.tsx` - Date 파싱 실패 방어 (isNaN 체크)

**낮음 (2건)**
- 전체 console.error 로깅 (위에서 함께 처리)
- 접근성 TODO 주석

---

## v0.4.0.0 (2026-03-16) - 권한 체계 개편 및 관리 기능 강화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.3.0.0 | **0.4.0.0** | 권한 체계 전면 개편, 다수 신규 기능 |
| Frontend | 0.3.0.0 | **0.4.0.0** | 권한 UI 전면 수정, 회원가입 개선, 관리 페이지 확장 |
| Backend | 0.2.1.1 | **0.4.0.0** | 역할 체계 변경, API 다수 추가/수정 |
| Database | 0.1.0.0 | **0.2.0.0** | UserRole/ProjectRole 열거형 변경, 자동 마이그레이션 |

### 권한 체계 개편 (Breaking Change)

**기존 (4단계 플랫 구조)**
- `admin` / `editor` / `tester` / `viewer`

**신규 (2-tier 역할 체계)**

| 시스템 역할 | 설명 | 프로젝트 접근 |
|---|---|---|
| `admin` (시스템 관리자) | 최상위 권한, 전체 시스템 관리 | 모든 프로젝트 admin |
| `qa_manager` (QA 관리자) | 프로젝트 생성·관리, 사용자 목록 조회 | 모든 프로젝트 admin |
| `user` (일반 사용자) | 배정된 프로젝트만 접근 | 프로젝트별 역할 적용 |

| 프로젝트 역할 | 설명 |
|---|---|
| `admin` (프로젝트 관리자) | TC 읽기/쓰기, 테스트 런 삭제, 멤버 관리 |
| `tester` (프로젝트 테스터) | TC 읽기 전용, 테스트 수행만 가능 |

- DB 자동 마이그레이션: 서버 시작 시 기존 역할을 새 체계로 변환
  - `viewer`/`tester` → `user`, `editor` → `qa_manager`
  - 프로젝트: `viewer` → `tester`, `editor` → `admin`

### Backend 변경사항

**권한 관련**
- `auth.py` 전면 재작성: `SYSTEM_ROLE_HIERARCHY` + `PROJECT_ROLE_HIERARCHY` 분리
- `get_project_role()`: admin/qa_manager는 모든 프로젝트에 암묵적 admin 권한
- `check_project_access()`: 일반 사용자는 ProjectMember에 등록된 프로젝트만 접근
- `role_required()`: 시스템 역할 계층만 검사
- 프로젝트 생성 권한: `admin` → `qa_manager` 이상

**신규 API**
- `GET /api/auth/check-username` - 아이디 중복 확인
- `PUT /api/auth/users/{user_id}/reset-password` - 비밀번호 초기화 (임시 PW 발급 + 강제 변경)
- `POST /api/projects/assign-all` - 사용자를 모든 프로젝트에 일괄 배정
- `GET /api/projects/all-assignments` - 전체 사용자의 프로젝트 배정 현황 조회

**대시보드 수정**
- "전체" 모드: 모든 run의 결과를 합산 (기존: 최근 run 1개만 표시)
- summary, priority, category, assignee, heatmap 5개 엔드포인트 모두 수정
- `deleted_at.is_(None)` 필터 추가 (소프트 삭제 TC 제외)

**오류 메시지 한글화**
- 로그인/회원가입/비밀번호 변경 오류 메시지 전체 한글 전환

**변경 파일**
- `auth.py`, `models.py`, `schemas.py`, `main.py`
- `routes/auth.py`, `routes/projects.py`, `routes/testcases.py`, `routes/testruns.py`
- `routes/dashboard.py`, `routes/members.py`, `routes/overview.py`, `routes/search.py`

### Frontend 변경사항

**회원가입 개선**
- 실시간 아이디 중복 확인 (400ms 디바운스, 상태 표시: 확인 중/사용 가능/사용 불가)
- 회원가입 완료 토스트 중복 제거 (2개 → 1개)
- 토스트 위치 변경 (`top-right` → `top-center`)

**관리자 페이지 확장**
- 시스템 역할 드롭다운: 일반 사용자 / QA 관리자 / 시스템 관리자
- 프로젝트 배정 모달: 개별 프로젝트 추가/제거, 역할 변경, 전체 일괄 배정
- **프로젝트 배정 현황 인라인 표시**: 사용자 목록에서 배정된 프로젝트를 태그로 즉시 확인
  - 파란 태그: 관리자 역할 / 회색 태그: 테스터 역할
  - "미배정" 상태 표시
- 비밀번호 초기화 기능 (임시 PW 표시 + 클립보드 복사)

**권한 기반 UI 제어**
- TC 그리드: `project.my_role === "admin"`일 때만 편집 가능 (추가/삭제/복사/수정/가져오기/저장)
- 테스트 런: 관리자만 런 삭제 가능
- 프로젝트 목록: QA 관리자 이상만 프로젝트 생성 버튼 표시
- 프로젝트 멤버: 역할 선택지를 `tester`/`admin`으로 변경
- 헤더: 역할별 뱃지 색상 구분, 한글 역할명 표시

**비밀번호 분실 안내**
- 로그인 페이지에 "관리자에게 초기화를 요청하세요" 안내 텍스트 추가
- 비밀번호 변경 모달 인라인 에러 메시지 전환 (토스트 → 인라인)

**변경 파일**
- `api/index.ts`, `types/index.ts`, `contexts/AuthContext.tsx`, `main.tsx`
- `pages/AdminPage.tsx`, `pages/RegisterPage.tsx`, `pages/LoginPage.tsx`, `pages/ProjectListPage.tsx`, `pages/ProjectPage.tsx`
- `components/Header.tsx`, `components/TestCaseGrid.tsx`, `components/TestRunManager.tsx`
- `components/ProjectMembers.tsx`, `components/ChangePasswordModal.tsx`

### Database 변경사항

- `UserRole` 열거형: `viewer, tester, editor, admin` → `user, qa_manager, admin`
- `ProjectRole` 열거형: `viewer, tester, editor, admin` → `tester, admin`
- 기본값 변경: 신규 사용자 `user`, 신규 프로젝트 멤버 `tester`
- 시작 시 자동 마이그레이션 (`_migrate_roles()`)

---

## v0.3.0.0 (2026-03-16) - 매뉴얼 및 문서화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.2.1.1 | **0.3.0.0** | 신규 기능 (매뉴얼 페이지) |
| Frontend | 0.2.1.0 | **0.3.0.0** | 페이지 2개 추가, 헤더 수정, 라우팅 추가 |
| Backend | 0.2.1.1 | 0.2.1.1 | 변경 없음 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Frontend 변경사항

**신규 기능**
- **사용자 매뉴얼 페이지** (`/manual`)
  - 14개 섹션 (개요, 로그인, 프로젝트, TC 관리, 테스트 수행, 비교, 대시보드, 리포트, 설정, 테마, 단축키, 역할별 권한)
  - 좌측 고정 목차 네비게이션
  - 실제 앱 캡처 스크린샷 23장 포함
  - 모든 로그인 사용자 접근 가능

- **운영 매뉴얼 페이지** (`/admin-manual`)
  - 12개 섹션 (시스템 구성, 설치, 환경변수, DB, 사용자 관리, 권한 체계, API 52개 목록, 보안, 트러블슈팅, 백업)
  - Admin 역할 전용 (비관리자 접근 시 자동 리다이렉트)

- **헤더 "도움말" 버튼 추가**: 사용자 매뉴얼 페이지로 이동

**변경 파일**
- `App.tsx` - `/manual`, `/admin-manual` 라우트 추가
- `Header.tsx` - 도움말 버튼 추가
- `pages/UserManualPage.tsx` - 신규
- `pages/AdminManualPage.tsx` - 신규
- `public/manual-images/` - 캡처 이미지 23장

### 문서
- Confluence 사내 업무 가이드 초안 (`docs/confluence_draft.md`)
- TC 리그레션 체크리스트 한글화 및 확장 (46건 → 150건)
- 릴리즈 노트 신규 작성 (`Release_note.md`)
- 이슈 목록 신규 작성 (`Issue_list.xlsx`)

---

## v0.2.1.1 (2026-03-16) - 보안 강화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.2.1.0 | **0.2.1.1** | 보안 패치 |
| Frontend | 0.2.1.0 | 0.2.1.0 | 변경 없음 |
| Backend | 0.2.1.0 | **0.2.1.1** | 보안 취약점 수정 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Backend 변경사항

**보안 수정**
- **첨부파일 API 프로젝트 권한 검증**: 업로드/다운로드/삭제 시 프로젝트 멤버 여부 확인
- **확장자 없는 파일 업로드 차단**: 확장자가 없는 파일은 업로드 거부
- **다운로드 MIME 타입 안전 처리**: 안전하지 않은 MIME 타입은 `application/octet-stream` 강제
- **Rate Limiting 수정**: 성공 시도 미카운트, 성공 시 실패 카운터 초기화
- **SECRET_KEY 하드코딩 제거**: 프로덕션 환경에서 환경변수 미설정 시 서버 시작 실패
- **CORS 강화**: 와일드카드(`*`) → 특정 도메인 화이트리스트
- **보안 테스트 정비**: pytest 기반 36개 테스트 통과

### 리뷰
- 제품 리뷰 수행 (`product_review_2026-03-16.md`)
- 보안 리뷰 3차 수행 (`security_review_2026-03-16.md`)
- OWASP Top 10 기반 취약점 점검

---

## v0.2.1.0 (2026-03-09) - 코드 리뷰 반영 및 안정화

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.2.0.0 | **0.2.1.0** | 빌드 실패 수정, 중요 버그 수정 |
| Frontend | 0.2.0.0 | **0.2.1.0** | 빌드 에러 수정, 검색 네비게이션, 다크 모드 통일 |
| Backend | 0.2.0.0 | **0.2.1.0** | 첨부파일 물리 삭제 연결 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Frontend 변경사항

**버그 수정**
- **TypeScript 빌드 에러 해결**
  - `TestRunManager.tsx` handleDeleteAttachment 미사용 변수 제거
  - `doesExternalFilterPass` 파라미터 타입 수정 (`IRowNode<TestResult>`)
  - Vite 프로덕션 빌드 정상 통과

- **글로벌 검색 TC 위치 이동**
  - 검색 결과 클릭 시 `?tab=tc&highlight=TC_ID` 파라미터 전달
  - `TestCaseGrid`에서 해당 행 자동 선택 및 스크롤

- **관리자 페이지 권한 가드**
  - `useEffect`로 Admin 여부 사전 체크
  - 비관리자 접근 시 API 호출 없이 안내 메시지 표시

**개선**
- **한글 인코딩 대응**: `vite.config.ts`에 `charsetPlugin` 추가, `index.html`에 `lang="ko"`
- **다크 모드 테마 통일**: 6개 컴포넌트의 하드코딩 인라인 색상 → CSS 변수 전환

### Backend 변경사항

**버그 수정**
- **첨부파일 물리 삭제 연결**: 테스트 런 삭제 시 `UPLOAD_DIR` 기반 실제 파일 경로 구성하여 물리 파일 삭제

---

## v0.2.0.0 (2026-03-06) - 핵심 기능 구현 완료

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | 0.1.0.0 | **0.2.0.0** | 다수 신규 기능 추가 |
| Frontend | 0.1.0.0 | **0.2.0.0** | 비교 뷰, 대시보드, 단축키, 타이머, 다크 모드 등 |
| Backend | 0.1.0.0 | **0.2.0.0** | 대시보드 API, 비교 API, Excel Export API 등 |
| Database | 0.1.0.0 | 0.1.0.0 | 변경 없음 |

### Frontend 변경사항

**테스트 수행**
- **키보드 단축키** (P/F/B/N): 결과 셀에서 키 입력으로 빠른 결과 입력, 자동 다음 행 이동
- **TC 수행 타이머**: 행 포커스 시 자동 타이머 시작, 행 변경 시 누적 기록
- **Undo/Redo**: Ctrl+Z로 결과 변경 실행 취소 (최대 200단계 스택)
- **드래그 앤 드롭 이미지 첨부**: 그리드 영역에 이미지 드롭 → 포커스된 행에 첨부
- **결과 Excel Export**: 테스트 수행 결과를 서식 적용된 엑셀 파일로 다운로드

**분석**
- **비교 뷰**: 두 테스트 런 간 결과 비교, 변경/리그레션/개선 자동 감지, 필터링
- **대시보드**: 요약 카드, 결과 분포 도넛 차트, 라운드별 비교 바 차트, 추이 라인 차트
- **실패 히트맵**: 카테고리 × 우선순위 매트릭스에서 실패 건수 색상 강도 표시
- **담당자별 현황**: 담당자별 진행률/완료율 테이블

**기타**
- **다크 모드**: ThemeContext + CSS 변수 기반, 헤더 토글 버튼
- **그리드 정렬/필터 개선**: 결과/카테고리/우선순위 드롭다운 필터 + 텍스트 검색 + 초기화
- **텍스트 줄바꿈**: `white-space: pre-wrap` 전역 적용

### Backend 변경사항

- **대시보드 API**: summary, priority, category, rounds, assignee, heatmap 6개 엔드포인트
- **비교 API**: 두 런 간 결과 비교 데이터
- **Excel Export API**: 테스트 런 결과 엑셀 다운로드
- **전체 현황 API**: 프로젝트 횡단 집계

---

## v0.1.0.0 (2026-03-05 이전) - MVP 초기 구현

| 컴포넌트 | 이전 | 이후 | 변경 사유 |
|---|---|---|---|
| System | - | **0.1.0.0** | 최초 릴리즈 |
| Frontend | - | **0.1.0.0** | 최초 구현 |
| Backend | - | **0.1.0.0** | 최초 구현 |
| Database | - | **0.1.0.0** | 스키마 최초 생성 |

### Frontend

- 로그인/회원가입 페이지
- 프로젝트 목록 페이지 (전체 현황, 프로젝트 카드)
- 프로젝트 상세 페이지 (탭 구조: TC 관리, 테스트 수행, 비교, 대시보드, 리포트, 설정)
- TC 관리 그리드 (AG Grid 인라인 편집, Excel Import/Export)
- 테스트 런 관리 (생성/복제/완료/삭제, 결과 기록)
- 첨부파일 업로드/다운로드/미리보기
- 리포트 뷰 (PDF/Excel 다운로드)
- 글로벌 검색 (헤더 검색바)
- 관리자 페이지 (사용자 목록, 역할 변경)

### Backend

- **인증**: 회원가입/로그인/로그아웃, JWT (HS256), bcrypt, 최초 가입자 Admin 자동 부여
- **RBAC**: Admin/Editor/Tester/Viewer 4단계 + 프로젝트별 역할
- **프로젝트**: CRUD, 공개/비공개, Jira Base URL, 멤버 관리
- **TC**: CRUD, 벌크 업데이트, 소프트 삭제/복원 (7일), 변경 이력 추적
- **Excel Import**: 50+ 영문/한글 헤더 자동 매핑, 스마트 헤더 감지, 병합 셀 처리
- **테스트 런**: 생성/복제/완료/삭제, 결과 벌크 저장
- **첨부파일**: 업로드/다운로드/삭제, 이미지/문서/아카이브 (50MB), UUID 파일명
- **리포트**: JSON/PDF/Excel 생성, 한글 폰트 지원 (Malgun Gothic)
- **글로벌 검색**: 전체 프로젝트 TC 검색 (100건 제한)

### Database

- **스키마 v0.1.0.0**: 8개 테이블 초기 생성
  - `users`, `projects`, `test_cases`, `test_runs`, `test_results`, `attachments`, `project_members`, `test_case_history`
- SQLAlchemy `create_all()` 기반 자동 생성
- SQLite (`tc_manager.db`)

### 인프라

- Backend: FastAPI + Uvicorn (포트 8000)
- Frontend: React 18 + TypeScript + Vite (포트 5173)
- Docker / Docker Compose 지원
- Swagger API 문서 자동 생성 (`/docs`)

---

## 미구현 기능 (Backlog)

| ID | 기능 | 우선순위 | 영향 컴포넌트 | 비고 |
|---|---|---|---|---|
| #2 | Jira 이슈 자동 생성 (FAIL 시) | 중간 | BE | 외부 Jira API 연동 필요 |
| #12 | Slack/Email 알림 | 낮음 | BE | 외부 연동 필요 |
| #13 | 실시간 협업 편집 (WebSocket) | 낮음 | FE + BE | 인프라 구성 필요 |
| #14 | 코멘트/스레드 | 중간 | FE + BE + DB | TC별 토론 기능 |
| #15 | @멘션 + 알림 | 낮음 | FE + BE + DB | FAIL 케이스 담당자 지정 |
| #16 | TC 버전 관리 | 중간 | FE + BE | 변경 이력 diff 뷰 |
| #17 | 테스트 계획 관리 | 중간 | FE + BE + DB | 스프린트/마일스톤 범위 |
| #18 | API 자동화 연동 | 높음 | BE + DB | Playwright/pytest 결과 자동 기록 |
| #19 | 태그/라벨 시스템 | 낮음 | FE + BE + DB | 자유 형식 TC 태깅 |

---

## 알려진 이슈

> 상세 내역은 `Issue_list.xlsx` 참고
> 최종 검증일: 2026-03-16

### 현황: Open 3건 / Fixed 31건 / Deferred 1건

**Open (3건)**
- ENH-001: Alembic 마이그레이션 미도입 - `create_all()` + 수동 ALTER TABLE 사용 중 (프로덕션 전 필수)
- ENH-002: PostgreSQL 전환 준비 - 현재 SQLite, 프로덕션 시 전환 필요
- ENH-003: N+1 쿼리 최적화 - overview/dashboard/reports 대량 데이터 시 성능 저하 가능

**Deferred (1건)**
- SEC-002: localStorage JWT 토큰 저장 - XSS 시 탈취 가능 (장기 과제, DOMPurify로 현재 리스크 낮음)

**v0.5.0.0에서 해결 (4건)**
- FIX-032: overview/dashboard/testruns에서 deleted_at 필터 누락 → 삭제된 TC가 카운트에 포함
- FIX-033: TC 삭제 시 순차 DELETE로 수십 초 소요 → 벌크 DELETE API로 280ms 이내
- FIX-034: 첨부파일 전체 동시 API 호출로 237개 TC에서 버벅임 → 행 포커스 시 lazy load
- FIX-035: 빈 이름으로 프로젝트 생성 가능 → ProjectCreate에 min_length=1 추가

**v0.4.0.0에서 해결 (5건)**
- FIX-028: 로그인 오류 메시지 영문 표시 → 한글로 변경
- FIX-029: 회원가입 시 아이디 중복 체크 미제공 → 실시간 중복 확인 추가
- FIX-030: 회원가입 완료 시 토스트 2개 중복 표시 → 1개로 수정
- FIX-031: 대시보드 "전체" 모드가 특정 run과 동일 데이터 표시 → 모든 run 결과 합산으로 수정
- ENH-004: 권한 체계 세분화 미흡 (viewer/admin 구분 불명확) → 2-tier 역할 체계로 전면 개편

---

*이 문서는 YM TestCase의 모든 릴리즈 이력을 관리합니다. 새로운 배포 시 최상단에 새 버전을 추가하세요.*
