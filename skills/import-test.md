---
name: import-test
description: Import 테스트 (Excel/CSV/Markdown 샘플 파일 생성 포함)
---

Import 기능을 테스트합니다. 샘플 파일을 생성하고 import를 실행합니다.

실행:
1. 테스트용 프로젝트 생성 (API)
2. 샘플 파일 생성:
   - 일반 CSV (TC ID, Category, Priority, Steps, Expected)
   - Jira CSV (Issue key, Summary, Component/s, Description, Assignee)
   - CP949 인코딩 CSV (한글 헤더)
   - 대량 CSV (100행)
   - **Markdown 파일** (# 헤딩으로 시트 분리, 테이블 2개)
   - **Markdown 한글 헤더** (카테고리, 우선순위, 테스트 절차, 기대 결과)
3. 각 파일 preview → import 실행
4. 결과 확인 (created, updated 건수)
5. 매핑 정확성 검증 (Jira 헤더 → TC 필드, MD 헤딩 → 시트명)
6. 덮어쓰기 테스트 (동일 TC ID 재 import → updated 확인)
7. 테스트 프로젝트 삭제

보고: 각 테스트 PASS/FAIL + 상세 결과

지원 형식:
- Excel (.xlsx, .xls) — 멀티시트, HEADER_MAP 자동 매핑
- CSV (.csv) — Jira/Xray/Zephyr, CP949/UTF-8 BOM 자동 감지
- Markdown (.md) — # 헤딩 → 시트명, 표준 Markdown 테이블, 이스케이프 파이프(\|)
