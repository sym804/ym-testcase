import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Navigate } from "react-router-dom";

export default function AdminManualPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Admin 전용
  if (!user || user.role !== "admin") {
    return <Navigate to="/projects" replace />;
  }

  return (
    <div style={s.page}>
      {/* 상단 바 */}
      <div style={s.topBar}>
        <div style={s.topLeft}>
          <span style={s.logo} onClick={() => navigate("/projects")}>
            YM TestCase
          </span>
          <span style={s.badge}>운영 매뉴얼 (Admin)</span>
        </div>
        <div style={s.topRight}>
          <span style={s.userName}>{user.display_name}</span>
          <button style={s.backBtn} onClick={() => navigate(-1)}>
            돌아가기
          </button>
        </div>
      </div>

      <div style={s.container}>
        {/* 사이드 목차 */}
        <nav style={s.toc}>
          <div style={s.tocTitle}>운영 매뉴얼 목차</div>
          <a href="#architecture" style={s.tocItem}>1. 시스템 구성</a>
          <a href="#install" style={s.tocItem}>2. 설치 및 실행</a>
          <a href="#env" style={s.tocItem}>3. 환경 변수</a>
          <a href="#database" style={s.tocItem}>4. 데이터베이스</a>
          <a href="#user-mgmt" style={s.tocItem}>5. 사용자 관리</a>
          <a href="#role-system" style={s.tocItem}>6. 역할/권한 체계</a>
          <a href="#project-mgmt" style={s.tocItem}>7. 프로젝트 운영</a>
          <a href="#file-mgmt" style={s.tocItem}>8. 파일/첨부 관리</a>
          <a href="#security" style={s.tocItem}>9. 보안 설정</a>
          <a href="#api-ref" style={s.tocItem}>10. API 엔드포인트</a>
          <a href="#troubleshoot" style={s.tocItem}>11. 트러블슈팅</a>
          <a href="#backup" style={s.tocItem}>12. 백업/복구</a>
        </nav>

        <main style={s.main}>
          {/* 1. 시스템 구성 */}
          <section id="architecture" style={s.section}>
            <h1 style={s.h1}>YM TestCase 운영 매뉴얼</h1>
            <p style={s.updatedAt}>최종 업데이트: 2026-03-24 | v0.7.1.0 | Admin 전용 문서</p>

            <h2 style={s.h2}>1. 시스템 구성</h2>
            <div style={s.archGrid}>
              <div style={s.archCard}>
                <div style={s.archTitle}>Backend</div>
                <ul style={s.archList}>
                  <li>FastAPI (Python 3.12)</li>
                  <li>SQLAlchemy 2 ORM</li>
                  <li>SQLite (기본) / PostgreSQL</li>
                  <li>JWT 인증 (httpOnly 쿠키 + CSRF 토큰)</li>
                  <li>bcrypt 비밀번호 해싱</li>
                  <li>Uvicorn ASGI 서버</li>
                </ul>
              </div>
              <div style={s.archCard}>
                <div style={s.archTitle}>Frontend</div>
                <ul style={s.archList}>
                  <li>React 19 + TypeScript 5.9</li>
                  <li>Vite 7 (빌드 도구)</li>
                  <li>AG Grid Community (데이터 그리드)</li>
                  <li>Chart.js (차트)</li>
                  <li>Axios (HTTP 클라이언트)</li>
                  <li>React Router v7</li>
                </ul>
              </div>
              <div style={s.archCard}>
                <div style={s.archTitle}>인프라</div>
                <ul style={s.archList}>
                  <li>Backend: 포트 8008</li>
                  <li>Frontend: 포트 5173 (개발)</li>
                  <li>CORS 설정 필요</li>
                  <li>파일 저장: UPLOAD_DIR</li>
                  <li>라이선스: AGPL-3.0</li>
                </ul>
              </div>
            </div>
          </section>

          {/* 2. 설치 및 실행 */}
          <section id="install" style={s.section}>
            <h2 style={s.h2}>2. 설치 및 실행</h2>

            <h3 style={s.h3}>2-1. 개발 환경 실행</h3>
            <div style={s.codeBlock}>
              <div style={s.codeTitle}>run_dev.bat (Windows)</div>
              <pre style={s.code}>{`# Backend 시작
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8008

# Frontend 시작 (별도 터미널)
cd frontend
npm install
npm run dev`}</pre>
            </div>

            <h3 style={s.h3}>2-2. Mac/Linux 실행</h3>
            <div style={s.codeBlock}>
              <div style={s.codeTitle}>run_dev.sh</div>
              <pre style={s.code}>{`bash run_dev.sh

# 또는 수동 실행
cd backend && python -m uvicorn main:app --reload --port 8008 &
cd frontend && npm run dev &`}</pre>
            </div>

            <h3 style={s.h3}>2-3. 프로덕션 빌드</h3>
            <div style={s.codeBlock}>
              <pre style={s.code}>{`# Frontend 프로덕션 빌드
cd frontend
npm run build

# TypeScript 타입 체크
npx tsc --noEmit`}</pre>
            </div>
          </section>

          {/* 3. 환경 변수 */}
          <section id="env" style={s.section}>
            <h2 style={s.h2}>3. 환경 변수</h2>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>변수명</th>
                  <th style={s.th}>기본값</th>
                  <th style={s.th}>설명</th>
                  <th style={s.th}>필수</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style={s.tdCode}>SECRET_KEY</td><td style={s.td}>(자동 생성/dev)</td><td style={s.td}>JWT 서명 키. 프로덕션에서 반드시 설정해야 함</td><td style={s.tdWarn}>프로덕션 필수</td></tr>
                <tr><td style={s.tdCode}>ENV</td><td style={s.td}>development</td><td style={s.td}>환경 구분. production 시 SECRET_KEY 미설정 시 에러</td><td style={s.td}>선택</td></tr>
                <tr><td style={s.tdCode}>DATABASE_URL</td><td style={s.td}>sqlite:///./tc_manager.db</td><td style={s.td}>데이터베이스 연결 문자열</td><td style={s.td}>선택</td></tr>
                <tr><td style={s.tdCode}>TOKEN_EXPIRE_HOURS</td><td style={s.td}>2</td><td style={s.td}>JWT 토큰 만료 시간 (시간)</td><td style={s.td}>선택</td></tr>
                <tr><td style={s.tdCode}>CORS_ORIGINS</td><td style={s.td}>http://localhost:5173, http://localhost:3000</td><td style={s.td}>허용할 CORS 오리진 (콤마 구분)</td><td style={s.td}>선택</td></tr>
                <tr><td style={s.tdCode}>UPLOAD_DIR</td><td style={s.td}>./uploads</td><td style={s.td}>첨부파일 저장 디렉토리</td><td style={s.td}>선택</td></tr>
              </tbody>
            </table>
            <div style={s.warnBox}>
              <strong>주의:</strong> 프로덕션 환경에서는 반드시 <code>SECRET_KEY</code>를 고유한 값으로 설정하세요. 미설정 시 서버 시작이 실패합니다.
            </div>
          </section>

          {/* 4. 데이터베이스 */}
          <section id="database" style={s.section}>
            <h2 style={s.h2}>4. 데이터베이스</h2>
            <ul style={s.ul}>
              <li>기본: SQLite (<code>backend/tc_manager.db</code>)</li>
              <li>테이블은 서버 최초 시작 시 SQLAlchemy가 자동 생성합니다.</li>
              <li>PostgreSQL 전환 시 <code>DATABASE_URL</code> 환경변수를 변경하세요.</li>
            </ul>

            <h3 style={s.h3}>4-1. 주요 테이블</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>테이블</th><th style={s.th}>설명</th><th style={s.th}>주요 관계</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.tdCode}>users</td><td style={s.td}>사용자 계정</td><td style={s.td}>projects, test_runs 소유</td></tr>
                <tr><td style={s.tdCode}>projects</td><td style={s.td}>프로젝트</td><td style={s.td}>test_cases, test_runs 포함</td></tr>
                <tr><td style={s.tdCode}>test_cases</td><td style={s.td}>테스트 케이스</td><td style={s.td}>project 소속, 소프트 삭제 지원</td></tr>
                <tr><td style={s.tdCode}>test_runs</td><td style={s.td}>테스트 런</td><td style={s.td}>project 소속, test_results 포함</td></tr>
                <tr><td style={s.tdCode}>test_results</td><td style={s.td}>테스트 결과</td><td style={s.td}>test_run + test_case 참조, attachments 포함</td></tr>
                <tr><td style={s.tdCode}>attachments</td><td style={s.td}>첨부파일 메타데이터</td><td style={s.td}>test_result 참조</td></tr>
                <tr><td style={s.tdCode}>project_members</td><td style={s.td}>프로젝트 멤버</td><td style={s.td}>user + project 연결</td></tr>
                <tr><td style={s.tdCode}>test_case_history</td><td style={s.td}>TC 변경 이력</td><td style={s.td}>test_case 참조</td></tr>
                <tr><td style={s.tdCode}>test_case_sheets</td><td style={s.td}>시트 (트리 구조)</td><td style={s.td}>parent_id 자기 참조, project 소속</td></tr>
                <tr><td style={s.tdCode}>custom_field_defs</td><td style={s.td}>커스텀 필드 정의</td><td style={s.td}>project 소속, field_type/options</td></tr>
                <tr><td style={s.tdCode}>test_plans</td><td style={s.td}>테스트 플랜/마일스톤</td><td style={s.td}>project 소속, test_runs 연결 (1:N)</td></tr>
                <tr><td style={s.tdCode}>saved_filters</td><td style={s.td}>저장된 필터</td><td style={s.td}>project 소속, conditions JSON</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>4-2. 소프트 삭제 정책</h3>
            <div style={s.infoBox}>
              테스트 케이스는 삭제 시 <strong>소프트 삭제</strong>됩니다 (deleted_at 필드 설정). <strong>7일 후</strong> 자동 영구 삭제됩니다.
              삭제된 TC는 복원 API(<code>POST /api/projects/&#123;id&#125;/testcases/&#123;tc_id&#125;/restore</code>)로 복원 가능합니다.
            </div>
          </section>

          {/* 5. 사용자 관리 */}
          <section id="user-mgmt" style={s.section}>
            <h2 style={s.h2}>5. 사용자 관리</h2>
            <img src="/manual-images/22_admin_page.png" alt="관리자 페이지" style={s.img} />

            <h3 style={s.h3}>5-1. 사용자 목록</h3>
            <ul style={s.ul}>
              <li>헤더의 <strong>"관리"</strong> 버튼 클릭으로 관리자 페이지에 접근합니다.</li>
              <li>모든 사용자의 ID, 사용자명, 표시명, 역할, 가입일을 확인합니다.</li>
            </ul>

            <h3 style={s.h3}>5-2. 역할 변경</h3>
            <ol style={s.ol}>
              <li>대상 사용자의 역할 드롭다운을 변경합니다.</li>
              <li>변경 즉시 적용됩니다.</li>
              <li>해당 사용자의 다음 API 호출부터 새 권한이 적용됩니다.</li>
            </ol>
            <div style={s.warnBox}>
              <strong>주의:</strong> 자신의 Admin 역할을 해제하면 관리자 페이지에 접근할 수 없게 됩니다. 최소 1명의 Admin을 유지하세요.
            </div>

            <h3 style={s.h3}>5-3. 비밀번호 초기화</h3>
            <img src="/manual-images/25_admin_page_with_reset.png" alt="Admin 페이지 - 비밀번호 초기화" style={s.img} />
            <ol style={s.ol}>
              <li>대상 사용자 행에서 <strong>"비밀번호 초기화"</strong> 버튼을 클릭합니다.</li>
              <li>12자리 임시 비밀번호가 생성되어 표시됩니다.</li>
              <li>해당 임시 비밀번호를 사용자에게 전달합니다.</li>
              <li>사용자는 다음 로그인 시 <strong>비밀번호 강제 변경</strong> 화면이 표시됩니다.</li>
            </ol>
            <div style={s.warnBox}>
              <strong>주의:</strong> 임시 비밀번호는 화면에 1회만 표시됩니다. 반드시 메모하여 전달하세요.
            </div>

            <h3 style={s.h3}>5-4. 초기 계정</h3>
            <div style={s.infoBox}>
              시스템 최초 가입 사용자가 자동으로 <strong>Admin</strong> 역할을 부여받습니다. 이후 가입자는 모두 <strong>User</strong>로 시작합니다.
              관리자가 필요에 따라 역할을 변경해주어야 합니다.
            </div>
          </section>

          {/* 6. 역할/권한 체계 */}
          <section id="role-system" style={s.section}>
            <h2 style={s.h2}>6. 역할/권한 체계</h2>

            <h3 style={s.h3}>6-1. 시스템 역할</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>역할</th><th style={s.th}>수준</th><th style={s.th}>주요 권한</th></tr>
              </thead>
              <tbody>
                <tr><td style={{ ...s.td, color: "#CF222E", fontWeight: 700 }}>Admin</td><td style={s.td}>최상위</td><td style={s.td}>모든 기능 + 사용자 관리 + 비밀번호 초기화 + 역할 변경</td></tr>
                <tr><td style={{ ...s.td, color: "#BF8700", fontWeight: 700 }}>QA Manager</td><td style={s.td}>관리</td><td style={s.td}>사용자 목록 조회 + 모든 프로젝트 접근</td></tr>
                <tr><td style={{ ...s.td, color: "#6B7280", fontWeight: 700 }}>User</td><td style={s.td}>일반</td><td style={s.td}>소속 프로젝트 + 공개 프로젝트 접근</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>6-2. 프로젝트 역할</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>역할</th><th style={s.th}>설명</th></tr>
              </thead>
              <tbody>
                <tr><td style={{ ...s.td, fontWeight: 700 }}>Project Admin</td><td style={s.td}>프로젝트 관리, TC CRUD, 런 관리, 멤버 관리, 설정 변경</td></tr>
                <tr><td style={{ ...s.td, fontWeight: 700 }}>Project Tester</td><td style={s.td}>테스트 수행, 결과 기록, 첨부파일 업로드</td></tr>
              </tbody>
            </table>
            <ul style={s.ul}>
              <li>비공개 프로젝트는 멤버 또는 생성자만 접근 가능합니다.</li>
              <li>공개 프로젝트는 인증된 사용자 모두 조회 가능하지만, 수정은 프로젝트 역할에 따릅니다.</li>
              <li>System Admin / QA Manager는 모든 프로젝트에 접근 가능합니다.</li>
            </ul>

            <h3 style={s.h3}>6-3. 비밀번호 정책</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>항목</th><th style={s.th}>설정</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>최소 길이</td><td style={s.td}>8자</td></tr>
                <tr><td style={s.td}>동일 비밀번호 재사용</td><td style={s.td}>불가 (변경 시 현재 비밀번호와 동일하면 거부)</td></tr>
                <tr><td style={s.td}>강제 변경</td><td style={s.td}>관리자 초기화 후 다음 로그인 시 강제</td></tr>
                <tr><td style={s.td}>임시 비밀번호</td><td style={s.td}>12자리 영문+숫자 랜덤 생성</td></tr>
              </tbody>
            </table>
          </section>

          {/* 7. 프로젝트 운영 */}
          <section id="project-mgmt" style={s.section}>
            <h2 style={s.h2}>7. 프로젝트 운영</h2>

            <h3 style={s.h3}>7-1. 프로젝트 삭제 시 영향 범위</h3>
            <div style={s.warnBox}>
              프로젝트 삭제 시 다음 데이터가 <strong>모두 영구 삭제</strong>됩니다:
              <ul style={{ margin: "8px 0 0 20px" }}>
                <li>프로젝트 정보</li>
                <li>모든 테스트 케이스 (이력 포함)</li>
                <li>모든 테스트 런 및 결과</li>
                <li>모든 첨부파일 (DB 레코드 + 물리 파일)</li>
                <li>프로젝트 멤버 연결</li>
              </ul>
            </div>

            <h3 style={s.h3}>7-2. Jira 연동</h3>
            <ul style={s.ul}>
              <li>프로젝트 설정에서 <strong>Jira Base URL</strong>을 설정합니다.</li>
              <li>예: <code>https://your-domain.atlassian.net/browse/</code></li>
              <li>TC 또는 테스트 결과의 Issue Link 필드에 이슈 키(예: PROJ-123)를 입력하면 자동으로 링크가 생성됩니다.</li>
            </ul>
          </section>

          {/* 8. 파일/첨부 관리 */}
          <section id="file-mgmt" style={s.section}>
            <h2 style={s.h2}>8. 파일/첨부 관리</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>항목</th><th style={s.th}>설정</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>저장 경로</td><td style={s.td}><code>UPLOAD_DIR</code> 환경변수 (기본: <code>./uploads</code>)</td></tr>
                <tr><td style={s.td}>파일 크기 제한</td><td style={s.td}>50MB</td></tr>
                <tr><td style={s.td}>허용 확장자 (이미지)</td><td style={s.td}>.png, .jpg, .jpeg, .gif, .bmp, .webp</td></tr>
                <tr><td style={s.td}>허용 확장자 (문서)</td><td style={s.td}>.pdf, .doc, .docx, .xlsx, .xls, .pptx</td></tr>
                <tr><td style={s.td}>허용 확장자 (기타)</td><td style={s.td}>.zip, .txt, .csv, .log</td></tr>
                <tr><td style={s.td}>파일명 처리</td><td style={s.td}>UUID 기반 이름 변환 (경로 탐색 공격 방지)</td></tr>
                <tr><td style={s.td}>다운로드 보안</td><td style={s.td}>안전하지 않은 MIME 타입은 octet-stream으로 강제 다운로드</td></tr>
              </tbody>
            </table>
            <div style={s.tipBox}>
              <strong>디스크 관리:</strong> 테스트 런 삭제 시 관련 첨부파일의 물리 파일도 자동 삭제됩니다 (UPLOAD_DIR 기준). 주기적으로 디스크 사용량을 확인하세요.
            </div>
          </section>

          {/* 9. 보안 설정 */}
          <section id="security" style={s.section}>
            <h2 style={s.h2}>9. 보안 설정</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>보안 항목</th><th style={s.th}>구현</th><th style={s.th}>설정</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>비밀번호 정책</td><td style={s.td}>최소 8자, 동일 비밀번호 재사용 불가</td><td style={s.td}>자동 적용</td></tr>
                <tr><td style={s.td}>비밀번호 저장</td><td style={s.td}>bcrypt 해싱</td><td style={s.td}>자동 적용</td></tr>
                <tr><td style={s.td}>비밀번호 초기화</td><td style={s.td}>Admin이 임시 비밀번호 발급, 강제 변경</td><td style={s.td}>Admin 페이지</td></tr>
                <tr><td style={s.td}>인증 토큰</td><td style={s.td}>JWT (HS256) + httpOnly 쿠키</td><td style={s.td}>TOKEN_EXPIRE_HOURS (기본 2시간)</td></tr>
                <tr><td style={s.td}>CSRF 방어</td><td style={s.td}>csrf_token 쿠키 + X-CSRF-Token 헤더 검증</td><td style={s.td}>상태 변경 요청 시 자동 적용</td></tr>
                <tr><td style={s.td}>로그인 제한</td><td style={s.td}>Rate Limiting</td><td style={s.td}>IP+사용자당 5분간 10회 (초과 시 잠금)</td></tr>
                <tr><td style={s.td}>CORS</td><td style={s.td}>오리진 화이트리스트</td><td style={s.td}>CORS_ORIGINS (와일드카드 금지)</td></tr>
                <tr><td style={s.td}>파일 업로드</td><td style={s.td}>확장자 화이트리스트 + 경로 탐색 방지</td><td style={s.td}>허용 확장자 고정</td></tr>
                <tr><td style={s.td}>XSS 방지</td><td style={s.td}>DOMPurify (프론트엔드)</td><td style={s.td}>마크다운 셀 렌더링 시 자동 적용</td></tr>
                <tr><td style={s.td}>API 권한</td><td style={s.td}>역할 기반 접근 제어</td><td style={s.td}>엔드포인트별 역할 체크</td></tr>
              </tbody>
            </table>
          </section>

          {/* 10. API 엔드포인트 */}
          <section id="api-ref" style={s.section}>
            <h2 style={s.h2}>10. API 엔드포인트 (70개)</h2>
            <div style={s.infoBox}>
              API 문서(Swagger UI)는 <a href="http://localhost:8008/docs" target="_blank" rel="noreferrer" style={{ color: "#2563EB" }}>http://localhost:8008/docs</a> 에서 확인할 수 있습니다.
            </div>

            {[
              { title: "인증 (Auth)", endpoints: [
                ["GET", "/api/auth/check-username", "사용자명 중복 확인"],
                ["POST", "/api/auth/register", "회원가입 (비밀번호 최소 8자)"],
                ["POST", "/api/auth/login", "로그인 (JWT 토큰 발급)"],
                ["GET", "/api/auth/me", "현재 사용자 정보"],
                ["PUT", "/api/auth/change-password", "비밀번호 변경 (최소 8자)"],
                ["GET", "/api/auth/users", "사용자 목록 (QA Manager 이상)"],
                ["PUT", "/api/auth/users/{user_id}/role", "역할 변경 (Admin)"],
                ["PUT", "/api/auth/users/{user_id}/reset-password", "비밀번호 초기화 (Admin)"],
              ]},
              { title: "프로젝트", endpoints: [
                ["GET", "/api/projects", "프로젝트 목록"],
                ["POST", "/api/projects", "프로젝트 생성 (Admin)"],
                ["GET", "/api/projects/{id}", "프로젝트 상세"],
                ["PUT", "/api/projects/{id}", "프로젝트 수정"],
                ["DELETE", "/api/projects/{id}", "프로젝트 삭제 (Admin)"],
              ]},
              { title: "테스트 케이스", endpoints: [
                ["GET", "/api/projects/{id}/testcases", "TC 목록"],
                ["POST", "/api/projects/{id}/testcases", "TC 생성"],
                ["PUT", "/api/projects/{id}/testcases/{tc_id}", "TC 수정"],
                ["PUT", "/api/projects/{id}/testcases/bulk", "TC 일괄 수정"],
                ["DELETE", "/api/projects/{id}/testcases/{tc_id}", "TC 삭제 (소프트)"],
                ["POST", "/api/projects/{id}/testcases/{tc_id}/restore", "TC 복원"],
                ["DELETE", "/api/projects/{id}/testcases/bulk?ids=1,2,3", "TC 벌크 삭제"],
                ["GET", "/api/projects/{id}/testcases/sheets", "시트 목록"],
                ["POST", "/api/projects/{id}/testcases/sheets", "시트 생성"],
                ["DELETE", "/api/projects/{id}/testcases/sheets/{name}", "시트 삭제 (하위 CASCADE)"],
                ["PUT", "/api/projects/{id}/testcases/sheets/{sheet_id}/rename", "시트 이름 변경"],
                ["PUT", "/api/projects/{id}/testcases/sheets/{sheet_id}/move", "시트 이동 (부모 변경)"],
                ["POST", "/api/projects/{id}/testcases/import/preview", "Import 미리보기"],
                ["POST", "/api/projects/{id}/testcases/import", "Excel/CSV/Markdown Import (Jira/Xray/Zephyr 호환)"],
                ["GET", "/api/projects/{id}/testcases/export", "Excel Export"],
              ]},
              { title: "테스트 런", endpoints: [
                ["GET", "/api/projects/{id}/testruns", "런 목록"],
                ["POST", "/api/projects/{id}/testruns", "런 생성"],
                ["GET", "/api/projects/{id}/testruns/{run_id}", "런 상세 (결과 포함)"],
                ["PUT", "/api/projects/{id}/testruns/{run_id}", "런 수정"],
                ["POST", "/api/projects/{id}/testruns/{run_id}/results", "결과 저장 (벌크)"],
                ["PUT", "/api/projects/{id}/testruns/{run_id}/complete", "런 완료"],
                ["PUT", "/api/projects/{id}/testruns/{run_id}/reopen", "런 다시 수행 (완료→진행중)"],
                ["POST", "/api/projects/{id}/testruns/{run_id}/clone", "런 복제"],
                ["DELETE", "/api/projects/{id}/testruns/{run_id}", "런 삭제"],
                ["GET", "/api/projects/{id}/testruns/{run_id}/export", "런 Excel Export"],
              ]},
              { title: "대시보드", endpoints: [
                ["GET", "/api/projects/{id}/dashboard/summary", "요약 통계"],
                ["GET", "/api/projects/{id}/dashboard/priority", "우선순위별 분포"],
                ["GET", "/api/projects/{id}/dashboard/category", "카테고리별 분포"],
                ["GET", "/api/projects/{id}/dashboard/rounds", "라운드별 비교"],
                ["GET", "/api/projects/{id}/dashboard/assignee", "담당자별 현황"],
                ["GET", "/api/projects/{id}/dashboard/heatmap", "실패 히트맵"],
              ]},
              { title: "커스텀 필드", endpoints: [
                ["GET", "/api/projects/{id}/custom-fields", "필드 정의 목록"],
                ["POST", "/api/projects/{id}/custom-fields", "필드 생성 (text/number/select/checkbox/date)"],
                ["PUT", "/api/projects/{id}/custom-fields/{field_id}", "필드 수정"],
                ["DELETE", "/api/projects/{id}/custom-fields/{field_id}", "필드 삭제"],
              ]},
              { title: "테스트 플랜", endpoints: [
                ["GET", "/api/projects/{id}/testplans", "플랜 목록 (progress 포함)"],
                ["POST", "/api/projects/{id}/testplans", "플랜 생성"],
                ["GET", "/api/projects/{id}/testplans/{plan_id}", "플랜 상세 (run_count, progress)"],
                ["PUT", "/api/projects/{id}/testplans/{plan_id}", "플랜 수정"],
                ["DELETE", "/api/projects/{id}/testplans/{plan_id}", "플랜 삭제 (Run 연결 해제)"],
                ["GET", "/api/projects/{id}/testplans/{plan_id}/runs", "플랜 연결 Run 목록"],
              ]},
              { title: "고급 필터", endpoints: [
                ["GET", "/api/projects/{id}/filters", "저장된 필터 목록"],
                ["POST", "/api/projects/{id}/filters", "필터 저장"],
                ["PUT", "/api/projects/{id}/filters/{filter_id}", "필터 수정"],
                ["DELETE", "/api/projects/{id}/filters/{filter_id}", "필터 삭제"],
                ["POST", "/api/projects/{id}/filters/apply", "필터 즉시 적용 (AND/OR)"],
              ]},
              { title: "리포트 / 첨부파일 / 기타", endpoints: [
                ["GET", "/api/projects/{id}/reports", "리포트 JSON"],
                ["GET", "/api/projects/{id}/reports/pdf", "PDF 다운로드"],
                ["GET", "/api/projects/{id}/reports/excel", "Excel 다운로드"],
                ["GET", "/api/attachments/{result_id}", "첨부파일 목록"],
                ["POST", "/api/attachments/{result_id}", "첨부파일 업로드"],
                ["GET", "/api/attachments/download/{id}", "첨부파일 다운로드"],
                ["DELETE", "/api/attachments/{id}", "첨부파일 삭제"],
                ["GET", "/api/search?q=...", "글로벌 TC 검색"],
                ["GET", "/api/dashboard/overview", "전체 현황"],
              ]},
            ].map((group, gi) => (
              <div key={gi} style={{ marginBottom: 20 }}>
                <h3 style={s.h3}>{group.title}</h3>
                <table style={s.table}>
                  <thead>
                    <tr><th style={{ ...s.th, width: 70 }}>Method</th><th style={s.th}>Endpoint</th><th style={s.th}>설명</th></tr>
                  </thead>
                  <tbody>
                    {group.endpoints.map(([method, path, desc], i) => (
                      <tr key={i}>
                        <td style={{ ...s.td, fontWeight: 700, color: method === "GET" ? "#2563EB" : method === "POST" ? "#16A34A" : method === "PUT" ? "#D97706" : "#DC2626" }}>{method}</td>
                        <td style={s.tdCode}>{path}</td>
                        <td style={s.td}>{desc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>

          {/* 11. 트러블슈팅 */}
          <section id="troubleshoot" style={s.section}>
            <h2 style={s.h2}>11. 트러블슈팅</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>증상</th><th style={s.th}>원인</th><th style={s.th}>해결</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>서버 시작 실패 (RuntimeError)</td><td style={s.td}>프로덕션에서 SECRET_KEY 미설정</td><td style={s.td}>환경변수 SECRET_KEY 설정</td></tr>
                <tr><td style={s.td}>로그인 시 401 에러</td><td style={s.td}>잘못된 자격증명 또는 토큰 만료</td><td style={s.td}>자격증명 확인 또는 재로그인</td></tr>
                <tr><td style={s.td}>로그인 잠금 (429)</td><td style={s.td}>5분간 10회 실패</td><td style={s.td}>5분 대기 후 재시도</td></tr>
                <tr><td style={s.td}>CORS 에러</td><td style={s.td}>프론트엔드 오리진이 허용 목록에 없음</td><td style={s.td}>CORS_ORIGINS 환경변수에 오리진 추가</td></tr>
                <tr><td style={s.td}>파일 업로드 실패</td><td style={s.td}>파일 크기 초과 또는 비허용 확장자</td><td style={s.td}>50MB 이하, 허용 확장자 확인</td></tr>
                <tr><td style={s.td}>한글 깨짐 (mojibake)</td><td style={s.td}>프론트엔드 소스 파일 인코딩 문제</td><td style={s.td}>UTF-8로 파일 재저장, 빌드 후 확인</td></tr>
                <tr><td style={s.td}>Excel/CSV Import 실패</td><td style={s.td}>헤더 매핑 실패 또는 파일 형식 오류</td><td style={s.td}>지원 형식(.xlsx, .xls, .csv) 확인, 헤더 행 확인. CSV는 UTF-8/CP949 자동 감지</td></tr>
                <tr><td style={s.td}>커스텀 필드 컬럼 안 보임</td><td style={s.td}>커스텀 필드 정의가 없음</td><td style={s.td}>API로 custom-fields 생성 후 새로고침</td></tr>
                <tr><td style={s.td}>시트 삭제 시 하위 시트 남음</td><td style={s.td}>SQLite FK 미활성화 (구버전)</td><td style={s.td}>서버 재시작 (database.py에서 PRAGMA foreign_keys=ON 확인)</td></tr>
                <tr><td style={s.td}>테스트 플랜 progress 0</td><td style={s.td}>TestRun에 test_plan_id 미연결</td><td style={s.td}>Run 생성 시 test_plan_id 지정 확인</td></tr>
                <tr><td style={s.td}>PDF 리포트 한글 깨짐</td><td style={s.td}>한글 폰트 미설치</td><td style={s.td}>Malgun Gothic 폰트 설치 확인</td></tr>
              </tbody>
            </table>
          </section>

          {/* 12. 백업/복구 */}
          <section id="backup" style={s.section}>
            <h2 style={s.h2}>12. 백업/복구</h2>

            <h3 style={s.h3}>12-1. 데이터 백업</h3>
            <div style={s.codeBlock}>
              <div style={s.codeTitle}>SQLite 백업</div>
              <pre style={s.code}>{`# 데이터베이스 파일 복사
cp backend/tc_manager.db backup/tc_manager_$(date +%Y%m%d).db

# 첨부파일 백업
cp -r backend/uploads backup/uploads_$(date +%Y%m%d)`}</pre>
            </div>

            <h3 style={s.h3}>12-2. 복구</h3>
            <div style={s.codeBlock}>
              <pre style={s.code}>{`# 데이터베이스 복구
cp backup/tc_manager_20260316.db backend/tc_manager.db

# 첨부파일 복구
cp -r backup/uploads_20260316/* backend/uploads/

# 서버 재시작
docker-compose restart backend`}</pre>
            </div>

            <div style={s.tipBox}>
              <strong>권장사항:</strong> 정기적인 백업 스케줄을 설정하세요. SQLite 파일과 uploads 디렉토리를 함께 백업해야 합니다. 크론잡이나 CI/CD 파이프라인에 자동 백업을 추가하는 것을 추천합니다.
            </div>
          </section>

          <div style={s.footer}>
            <p>YM TestCase v1.0 | 운영 매뉴얼 (Admin 전용)</p>
          </div>
        </main>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", backgroundColor: "var(--bg-page, #F5F7FA)", color: "var(--text-primary, #0F1923)" },
  topBar: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 24px", backgroundColor: "#7C2D12", color: "#fff", position: "sticky", top: 0, zIndex: 100 },
  topLeft: { display: "flex", alignItems: "center", gap: 16 },
  topRight: { display: "flex", alignItems: "center", gap: 12 },
  logo: { fontSize: 18, fontWeight: 700, cursor: "pointer" },
  badge: { fontSize: 12, padding: "3px 10px", borderRadius: 12, backgroundColor: "rgba(255,255,255,0.2)" },
  userName: { fontSize: 13, opacity: 0.8 },
  backBtn: { padding: "6px 16px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.3)", backgroundColor: "transparent", color: "#fff", cursor: "pointer", fontSize: 13 },
  container: { display: "flex", maxWidth: 1400, margin: "0 auto" },
  toc: { width: 220, minWidth: 220, padding: "24px 16px", position: "sticky", top: 52, height: "calc(100vh - 52px)", overflowY: "auto", borderRight: "1px solid var(--border-color, #E2E8F0)", backgroundColor: "var(--bg-card, #fff)" },
  tocTitle: { fontSize: 14, fontWeight: 700, marginBottom: 16 },
  tocItem: { display: "block", fontSize: 13, padding: "6px 8px", borderRadius: 4, color: "var(--text-secondary, #64748B)", textDecoration: "none", marginBottom: 2, lineHeight: 1.5 },
  main: { flex: 1, padding: "32px 48px", maxWidth: 960 },
  section: { marginBottom: 56, scrollMarginTop: 70 },
  h1: { fontSize: 28, fontWeight: 800, marginBottom: 8 },
  h2: { fontSize: 22, fontWeight: 700, marginBottom: 16, paddingBottom: 8, borderBottom: "2px solid var(--border-color, #E2E8F0)" },
  h3: { fontSize: 16, fontWeight: 600, marginTop: 24, marginBottom: 12 },
  p: { fontSize: 14, lineHeight: 1.8, color: "var(--text-secondary, #475569)", marginBottom: 12 },
  updatedAt: { fontSize: 13, color: "var(--text-secondary, #94A3B8)", marginBottom: 20 },
  img: { width: "100%", borderRadius: 8, border: "1px solid var(--border-color, #E2E8F0)", marginBottom: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
  ol: { fontSize: 14, lineHeight: 2, paddingLeft: 20, marginBottom: 16 },
  ul: { fontSize: 14, lineHeight: 2, paddingLeft: 20, marginBottom: 16 },
  infoBox: { fontSize: 14, lineHeight: 1.8, padding: "16px 20px", borderRadius: 8, backgroundColor: "#EFF6FF", border: "1px solid #BFDBFE", marginBottom: 16 },
  tipBox: { fontSize: 13, lineHeight: 1.7, padding: "12px 16px", borderRadius: 8, backgroundColor: "#F0FDF4", border: "1px solid #86EFAC", marginBottom: 16, color: "#166534" },
  warnBox: { fontSize: 13, lineHeight: 1.7, padding: "12px 16px", borderRadius: 8, backgroundColor: "#FEF2F2", border: "1px solid #FCA5A5", marginBottom: 16, color: "#991B1B" },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13, marginBottom: 20 },
  th: { padding: "10px 12px", backgroundColor: "#7C2D12", color: "#fff", textAlign: "left" as const, fontWeight: 600 },
  td: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", verticalAlign: "top" as const },
  tdCode: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", fontFamily: "monospace", fontSize: 12, backgroundColor: "var(--bg-input, #F8FAFC)" },
  tdWarn: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", color: "#DC2626", fontWeight: 600 },
  codeBlock: { borderRadius: 8, overflow: "hidden", marginBottom: 16, border: "1px solid var(--border-color, #E2E8F0)" },
  codeTitle: { padding: "8px 16px", backgroundColor: "#334155", color: "#94A3B8", fontSize: 12, fontWeight: 600 },
  code: { margin: 0, padding: "16px", backgroundColor: "#1E293B", color: "#E2E8F0", fontSize: 13, lineHeight: 1.6, overflowX: "auto" as const, whiteSpace: "pre" as const },
  archGrid: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 20 },
  archCard: { padding: 16, borderRadius: 8, border: "1px solid var(--border-color, #E2E8F0)", backgroundColor: "var(--bg-card, #fff)" },
  archTitle: { fontSize: 15, fontWeight: 700, marginBottom: 12, color: "#7C2D12" },
  archList: { fontSize: 13, lineHeight: 1.8, paddingLeft: 18, margin: 0 },
  footer: { textAlign: "center" as const, padding: "32px 0", color: "var(--text-secondary, #94A3B8)", fontSize: 13, borderTop: "1px solid var(--border-color, #E2E8F0)", marginTop: 40 },
};
