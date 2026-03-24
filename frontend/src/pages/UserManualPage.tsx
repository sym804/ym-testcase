import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export default function UserManualPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  return (
    <div style={s.page}>
      {/* 상단 바 */}
      <div style={s.topBar}>
        <div style={s.topLeft}>
          <span style={s.logo} onClick={() => navigate("/projects")}>
            YM TestCase
          </span>
          <span style={s.badge}>사용자 매뉴얼</span>
        </div>
        <div style={s.topRight}>
          {user && <span style={s.userName}>{user.display_name}</span>}
          <button style={s.backBtn} onClick={() => navigate(-1)}>
            돌아가기
          </button>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <div style={s.container}>
        {/* 사이드 목차 */}
        <nav style={s.toc}>
          <div style={s.tocTitle}>목차</div>
          <a href="#overview" style={s.tocItem}>개요</a>
          <a href="#login" style={s.tocItem}>1. 로그인 / 회원가입</a>
          <a href="#project-list" style={s.tocItem}>2. 프로젝트 목록</a>
          <a href="#project-detail" style={s.tocItem}>3. 프로젝트 상세</a>
          <a href="#tc-manage" style={s.tocItem}>4. TC 관리</a>
          <a href="#sheet-tree" style={s.tocItem}>5. 폴더 / 시트 트리</a>
          <a href="#custom-fields" style={s.tocItem}>6. 커스텀 필드</a>
          <a href="#import" style={s.tocItem}>7. Import (Excel / CSV / Markdown)</a>
          <a href="#advanced-filter" style={s.tocItem}>8. 고급 필터</a>
          <a href="#testrun" style={s.tocItem}>9. 테스트 수행</a>
          <a href="#test-plans" style={s.tocItem}>10. 테스트 플랜</a>
          <a href="#compare" style={s.tocItem}>11. 비교</a>
          <a href="#dashboard" style={s.tocItem}>12. 대시보드</a>
          <a href="#report" style={s.tocItem}>13. 리포트</a>
          <a href="#settings" style={s.tocItem}>14. 설정</a>
          <a href="#roles" style={s.tocItem}>15. 역할별 권한</a>
          <a href="#header" style={s.tocItem}>16. 헤더 / 네비게이션</a>
          <a href="#theme" style={s.tocItem}>17. 테마 (다크모드)</a>
          <a href="#shortcuts" style={s.tocItem}>18. 단축키 모음</a>
        </nav>

        {/* 본문 */}
        <main style={s.main}>
          {/* 1. 개요 */}
          <section id="overview" style={s.section}>
            <h1 style={s.h1}>YM TestCase 사용자 매뉴얼</h1>
            <p style={s.updatedAt}>최종 업데이트: 2026-03-24</p>
            <div style={s.infoBox}>
              <strong>YM TestCase</strong>는 테스트 케이스(TC)의 관리, 테스트 수행, 결과 분석 및 리포트 생성을 위한 웹 기반 테스트 관리 시스템입니다.
              <br /><br />
              주요 기능:
              <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
                <li>프로젝트 단위 테스트 케이스 관리 (CRUD, Excel Import/Export)</li>
                <li>테스트 수행 및 결과 기록 (키보드 단축키, 첨부파일 지원)</li>
                <li>테스트 런 간 비교 (변경/리그레션 감지)</li>
                <li>대시보드 (도넛 차트, 바 차트, 히트맵 등 분석)</li>
                <li>리포트 생성 (PDF / Excel 다운로드)</li>
                <li>역할 기반 접근 제어 (Admin, QA Manager, User)</li>
                <li>시트 트리 구조 (N depth 폴더 분류)</li>
                <li>커스텀 필드 (프로젝트별 동적 컬럼 추가)</li>
                <li>테스트 플랜 / 마일스톤 (릴리즈 단위 관리)</li>
                <li>Jira CSV Import (Jira/Xray/Zephyr 호환)</li>
                <li>고급 필터 + 저장된 뷰 (AND/OR 다중 조건)</li>
              </ul>
            </div>
          </section>

          {/* 1. 로그인/회원가입 */}
          {/* 1. 로그인/회원가입 */}
          <section id="login" style={s.section}>
            <h2 style={s.h2}>1. 로그인 / 회원가입</h2>

            <h3 style={s.h3}>1-1. 로그인</h3>
            <img src="/manual-images/01_login_page.png" alt="로그인 페이지" style={s.img} />
            <ol style={s.ol}>
              <li>아이디(사용자명)를 입력합니다.</li>
              <li>비밀번호를 입력합니다.</li>
              <li><strong>로그인</strong> 버튼을 클릭합니다.</li>
              <li>성공 시 프로젝트 목록 페이지로 이동합니다.</li>
            </ol>
            <div style={s.tipBox}>
              <strong>TIP:</strong> 로그인 실패 시 5분간 최대 10회까지 시도할 수 있습니다. 초과 시 일시적으로 잠깁니다.
            </div>

            <h3 style={s.h3}>1-2. 회원가입</h3>
            <img src="/manual-images/02_register_page.png" alt="회원가입 페이지" style={s.img} />
            <ol style={s.ol}>
              <li>로그인 화면 하단의 <strong>"회원가입"</strong> 링크를 클릭합니다.</li>
              <li>아이디, 표시명, 비밀번호를 입력합니다.</li>
              <li><strong>회원가입</strong> 버튼을 클릭합니다.</li>
            </ol>
            <div style={s.warnBox}>
              <strong>비밀번호 규칙:</strong> 비밀번호는 <strong>최소 8자</strong> 이상이어야 합니다.
            </div>
            <div style={s.infoBox}>
              <strong>참고:</strong> 최초 가입 사용자는 자동으로 <strong>Admin</strong> 역할이 부여됩니다. 이후 가입자는 <strong>User</strong> 역할로 시작합니다.
            </div>

            <h3 style={s.h3}>1-3. 비밀번호 변경</h3>
            <img src="/manual-images/24_password_change_modal.png" alt="비밀번호 변경 모달" style={s.img} />
            <ol style={s.ol}>
              <li>로그인 후 사용자 정보 영역에서 <strong>비밀번호 변경</strong>을 선택합니다.</li>
              <li>현재 비밀번호를 입력합니다.</li>
              <li>새 비밀번호를 입력합니다 (최소 8자).</li>
              <li><strong>변경</strong> 버튼을 클릭합니다.</li>
            </ol>
            <div style={s.infoBox}>
              <strong>강제 변경:</strong> 관리자가 비밀번호를 초기화한 경우, 다음 로그인 시 비밀번호 변경이 강제됩니다. 변경 완료 전까지 다른 기능을 사용할 수 없습니다.
              <br /><br />
              <img src="/manual-images/26_force_password_change.png" alt="비밀번호 강제 변경 화면" style={{ width: "100%", borderRadius: 8, border: "1px solid #E2E8F0" }} />
            </div>
          </section>

          {/* 1. 프로젝트 목록 */}
          {/* 1. 프로젝트 목록 */}
          <section id="project-list" style={s.section}>
            <h2 style={s.h2}>2. 프로젝트 목록</h2>
            <p style={s.p}>로그인 후 첫 화면입니다. 전체 프로젝트 현황을 한눈에 파악할 수 있습니다.</p>

            <h3 style={s.h3}>2-1. 전체 현황 (Overview)</h3>
            <img src="/manual-images/04_project_list_overview.png" alt="프로젝트 목록 - 전체 현황" style={s.img} />
            <div style={s.featureGrid}>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📊</div>
                <div>
                  <strong>요약 카드</strong>
                  <p style={s.featureDesc}>전체 프로젝트 수, 전체 TC 수, 진행률, Pass Rate를 카드로 표시합니다.</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📈</div>
                <div>
                  <strong>프로그레스 바</strong>
                  <p style={s.featureDesc}>PASS/FAIL/BLOCK/N/A/미수행 비율을 색상 바로 시각화합니다.</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📋</div>
                <div>
                  <strong>프로젝트 테이블</strong>
                  <p style={s.featureDesc}>프로젝트별 TC 수, PASS/FAIL 수, 진행률, Pass Rate를 테이블로 표시합니다.</p>
                </div>
              </div>
            </div>

            <h3 style={s.h3}>2-2. 프로젝트 카드</h3>
            <img src="/manual-images/05_project_list_cards.png" alt="프로젝트 카드" style={s.img} />
            <ul style={s.ul}>
              <li>각 카드는 프로젝트명, 설명, TC 수, Pass/Fail 수, 진행률, 최근 활동일을 표시합니다.</li>
              <li>카드를 클릭하면 해당 프로젝트 상세 페이지로 이동합니다.</li>
            </ul>

            <h3 style={s.h3}>2-3. 프로젝트 생성</h3>
            <img src="/manual-images/06_project_create_modal.png" alt="프로젝트 생성 모달" style={s.img} />
            <ol style={s.ol}>
              <li>우측 상단의 <strong>"+ 새 프로젝트"</strong> 버튼을 클릭합니다.</li>
              <li>프로젝트명과 설명을 입력합니다.</li>
              <li><strong>만들기</strong> 버튼을 클릭합니다.</li>
            </ol>
            <div style={s.warnBox}>
              <strong>권한:</strong> Admin 역할만 프로젝트를 생성할 수 있습니다.
            </div>

            <h3 style={s.h3}>2-4. 프로젝트 일괄 삭제</h3>
            <ul style={s.ul}>
              <li>전체 현황 테이블의 왼쪽 체크박스로 프로젝트를 선택합니다.</li>
              <li>헤더의 체크박스를 클릭하면 전체 선택/해제가 가능합니다.</li>
              <li>선택 후 <strong>"N개 삭제"</strong> 버튼을 클릭하면 확인 후 일괄 삭제됩니다.</li>
            </ul>
          </section>

          {/* 16. 헤더 */}
          {/* 2. 프로젝트 상세 */}
          <section id="project-detail" style={s.section}>
            <h2 style={s.h2}>3. 프로젝트 상세</h2>
            <p style={s.p}>프로젝트 카드 클릭 또는 헤더 셀렉터로 진입합니다. 탭으로 기능을 전환합니다.</p>
            <img src="/manual-images/07_project_detail_tc_tab.png" alt="프로젝트 상세" style={s.img} />
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>탭</th><th style={s.th}>기능</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}><strong>TC 관리</strong></td><td style={s.td}>테스트 케이스 CRUD, Excel Import/Export, 변경이력</td></tr>
                <tr><td style={s.td}><strong>테스트 수행</strong></td><td style={s.td}>테스트 런 생성, 결과 기록, 첨부파일, 단축키</td></tr>
                <tr><td style={s.td}><strong>비교</strong></td><td style={s.td}>두 테스트 런 간 결과 비교, 리그레션 감지</td></tr>
                <tr><td style={s.td}><strong>대시보드</strong></td><td style={s.td}>요약 카드, 차트, 히트맵 분석</td></tr>
                <tr><td style={s.td}><strong>리포트</strong></td><td style={s.td}>결과 요약 보기, PDF/Excel 다운로드</td></tr>
                <tr><td style={s.td}><strong>설정</strong></td><td style={s.td}>프로젝트 정보 수정, Jira 연동, 멤버 관리</td></tr>
              </tbody>
            </table>
          </section>

          {/* 16. TC 관리 */}
          {/* 16. TC 관리 */}
          <section id="tc-manage" style={s.section}>
            <h2 style={s.h2}>4. TC 관리</h2>
            <img src="/manual-images/23_tc_toolbar.png" alt="TC 관리 툴바" style={s.img} />

            <h3 style={s.h3}>4-1. 툴바 기능</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>버튼</th><th style={s.th}>기능</th><th style={s.th}>설명</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>+ 행 추가</td><td style={s.td}>TC 생성</td><td style={s.td}>새 TC를 즉시 생성하여 그리드에 추가 (자동 저장)</td></tr>
                <tr><td style={s.td}>다중 추가 (▼)</td><td style={s.td}>다중 행 추가</td><td style={s.td}>드롭다운에서 1/3/5/10/20/30행을 선택하여 한 번에 여러 TC를 추가</td></tr>
                <tr><td style={s.td}>선택 복사</td><td style={s.td}>행 복사</td><td style={s.td}>선택한 TC 행을 복사하여 새 행으로 추가</td></tr>
                <tr><td style={s.td}>선택 삭제</td><td style={s.td}>TC 삭제</td><td style={s.td}>선택한 TC를 소프트 삭제. 삭제된 TC는 7일간 복원 가능하며, 7일 후 자동 영구삭제됨</td></tr>
                <tr><td style={s.td}>Undo / Redo</td><td style={s.td}>실행 취소/재실행</td><td style={s.td}>그리드 편집 작업을 취소(Ctrl+Z)하거나 재실행(Ctrl+Shift+Z). 최대 200단계까지 지원. 페이지 이동 시 히스토리는 초기화됨</td></tr>
                <tr><td style={s.td}>TC ID 자동채우기</td><td style={s.td}>ID 자동 생성</td><td style={s.td}>비어있는 TC ID를 <code>TC-001, TC-002...</code> 형식으로 자동 채움. 기존 ID의 최대 번호 다음부터 순차 부여</td></tr>
                <tr><td style={s.td}>일괄 변경</td><td style={s.td}>벌크 수정</td><td style={s.td}>선택한 TC의 특정 필드를 일괄 변경</td></tr>
                <tr><td style={s.td}>Excel Import</td><td style={s.td}>엑셀 가져오기</td><td style={s.td}>엑셀 파일에서 TC 가져오기. 여러 시트가 있으면 선택 가능. 동일 TC ID는 덮어쓰기</td></tr>
                <tr><td style={s.td}>Excel Export</td><td style={s.td}>엑셀 내보내기</td><td style={s.td}>현재 TC 목록을 서식이 적용된 엑셀 파일로 다운로드</td></tr>
                <tr><td style={s.td}>변경이력</td><td style={s.td}>수정 내역 확인</td><td style={s.td}>변경이력 패널이 열리며, 각 TC의 필드별 변경 전/후 값, 변경자, 변경 시각을 시간순으로 확인. 프로젝트 전체 이력 또는 특정 TC 이력 조회 가능</td></tr>
                <tr><td style={s.td}>바꾸기</td><td style={s.td}>찾기/바꾸기</td><td style={s.td}>찾을 텍스트와 바꿀 텍스트를 입력 → 대상 필드를 선택 → "바꾸기" 클릭으로 일괄 치환. 선택한 행만 또는 전체 행 대상 선택 가능</td></tr>
                <tr><td style={s.td}>검색...</td><td style={s.td}>TC 검색</td><td style={s.td}>TC ID, 제목, 카테고리 등으로 필터링</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>4-2. 폴더 / 시트 관리 (사이드바)</h3>
            <p style={s.p}>프로젝트 내에서 TC를 <strong>폴더</strong>와 <strong>시트</strong>로 계층 분류할 수 있습니다. 왼쪽 사이드바에서 VS Code 스타일의 트리로 관리합니다.</p>
            <div style={s.infoBox}>
              <strong>폴더와 시트의 차이:</strong>
              <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
                <li><strong>📁 폴더</strong> — TC를 직접 담지 않고, 하위 폴더나 시트를 그룹화하는 용도. 클릭 시 펼침/접기만 동작</li>
                <li><strong>📄 시트</strong> — 실제 TC가 저장되는 단위. 클릭 시 해당 시트의 TC가 그리드에 표시</li>
              </ul>
            </div>
            <ul style={s.ul}>
              <li><strong>빈 프로젝트</strong>에서는 화면 중앙에 "폴더 추가", "시트 추가", "Excel Import" 버튼이 표시됩니다.</li>
              <li><strong>폴더 추가:</strong> 사이드바 상단의 <strong>📁+</strong> 버튼으로 루트 폴더를 추가합니다. 폴더 노드의 <strong>📁+</strong> 버튼으로 하위 폴더를 추가할 수 있습니다.</li>
              <li><strong>시트 추가:</strong> 사이드바 상단의 <strong>📄+</strong> 버튼으로 루트 시트를 추가합니다. 폴더 노드의 <strong>📄+</strong> 버튼으로 폴더 안에 시트를 추가할 수 있습니다.</li>
              <li><strong>시트 전환:</strong> 사이드바에서 시트(📄)를 클릭하면 해당 시트의 TC만 표시됩니다.</li>
              <li><strong>전체 보기:</strong> 시트가 2개 이상일 때 사이드바 상단에 "전체" 항목이 나타나며, 모든 시트의 TC를 한 번에 볼 수 있습니다.</li>
              <li><strong>삭제:</strong> 폴더/시트의 인라인 <strong>×</strong> 버튼으로 삭제합니다. 폴더 삭제 시 하위 항목과 TC가 모두 함께 삭제됩니다.</li>
              <li><strong>Excel Import 시</strong> 엑셀 파일의 시트 이름이 그대로 사이드바 트리에 시트로 생성됩니다.</li>
              <li><strong>사이드바 접기/펼치기:</strong> ◀/▶ 토글 버튼으로 사이드바를 접거나 펼칠 수 있습니다.</li>
            </ul>

            <h3 style={s.h3}>4-3. 그리드 편집</h3>
            <img src="/manual-images/08_tc_grid_detail.png" alt="TC 그리드" style={s.img} />
            <ul style={s.ul}>
              <li>셀을 더블 클릭하면 인라인 편집 모드로 진입합니다.</li>
              <li>체크박스로 행을 선택하여 복사/삭제/일괄변경 대상을 지정합니다.</li>
              <li>컬럼 헤더 클릭으로 정렬할 수 있습니다.</li>
              <li>셀 편집 내용은 <strong>자동 저장</strong>됩니다. 별도의 저장 버튼이 없습니다.</li>
              <li>행 추가 시에도 즉시 서버에 저장되며, Undo(Ctrl+Z)로 되돌릴 수 있습니다.</li>
            </ul>

            <h3 style={s.h3}>4-4. TC 삭제 및 복원</h3>
            <ul style={s.ul}>
              <li>TC를 삭제하면 <strong>소프트 삭제</strong>됩니다. 즉시 영구 삭제되지 않습니다.</li>
              <li>삭제된 TC는 <strong>7일간 복원 가능</strong>합니다. 7일이 지나면 자동으로 영구 삭제됩니다.</li>
              <li>복원이 필요한 경우 관리자에게 요청하거나, API를 통해 복원할 수 있습니다: <code>POST /api/projects/:id/testcases/:tc_id/restore</code></li>
            </ul>
            <div style={s.warnBox}>
              <strong>주의:</strong> 시트 삭제 시에는 소속된 모든 TC가 함께 삭제됩니다. 하위 시트가 있는 경우 하위 시트의 TC까지 모두 삭제됩니다.
            </div>

            <h3 style={s.h3}>4-5. TC 필드 설명</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>필드</th><th style={s.th}>설명</th><th style={s.th}>예시</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>No</td><td style={s.td}>순번 (자동)</td><td style={s.td}>1, 2, 3...</td></tr>
                <tr><td style={s.td}>TC ID</td><td style={s.td}>고유 식별자</td><td style={s.td}>TC-PM-001</td></tr>
                <tr><td style={s.td}>Type</td><td style={s.td}>유형</td><td style={s.td}>Func., UI/UX, Perf., Security, API, Data</td></tr>
                <tr><td style={s.td}>Category</td><td style={s.td}>카테고리 (대분류)</td><td style={s.td}>프로젝트 관리 진입</td></tr>
                <tr><td style={s.td}>Depth 1</td><td style={s.td}>중분류</td><td style={s.td}>엔터프라이즈</td></tr>
                <tr><td style={s.td}>Depth 2</td><td style={s.td}>소분류</td><td style={s.td}>타이틀</td></tr>
                <tr><td style={s.td}>Priority</td><td style={s.td}>우선순위</td><td style={s.td}>매우 높음, 높음, 보통, 낮음, 매우 낮음</td></tr>
                <tr><td style={s.td}>Platform</td><td style={s.td}>플랫폼</td><td style={s.td}>WEB, Mobile, iOS, Android, API, 공통</td></tr>
                <tr><td style={s.td}>Precondition</td><td style={s.td}>사전 조건</td><td style={s.td}>의뢰인으로 로그인</td></tr>
                <tr><td style={s.td}>Test Steps</td><td style={s.td}>테스트 절차</td><td style={s.td}>1. 메뉴를 클릭한다. 2. ...</td></tr>
                <tr><td style={s.td}>Expected Result</td><td style={s.td}>기대 결과</td><td style={s.td}>1. 페이지가 표시된다.</td></tr>
                <tr><td style={s.td}>Issue Link</td><td style={s.td}>Jira 이슈 키. 설정 탭에서 Jira Base URL을 입력하면 클릭 시 해당 이슈 페이지로 이동 (예: https://jira.example.com/browse/PROJ-123)</td><td style={s.td}>PROJ-123</td></tr>
                <tr><td style={s.td}>Assignee</td><td style={s.td}>담당자</td><td style={s.td}>홍길동</td></tr>
                <tr><td style={s.td}>Remarks</td><td style={s.td}>비고</td><td style={s.td}>추가 참고사항</td></tr>
              </tbody>
            </table>
          </section>

          {/* 17. 테스트 수행 */}
          {/* 5. 폴더/시트 트리 구조 (VS Code 스타일 사이드바) */}
          <section id="sheet-tree" style={s.section}>
            <h2 style={s.h2}>5. 폴더 / 시트 트리 구조</h2>
            <img src="/manual-images/30_sheet_tree_tabs.png" alt="폴더/시트 트리 사이드바" style={s.img} />
            <p style={s.p}>TC를 <strong>폴더</strong>(📁)와 <strong>시트</strong>(📄)로 계층화하여 관리합니다. VS Code 스타일의 왼쪽 사이드바에서 트리 형태로 표시됩니다.</p>

            <h3 style={s.h3}>5-1. 폴더와 시트의 차이</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>구분</th><th style={s.th}>아이콘</th><th style={s.th}>역할</th><th style={s.th}>TC 저장</th><th style={s.th}>하위 항목</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>폴더</td><td style={s.td}>📁 / 📂</td><td style={s.td}>시트를 그룹화하는 컨테이너</td><td style={s.td}>불가</td><td style={s.td}>하위 폴더, 시트 추가 가능</td></tr>
                <tr><td style={s.td}>시트</td><td style={s.td}>📄</td><td style={s.td}>TC가 실제 저장되는 단위</td><td style={s.td}>가능</td><td style={s.td}>하위 항목 추가 불가</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>5-2. 사이드바 구조</h3>
            <ul style={s.ul}>
              <li>화면 왼쪽에 사이드바가 표시되며, 폴더와 시트가 트리 형태로 나열됩니다.</li>
              <li>폴더는 <strong>📁</strong>(접힌 상태) / <strong>📂</strong>(펼친 상태) 아이콘으로 표시됩니다.</li>
              <li>시트는 <strong>📄</strong> 아이콘으로 표시되며, 옆에 TC 수가 표시됩니다.</li>
              <li>하위 항목은 들여쓰기로 깊이(depth)를 시각적으로 구분합니다.</li>
              <li>사이드바 상단의 <strong>◀/▶</strong> 토글 버튼으로 사이드바를 접거나 펼칠 수 있습니다.</li>
            </ul>

            <h3 style={s.h3}>5-3. 폴더/시트 추가</h3>
            <img src="/manual-images/31_sheet_tree_add_child.png" alt="폴더/시트 추가" style={s.img} />
            <ul style={s.ul}>
              <li><strong>루트에 추가:</strong> 사이드바 상단의 <strong>📁+</strong>(폴더 추가) 또는 <strong>📄+</strong>(시트 추가) 버튼을 클릭합니다.</li>
              <li><strong>폴더 안에 추가:</strong> 폴더 노드의 <strong>📁+</strong>(하위 폴더) 또는 <strong>📄+</strong>(하위 시트) 버튼을 클릭합니다.</li>
              <li>시트(📄) 노드에는 하위 항목을 추가할 수 없습니다.</li>
              <li>입력 폼에 추가 유형(📁 폴더 / 📄 시트)이 표시되며, 이름을 입력 후 Enter 또는 "추가" 버튼을 클릭합니다.</li>
            </ul>

            <h3 style={s.h3}>5-4. 삭제 (CASCADE)</h3>
            <ul style={s.ul}>
              <li>폴더를 삭제하면 <strong>모든 하위 폴더, 시트, TC가 함께 삭제</strong>됩니다.</li>
              <li>삭제 확인 메시지에 하위 항목 수가 표시됩니다.</li>
              <li>폴더/시트의 인라인 <strong>×</strong> 버튼으로 삭제합니다.</li>
            </ul>

            <div style={s.infoBox}>
              <strong>기존 호환:</strong> 폴더를 사용하지 않으면 기존과 동일하게 시트만으로 TC를 관리할 수 있습니다.
            </div>
          </section>

          {/* 16. 커스텀 필드 */}
          {/* 16. 커스텀 필드 */}
          <section id="custom-fields" style={s.section}>
            <h2 style={s.h2}>6. 커스텀 필드</h2>
            <img src="/manual-images/32_custom_fields_grid.png" alt="커스텀 필드 그리드" style={s.img} />
            <p style={s.p}>프로젝트별로 TC에 사용자 정의 컬럼을 추가할 수 있습니다.</p>

            <h3 style={s.h3}>6-1. 필드 타입</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>타입</th><th style={s.th}>설명</th><th style={s.th}>예시</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>text</td><td style={s.td}>자유 텍스트 입력. 셀 더블클릭으로 편집</td><td style={s.td}>메모, 참고사항</td></tr>
                <tr><td style={s.td}>number</td><td style={s.td}>숫자만 입력 가능. 문자 입력 시 무시됨</td><td style={s.td}>예상 시간(분), 점수</td></tr>
                <tr><td style={s.td}>select</td><td style={s.td}>단일 선택 드롭다운. 설정에서 정의한 옵션 중 하나를 선택</td><td style={s.td}>환경: Dev/QA/Prod</td></tr>
                <tr><td style={s.td}>multiselect</td><td style={s.td}>복수 선택 드롭다운. 여러 옵션을 체크하여 선택 가능</td><td style={s.td}>태그: Smoke, Regression</td></tr>
                <tr><td style={s.td}>checkbox</td><td style={s.td}>체크박스 토글. 클릭으로 참/거짓 전환</td><td style={s.td}>자동화 여부</td></tr>
                <tr><td style={s.td}>date</td><td style={s.td}>날짜 선택기(캘린더 팝업)로 날짜 입력</td><td style={s.td}>마감일</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>6-2. 필드 관리 (설정 탭)</h3>
            <img src="/manual-images/32_custom_fields_grid.png" alt="커스텀 필드 설정 UI" style={s.img} />
            <ul style={s.ul}>
              <li>프로젝트 <strong>설정</strong> 탭에서 커스텀 필드를 관리할 수 있습니다.</li>
              <li><strong>필드 추가:</strong> 필드 이름과 타입(6종)을 선택하고, select/multiselect 타입은 옵션을 입력하여 추가합니다.</li>
              <li>추가된 필드는 목록 테이블에 표시되며, <strong>삭제</strong> 버튼으로 제거할 수 있습니다.</li>
              <li>생성된 필드는 TC 관리 그리드에 자동으로 컬럼이 추가됩니다.</li>
              <li>select 타입은 드롭다운 에디터가 자동 적용됩니다.</li>
            </ul>

            <div style={s.tipBox}>
              <strong>TIP:</strong> 커스텀 필드 값은 TC의 <code>custom_fields</code> JSON 필드에 저장됩니다. Import/Export 시에도 유지됩니다.
            </div>
          </section>

          {/* 18. 테스트 플랜 */}
          {/* 17. CSV Import */}
          <section id="import" style={s.section}>
            <h2 style={s.h2}>7. Import (Excel / CSV / Markdown)</h2>
            <img src="/manual-images/34_tc_toolbar_with_filter.png" alt="TC 툴바 (CSV 지원)" style={s.img} />
            <p style={s.p}>Excel 외에 CSV 파일로도 TC를 가져올 수 있습니다. Jira, Xray, Zephyr Scale에서 내보낸 CSV를 바로 import할 수 있습니다.</p>

            <h3 style={s.h3}>7-1. 사용 방법</h3>
            <ol style={s.ol}>
              <li>TC 관리 툴바에서 <strong>Import</strong> 버튼을 클릭합니다.</li>
              <li>파일 선택 대화상자에서 <strong>.csv</strong>, <strong>.xlsx</strong>, 또는 <strong>.md</strong> 파일을 선택합니다.</li>
              <li>CSV 파일의 경우 자동으로 헤더를 분석하여 TC 필드에 매핑합니다.</li>
            </ol>

            <h3 style={s.h3}>7-2. Jira 헤더 매핑</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>Jira 헤더</th><th style={s.th}>TC 필드</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>Issue key / Key</td><td style={s.td}>TC ID</td></tr>
                <tr><td style={s.td}>Summary / Name</td><td style={s.td}>Depth 2</td></tr>
                <tr><td style={s.td}>Priority</td><td style={s.td}>Priority</td></tr>
                <tr><td style={s.td}>Component/s</td><td style={s.td}>Category</td></tr>
                <tr><td style={s.td}>Description</td><td style={s.td}>Test Steps</td></tr>
                <tr><td style={s.td}>Assignee</td><td style={s.td}>Assignee</td></tr>
                <tr><td style={s.td}>Epic Link / Epic Name</td><td style={s.td}>Depth 1</td></tr>
                <tr><td style={s.td}>Precondition / Test Data</td><td style={s.td}>Precondition</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>7-3. 인코딩 지원</h3>
            <ul style={s.ul}>
              <li>UTF-8, UTF-8 BOM, CP949(EUC-KR) 인코딩을 자동 감지합니다.</li>
              <li>한글 헤더(<code>대분류</code>, <code>우선순위</code>, <code>테스트 절차</code> 등)도 자동 매핑됩니다.</li>
              <li><strong>덮어쓰기 정책:</strong> Import 파일의 TC ID가 기존 TC와 동일하면 해당 TC의 모든 필드가 파일 내용으로 갱신됩니다. TC ID가 없는 행은 신규 TC로 추가됩니다.</li>
            </ul>

            <div style={s.tipBox}>
              <strong>TIP:</strong> Jira에서 이슈 목록을 CSV로 내보내기: 이슈 검색 결과 → 우측 상단 "Export" → "CSV (All fields)"
            </div>
          </section>

          {/* 7-1. Markdown Import */}
          {/* 7-1. Markdown Import */}
          <section id="md-import" style={s.section}>
            <h2 style={s.h2}>7-1. Markdown Import</h2>
            <p style={s.p}>Markdown(.md) 파일에 작성한 테이블을 TC로 가져올 수 있습니다. 문서 기반 TC 관리나 GitHub/Wiki에서 작성한 TC를 바로 import할 때 유용합니다.</p>

            <h3 style={s.h3}>7-4. 사용 방법</h3>
            <ol style={s.ol}>
              <li>TC 관리 툴바에서 <strong>Import</strong> 버튼을 클릭합니다.</li>
              <li>파일 선택 대화상자에서 <strong>.md</strong> 파일을 선택합니다.</li>
              <li>파일 내 Markdown 테이블이 자동 파싱됩니다.</li>
              <li>테이블이 여러 개면 시트 선택 모달이 표시됩니다.</li>
            </ol>

            <h3 style={s.h3}>7-5. 지원 형식</h3>
            <p style={s.p}>표준 Markdown 테이블 문법을 사용합니다. 첫 번째 행은 헤더, 두 번째 행은 구분자(<code>|---|</code>), 그 이후가 데이터입니다.</p>
            <pre style={{...s.p, backgroundColor: "var(--bg-secondary)", padding: "16px", borderRadius: "8px", fontFamily: "monospace", fontSize: "13px", whiteSpace: "pre", overflowX: "auto"}}>{`# 로그인 테스트

| TC ID  | Category | Priority | Test Steps         | Expected Result    |
|--------|----------|----------|--------------------|--------------------|
| TC-001 | 로그인   | High     | 정상 로그인 시도    | 메인 화면 이동      |
| TC-002 | 로그인   | Medium   | 잘못된 비번 입력    | 에러 메시지 표시    |

## 검색 기능

| TC ID  | Category | Priority | Test Steps         | Expected Result    |
|--------|----------|----------|--------------------|--------------------|
| TC-003 | 검색     | High     | 키워드 입력 후 검색 | 검색 결과 표시      |`}</pre>

            <h3 style={s.h3}>7-6. 시트 이름 규칙</h3>
            <ul style={s.ul}>
              <li>테이블 위의 <code>#</code> 또는 <code>##</code> 제목이 <strong>시트 이름</strong>이 됩니다.</li>
              <li>위 예시에서 "로그인 테스트"와 "검색 기능"이 각각 시트 이름이 됩니다.</li>
              <li>제목이 없는 테이블은 "MD Import"라는 기본 이름이 사용됩니다.</li>
              <li>하나의 .md 파일에 여러 테이블을 넣으면 각각 다른 시트로 import됩니다.</li>
            </ul>

            <h3 style={s.h3}>7-7. 헤더 매핑</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>Markdown 헤더</th><th style={s.th}>TC 필드</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>TC ID / tc_id</td><td style={s.td}>TC ID</td></tr>
                <tr><td style={s.td}>Category / 카테고리 / 대분류</td><td style={s.td}>Category</td></tr>
                <tr><td style={s.td}>Priority / 우선순위</td><td style={s.td}>Priority</td></tr>
                <tr><td style={s.td}>Test Steps / Steps / 테스트 절차</td><td style={s.td}>Test Steps</td></tr>
                <tr><td style={s.td}>Expected Result / 기대 결과</td><td style={s.td}>Expected Result</td></tr>
                <tr><td style={s.td}>Depth1 / Depth2</td><td style={s.td}>Depth 1 / Depth 2</td></tr>
                <tr><td style={s.td}>Precondition / 사전조건</td><td style={s.td}>Precondition</td></tr>
                <tr><td style={s.td}>Assignee / 담당자</td><td style={s.td}>Assignee</td></tr>
                <tr><td style={s.td}>Remarks / 비고</td><td style={s.td}>Remarks</td></tr>
              </tbody>
            </table>
            <p style={s.p}>Excel/CSV Import와 동일한 헤더 매핑 규칙을 사용합니다. 한글/영문 헤더 모두 지원됩니다.</p>

            <h3 style={s.h3}>7-8. 주의사항</h3>
            <ul style={s.ul}>
              <li>셀 안에 파이프(<code>|</code>)를 사용하려면 <code>\|</code>로 이스케이프하세요.</li>
              <li>TC ID가 기존 TC와 동일하면 해당 TC가 덮어쓰기됩니다.</li>
              <li>TC ID가 없는 행은 <code>MD-0001</code>, <code>MD-0002</code> 형식으로 자동 생성됩니다.</li>
              <li>테이블 사이의 일반 텍스트(설명, 목록 등)는 무시됩니다.</li>
              <li>인코딩: UTF-8, UTF-8 BOM, CP949(EUC-KR) 자동 감지됩니다.</li>
            </ul>

            <div style={s.tipBox}>
              <strong>TIP:</strong> GitHub, Notion, Obsidian 등에서 작성한 Markdown 테이블을 그대로 .md 파일로 저장하여 import할 수 있습니다.
            </div>
          </section>

          {/* 15. 고급 필터 */}
          {/* 15. 고급 필터 */}
          <section id="advanced-filter" style={s.section}>
            <h2 style={s.h2}>8. 고급 필터 + 저장된 뷰</h2>
            <img src="/manual-images/33_advanced_filter_panel.png" alt="고급 필터 패널" style={s.img} />
            <p style={s.p}>다중 조건으로 TC를 필터링하고, 자주 쓰는 필터를 저장하여 재사용할 수 있습니다.</p>

            <h3 style={s.h3}>8-1. 필터 패널 열기</h3>
            <ol style={s.ol}>
              <li>TC 관리 툴바 우측의 <strong>필터</strong> 버튼을 클릭합니다.</li>
              <li>필터 패널이 그리드 위에 표시됩니다.</li>
              <li><strong>+ 조건 추가</strong> 버튼으로 필터 조건을 추가합니다.</li>
            </ol>

            <h3 style={s.h3}>8-2. 조건 설정</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>항목</th><th style={s.th}>설명</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>필드</td><td style={s.td}>TC ID, Type, Category, Priority, Assignee 등 선택</td></tr>
                <tr><td style={s.td}>연산자</td><td style={s.td}>포함, 미포함, 일치, 불일치, 비어있음, 비어있지 않음</td></tr>
                <tr><td style={s.td}>값</td><td style={s.td}>필터링할 값 입력 (비어있음/비어있지 않음은 값 불필요)</td></tr>
                <tr><td style={s.td}>논리</td><td style={s.td}><strong>AND</strong> (모두 일치) 또는 <strong>OR</strong> (하나라도 일치). 전체 조건에 하나의 논리 연산자가 적용됨 (예: 조건 3개 + AND → 3개 모두 만족하는 TC만 표시)</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>8-3. 필터 저장/불러오기</h3>
            <ul style={s.ul}>
              <li><strong>저장</strong> 버튼: 현재 필터 조건을 이름을 지정하여 저장합니다.</li>
              <li><strong>불러오기</strong> 버튼: 저장된 필터 목록에서 선택하여 복원합니다.</li>
              <li><strong>초기화</strong> 버튼: 모든 필터 조건을 제거하고 전체 TC를 표시합니다.</li>
            </ul>

            <div style={s.tipBox}>
              <strong>TIP:</strong> 필터가 적용 중일 때 필터 버튼에 조건 수가 표시됩니다 (예: <code>필터 (3)</code>).
            </div>
          </section>
          {/* 17. 테스트 수행 */}
          <section id="testrun" style={s.section}>
            <h2 style={s.h2}>9. 테스트 수행</h2>
            <img src="/manual-images/09_testrun_tab.png" alt="테스트 수행 탭" style={s.img} />

            <h3 style={s.h3}>9-1. 테스트 런 생성</h3>
            <ol style={s.ol}>
              <li>좌측 패널 하단의 <strong>"+ New Test Run"</strong> 버튼을 클릭합니다.</li>
              <li>런 이름, 라운드(R1/R2/...), 버전, 환경을 입력합니다.</li>
              <li>생성 시 프로젝트의 모든 TC가 <strong>NS(미실행)</strong> 상태로 포함됩니다.</li>
            </ol>

            <h3 style={s.h3}>9-2. 테스트 런 목록</h3>
            <ul style={s.ul}>
              <li>좌측 패널에 프로젝트의 모든 테스트 런이 표시됩니다.</li>
              <li>런 이름, 라운드, 버전, 상태(진행 중/완료)가 표시됩니다.</li>
              <li>런을 클릭하면 우측에 결과 그리드가 표시됩니다.</li>
            </ul>

            <h3 style={s.h3}>9-3. 결과 입력</h3>
            <div style={s.featureGrid}>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>🖱️</div>
                <div>
                  <strong>마우스 클릭</strong>
                  <p style={s.featureDesc}>결과 셀을 클릭하여 드롭다운에서 PASS/FAIL/BLOCK/N/A/NS를 선택합니다.</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>⌨️</div>
                <div>
                  <strong>키보드 단축키</strong>
                  <p style={s.featureDesc}>셀 선택 후 P(Pass), F(Fail), B(Block), N(NS) 키로 빠르게 결과를 입력합니다.</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📋</div>
                <div>
                  <strong>범위 채우기</strong>
                  <p style={s.featureDesc}>Ctrl+D로 현재 값을 아래로 복사하거나, Shift+Click으로 범위를 선택합니다.</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>↩️</div>
                <div>
                  <strong>Undo/Redo</strong>
                  <p style={s.featureDesc}>Ctrl+Z로 실행 취소, Ctrl+Shift+Z로 재실행합니다. (최대 200단계)</p>
                </div>
              </div>
            </div>

            <h3 style={s.h3}>9-4. 첨부파일</h3>
            <ul style={s.ul}>
              <li>결과 행에 이미지/문서 파일을 첨부할 수 있습니다.</li>
              <li>지원 형식: 이미지(PNG, JPEG, GIF, BMP, WebP), 문서(PDF, DOC, XLSX, PPTX), 아카이브(ZIP), 텍스트(TXT, CSV, LOG)</li>
              <li>파일 크기 제한: <strong>50MB</strong></li>
              <li>이미지 파일은 미리보기가 제공됩니다.</li>
            </ul>

            <h3 style={s.h3}>9-5. 런 관리</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>기능</th><th style={s.th}>설명</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>완료</td><td style={s.td}>런 상태를 "완료"로 변경합니다. 미수행(NS) TC가 남아있으면 확인 메시지가 표시됩니다. 완료된 런은 편집이 잠깁니다.</td></tr>
                <tr><td style={s.td}>다시 수행</td><td style={s.td}>완료된 런을 "진행중"으로 되돌립니다. 기존 결과 데이터는 그대로 유지되며 초기화되지 않습니다. 추가 수행이나 결과 수정이 필요할 때 사용합니다.</td></tr>
                <tr><td style={s.td}>복제</td><td style={s.td}>런 구조(이름, 라운드, 환경, TC 목록)를 복제하여 새 런을 생성합니다. 모든 결과는 NS로 초기화되며, 첨부파일과 코멘트는 복제되지 않습니다.</td></tr>
                <tr><td style={s.td}>삭제</td><td style={s.td}>런과 모든 결과, 첨부파일을 영구 삭제합니다. 복원할 수 없으므로 주의하세요.</td></tr>
                <tr><td style={s.td}>내보내기</td><td style={s.td}>런 결과를 Excel(.xlsx) 파일로 다운로드합니다. TC ID, 제목, 결과, 코멘트 등 전체 필드가 포함됩니다.</td></tr>
              </tbody>
            </table>
            <h3 style={s.h3}>9-6. 타이머 기능</h3>
            <ul style={s.ul}>
              <li>런 결과 그리드 상단의 <strong>타이머 토글</strong>을 켜면 각 TC 행에 타이머가 표시됩니다.</li>
              <li>TC 수행 시작 시 타이머가 자동으로 시작되고, 결과 입력 시 경과 시간이 기록됩니다.</li>
              <li>기록된 시간은 리포트 및 내보내기에 포함됩니다.</li>
            </ul>
            <div style={s.tipBox}>
              <strong>TIP:</strong> 타이머는 선택 사항입니다. 토글을 끄면 시간 기록 없이 결과만 입력할 수 있습니다.
            </div>
          </section>

          {/* 15. 비교 */}
          {/* 18. 테스트 플랜 */}
          <section id="test-plans" style={s.section}>
            <h2 style={s.h2}>10. 테스트 플랜 / 마일스톤</h2>
            <img src="/manual-images/35_dashboard_with_plan.png" alt="테스트 플랜 대시보드" style={s.img} />
            <p style={s.p}>릴리즈 단위로 테스트를 계획하고 진행률을 관리할 수 있습니다.</p>

            <h3 style={s.h3}>10-1. 플랜 생성</h3>
            <ul style={s.ul}>
              <li>API를 통해 테스트 플랜을 생성합니다: <code>POST /api/projects/:id/testplans</code></li>
              <li>플랜에는 이름, 마일스톤, 설명, 시작일/종료일을 설정할 수 있습니다.</li>
            </ul>

            <h3 style={s.h3}>10-2. TestRun 연결</h3>
            <ul style={s.ul}>
              <li>TestRun 생성 시 <code>test_plan_id</code>를 지정하여 플랜에 연결합니다.</li>
              <li>하나의 플랜에 여러 TestRun을 연결할 수 있습니다.</li>
            </ul>

            <h3 style={s.h3}>10-3. 진행률 확인</h3>
            <ul style={s.ul}>
              <li>플랜 조회 시 연결된 모든 TestRun의 결과가 합산되어 <strong>pass_rate</strong>가 계산됩니다.</li>
              <li>총 TC 수, PASS/FAIL/BLOCK/NA/NS 건수를 한 번에 확인할 수 있습니다.</li>
            </ul>

            <div style={s.infoBox}>
              <strong>참고:</strong> 플랜 삭제 시 연결된 TestRun은 삭제되지 않으며, Run의 <code>test_plan_id</code>가 null로 해제됩니다.
            </div>
          </section>

          {/* 17. CSV Import */}
          {/* 15. 비교 */}
          <section id="compare" style={s.section}>
            <h2 style={s.h2}>11. 비교</h2>
            <img src="/manual-images/12_compare_tab.png" alt="비교 탭" style={s.img} />
            <p style={s.p}>두 개의 테스트 런을 선택하여 결과를 나란히 비교할 수 있습니다.</p>
            <ol style={s.ol}>
              <li>좌측(기준) 런과 우측(대상) 런을 각각 선택합니다.</li>
              <li>비교 테이블에서 각 TC별 좌/우 결과를 확인합니다.</li>
              <li>필터로 <strong>변경된 항목만</strong> 또는 <strong>리그레션만</strong>(PASS→FAIL) 볼 수 있습니다.</li>
            </ol>
            <div style={s.infoBox}>
              <strong>통계 정보:</strong> 상단에 총 TC 수, 변경 건수, 리그레션 건수, 개선 건수가 표시됩니다.
            </div>
          </section>

          {/* 17. 대시보드 */}
          {/* 17. 대시보드 */}
          <section id="dashboard" style={s.section}>
            <h2 style={s.h2}>12. 대시보드</h2>
            <img src="/manual-images/13_dashboard_top.png" alt="대시보드 상단" style={s.img} />
            <p style={s.p}>선택한 테스트 런의 결과를 다양한 차트와 통계로 분석합니다.</p>

            <h3 style={s.h3}>12-1. 요약 카드</h3>
            <ul style={s.ul}>
              <li><strong>전체 TC</strong>: 테스트 케이스 총 개수와 실행률</li>
              <li><strong>PASS</strong>: 통과 건수 및 비율</li>
              <li><strong>FAIL</strong>: 실패 건수 및 비율</li>
              <li><strong>BLOCK</strong>: 블록 건수 및 비율</li>
              <li><strong>N/A</strong>: 해당없음 건수 및 비율</li>
              <li><strong>미수행</strong>: 미실행 건수 및 비율</li>
            </ul>

            <h3 style={s.h3}>12-2. 차트</h3>
            <img src="/manual-images/14_dashboard_charts.png" alt="대시보드 차트" style={s.img} />
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>차트</th><th style={s.th}>설명</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>결과 분포 (도넛)</td><td style={s.td}>PASS/FAIL/BLOCK/N/A/미수행 비율을 도넛 차트로 시각화</td></tr>
                <tr><td style={s.td}>라운드별 비교 (바)</td><td style={s.td}>테스트 런 생성 시 지정한 라운드(R1, R2, R3...)별 결과 추이를 스택 바 차트로 표시. 동일 라운드에 여러 런이 있으면 합산됨</td></tr>
                <tr><td style={s.td}>우선순위별 분포</td><td style={s.td}>우선순위별 TC 수, PASS/FAIL/BLOCK/N/A/미수행 건수 테이블</td></tr>
                <tr><td style={s.td}>카테고리별 분포</td><td style={s.td}>카테고리별 결과 분포 테이블</td></tr>
                <tr><td style={s.td}>담당자별 현황</td><td style={s.td}>담당자별 할당/완료/통과율 테이블</td></tr>
                <tr><td style={s.td}>실패 히트맵</td><td style={s.td}>카테고리 × 우선순위 매트릭스의 실패 건수를 색상 강도로 표시</td></tr>
              </tbody>
            </table>
          </section>

          {/* 18. 리포트 */}
          {/* 18. 리포트 */}
          <section id="report" style={s.section}>
            <h2 style={s.h2}>13. 리포트</h2>
            <img src="/manual-images/16_report_tab.png" alt="리포트 탭" style={s.img} />
            <p style={s.p}>테스트 런 결과를 요약 리포트로 확인하고, PDF/Excel로 다운로드할 수 있습니다.</p>
            <ol style={s.ol}>
              <li>리포트 탭에서 테스트 런을 선택합니다.</li>
              <li>요약 섹션: 총 TC, 결과별 건수/비율 등을 확인합니다.</li>
              <li>실패 목록: FAIL 결과의 TC 상세를 확인합니다.</li>
              <li>PDF 다운로드: <strong>PDF</strong> 버튼 클릭으로 서식화된 PDF 리포트를 다운로드합니다.</li>
              <li>Excel 다운로드: <strong>Excel</strong> 버튼 클릭으로 엑셀 리포트를 다운로드합니다.</li>
            </ol>
          </section>

          {/* 15. 설정 */}
          {/* 15. 설정 */}
          <section id="settings" style={s.section}>
            <h2 style={s.h2}>14. 설정</h2>
            <img src="/manual-images/17_settings_tab.png" alt="설정 탭" style={s.img} />

            <h3 style={s.h3}>14-1. 프로젝트 정보</h3>
            <ul style={s.ul}>
              <li>프로젝트명, 설명을 수정할 수 있습니다.</li>
              <li><strong>Jira Base URL:</strong> Jira 서버 주소를 입력합니다 (예: <code>https://jira.example.com</code>). 설정하면 TC의 Issue Link 필드에 입력한 이슈 키(예: PROJ-123)를 클릭할 때 <code>Jira Base URL/browse/PROJ-123</code>으로 이동합니다.</li>
              <li><strong>공개/비공개:</strong> 공개 프로젝트는 모든 로그인 사용자가 조회할 수 있습니다 (수정은 멤버만 가능). 비공개 프로젝트는 프로젝트 멤버와 생성자만 접근할 수 있습니다. 기본값은 <strong>공개</strong>입니다.</li>
            </ul>

            <h3 style={s.h3}>14-2. 기본 필드 설정</h3>
            <p style={s.p}>프로젝트의 기본 TC 필드(TC ID, Type, Category 등)의 <strong>표시 이름 변경</strong>과 <strong>숨김 설정</strong>이 가능합니다.</p>
            <ul style={s.ul}>
              <li><strong>표시 이름:</strong> 기본 영문 헤더를 한글이나 팀 용어로 변경할 수 있습니다 (예: Category → 모듈, Depth 1 → 대분류).</li>
              <li><strong>표시 체크박스:</strong> 사용하지 않는 필드를 그리드에서 숨길 수 있습니다.</li>
              <li><strong>필수 필드:</strong> TC ID, Test Steps, Expected Result은 숨길 수 없습니다.</li>
              <li><strong>저장 버튼</strong>을 클릭해야 반영됩니다. 초기화 버튼으로 기본값으로 되돌릴 수 있습니다.</li>
              <li>설정은 프로젝트별로 독립 관리됩니다. Import/Export는 내부 필드명(영문)을 사용하므로 영향 없습니다.</li>
            </ul>

            <h3 style={s.h3}>14-3. 멤버 관리</h3>
            <img src="/manual-images/18_settings_members.png" alt="멤버 관리" style={s.img} />
            <ul style={s.ul}>
              <li>프로젝트에 사용자를 추가하고 프로젝트 역할을 부여합니다.</li>
              <li>프로젝트 역할: <strong>Project Admin</strong> (프로젝트 관리), <strong>Project Tester</strong> (테스트 수행)</li>
              <li>역할 변경 및 멤버 제거가 가능합니다 (프로젝트 생성자는 제거 불가).</li>
            </ul>
          </section>

          {/* 17. 테마 */}
          {/* 5. 역할별 권한 */}
          <section id="roles" style={s.section}>
            <h2 style={s.h2}>15. 역할별 권한</h2>

            <h3 style={s.h3}>15-1. 시스템 역할</h3>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>기능</th>
                  <th style={{ ...s.th, backgroundColor: "#CF222E", color: "#fff" }}>Admin</th>
                  <th style={{ ...s.th, backgroundColor: "#BF8700", color: "#fff" }}>QA Manager</th>
                  <th style={{ ...s.th, backgroundColor: "#6B7280", color: "#fff" }}>User</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>프로젝트 생성</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>사용자 관리/역할 변경</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>비밀번호 초기화</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>사용자 목록 조회</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>TC 생성/편집/삭제</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>프로젝트 Admin</td></tr>
                <tr><td style={s.td}>테스트 결과 기록</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>프로젝트 Tester+</td></tr>
                <tr><td style={s.td}>대시보드/리포트</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>접근 가능 프로젝트</td></tr>
                <tr><td style={s.td}>PDF/Excel 다운로드</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>접근 가능 프로젝트</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>15-2. 프로젝트 접근 규칙</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>프로젝트 유형</th><th style={s.th}>접근 조건</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>공개 프로젝트</td><td style={s.td}>모든 인증된 사용자가 조회 가능 (수정은 역할에 따름)</td></tr>
                <tr><td style={s.td}>비공개 프로젝트</td><td style={s.td}>프로젝트 멤버 또는 생성자만 접근 가능</td></tr>
                <tr><td style={s.td}>-</td><td style={s.td}>System Admin / QA Manager는 모든 프로젝트에 접근 가능</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>15-3. 시스템 역할과 프로젝트 역할의 관계</h3>
            <div style={s.infoBox}>
              <strong>이중 역할 구조:</strong> 시스템 역할(Admin/QA Manager/User)은 전역 권한을 결정하고, 프로젝트 역할(Project Admin/Project Tester)은 해당 프로젝트 내 권한을 결정합니다.
              <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
                <li><strong>System Admin</strong>: 모든 프로젝트에 전체 권한. 프로젝트 역할과 무관하게 모든 기능 사용 가능</li>
                <li><strong>QA Manager</strong>: 모든 프로젝트에 접근 가능. 프로젝트 생성 가능. 프로젝트 내에서는 관리자급 권한</li>
                <li><strong>User + Project Admin</strong>: 해당 프로젝트에서 TC 생성/편집/삭제, 런 관리, 설정 변경 가능</li>
                <li><strong>User + Project Tester</strong>: 해당 프로젝트에서 테스트 결과 기록, 대시보드/리포트 조회 가능. TC 생성/삭제는 불가</li>
                <li><strong>User (멤버 아님)</strong>: 공개 프로젝트만 조회 가능. 비공개 프로젝트는 접근 불가</li>
              </ul>
            </div>
          </section>

          {/* 5. 폴더/시트 트리 구조 (VS Code 스타일 사이드바) */}
          {/* 16. 헤더 */}
          <section id="header" style={s.section}>
            <h2 style={s.h2}>16. 헤더 / 네비게이션</h2>
            <img src="/manual-images/19_global_search.png" alt="헤더 - 글로벌 검색" style={s.img} />

            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>영역</th>
                  <th style={s.th}>기능</th>
                  <th style={s.th}>설명</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={s.td}>YM TestCase 로고</td>
                  <td style={s.td}>홈 이동</td>
                  <td style={s.td}>클릭 시 프로젝트 목록 페이지로 이동</td>
                </tr>
                <tr>
                  <td style={s.td}>프로젝트 셀렉터</td>
                  <td style={s.td}>프로젝트 빠른 전환</td>
                  <td style={s.td}>드롭다운에서 프로젝트 선택 시 해당 프로젝트 상세로 즉시 이동</td>
                </tr>
                <tr>
                  <td style={s.td}>TC 검색</td>
                  <td style={s.td}>글로벌 검색</td>
                  <td style={s.td}>2자 이상 입력 시 전체 프로젝트에서 TC를 검색. 결과 클릭 시 해당 TC로 이동 및 하이라이트</td>
                </tr>
                <tr>
                  <td style={s.td}>테마 토글</td>
                  <td style={s.td}>라이트/다크 전환</td>
                  <td style={s.td}>🌙 아이콘 클릭으로 테마 전환. 설정은 브라우저에 저장</td>
                </tr>
                <tr>
                  <td style={s.td}>관리 버튼</td>
                  <td style={s.td}>관리자 페이지</td>
                  <td style={s.td}>Admin 역할에만 표시. 사용자 관리 페이지로 이동</td>
                </tr>
                <tr>
                  <td style={s.td}>사용자 정보</td>
                  <td style={s.td}>표시명 + 역할</td>
                  <td style={s.td}>현재 로그인한 사용자명과 역할 뱃지 표시</td>
                </tr>
                <tr>
                  <td style={s.td}>로그아웃</td>
                  <td style={s.td}>세션 종료</td>
                  <td style={s.td}>클릭 시 로그아웃 후 로그인 페이지로 이동</td>
                </tr>
              </tbody>
            </table>
          </section>

          {/* 2. 프로젝트 상세 */}
          {/* 17. 테마 */}
          <section id="theme" style={s.section}>
            <h2 style={s.h2}>17. 테마 (다크모드)</h2>
            <img src="/manual-images/20_dark_mode_project.png" alt="다크모드 - 프로젝트" style={s.img} />
            <p style={s.p}>헤더의 🌙 아이콘을 클릭하여 라이트/다크 테마를 전환할 수 있습니다.</p>
            <img src="/manual-images/21_dark_mode_dashboard.png" alt="다크모드 - 대시보드" style={s.img} />
            <ul style={s.ul}>
              <li>테마 설정은 브라우저 로컬 스토리지에 저장되어 재접속 시에도 유지됩니다.</li>
              <li>모든 페이지, 그리드, 차트에 테마가 일괄 적용됩니다.</li>
            </ul>
          </section>

          {/* 18. 단축키 */}
          {/* 18. 단축키 */}
          <section id="shortcuts" style={s.section}>
            <h2 style={s.h2}>18. 단축키 모음</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>단축키</th><th style={s.th}>기능</th><th style={s.th}>사용 위치</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.tdCode}>P</td><td style={s.td}>PASS 입력</td><td style={s.td}>테스트 수행 그리드</td></tr>
                <tr><td style={s.tdCode}>F</td><td style={s.td}>FAIL 입력</td><td style={s.td}>테스트 수행 그리드</td></tr>
                <tr><td style={s.tdCode}>B</td><td style={s.td}>BLOCK 입력</td><td style={s.td}>테스트 수행 그리드</td></tr>
                <tr><td style={s.tdCode}>N</td><td style={s.td}>NS (미실행) 입력</td><td style={s.td}>테스트 수행 그리드</td></tr>
                <tr><td style={s.tdCode}>Ctrl + Z</td><td style={s.td}>실행 취소 (Undo)</td><td style={s.td}>TC 관리 / 테스트 수행</td></tr>
                <tr><td style={s.tdCode}>Ctrl + Shift + Z</td><td style={s.td}>재실행 (Redo)</td><td style={s.td}>TC 관리 / 테스트 수행</td></tr>
                <tr><td style={s.tdCode}>Ctrl + D</td><td style={s.td}>아래로 값 채우기</td><td style={s.td}>테스트 수행 그리드</td></tr>
                <tr><td style={s.tdCode}>Shift + Click</td><td style={s.td}>범위 선택</td><td style={s.td}>테스트 수행 그리드</td></tr>
                <tr><td style={s.tdCode}>Ctrl + C / V</td><td style={s.td}>복사 / 붙여넣기</td><td style={s.td}>TC 관리 그리드</td></tr>
                <tr><td style={s.tdCode}>Enter</td><td style={s.td}>셀 편집 확정</td><td style={s.td}>모든 그리드</td></tr>
                <tr><td style={s.tdCode}>Escape</td><td style={s.td}>편집 취소 / 모달 닫기</td><td style={s.td}>전역</td></tr>
              </tbody>
            </table>
          </section>

          {/* 5. 역할별 권한 */}

          {user?.role === "admin" && (
            <div style={s.adminLinkBox}>
              <span style={{ marginRight: 8 }}>관리자이신가요?</span>
              <span
                style={s.adminLink}
                onClick={() => navigate("/admin-manual")}
              >
                운영 매뉴얼 바로가기
              </span>
            </div>
          )}

          <div style={s.footer}>
            <p>YM TestCase v1.0.0.0 | 사용자 매뉴얼</p>
          </div>
        </main>
      </div>
    </div>
  );
}

/* ── Styles ── */
const s: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", backgroundColor: "var(--bg-page, #F5F7FA)", color: "var(--text-primary, #0F1923)" },
  topBar: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 24px", backgroundColor: "#1E293B", color: "#fff", position: "sticky" as const, top: 0, zIndex: 100 },
  topLeft: { display: "flex", alignItems: "center", gap: 16 },
  topRight: { display: "flex", alignItems: "center", gap: 12 },
  logo: { fontSize: 18, fontWeight: 700, cursor: "pointer" },
  badge: { fontSize: 12, padding: "3px 10px", borderRadius: 12, backgroundColor: "rgba(255,255,255,0.15)" },
  userName: { fontSize: 13, opacity: 0.8 },
  backBtn: { padding: "6px 16px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.3)", backgroundColor: "transparent", color: "#fff", cursor: "pointer", fontSize: 13 },
  container: { display: "flex", maxWidth: 1400, margin: "0 auto", gap: 0 },
  toc: { width: 220, minWidth: 220, padding: "24px 16px", position: "sticky" as const, top: 52, height: "calc(100vh - 52px)", overflowY: "auto" as const, borderRight: "1px solid var(--border-color, #E2E8F0)", backgroundColor: "var(--bg-card, #fff)" },
  tocTitle: { fontSize: 14, fontWeight: 700, marginBottom: 16, color: "var(--text-primary)" },
  tocItem: { display: "block", fontSize: 13, padding: "6px 8px", borderRadius: 4, color: "var(--text-secondary, #64748B)", textDecoration: "none", marginBottom: 2, lineHeight: 1.5 },
  main: { flex: 1, padding: "32px 48px", maxWidth: 960 },
  section: { marginBottom: 56, scrollMarginTop: 70 },
  h1: { fontSize: 28, fontWeight: 800, marginBottom: 8 },
  h2: { fontSize: 22, fontWeight: 700, marginBottom: 16, paddingBottom: 8, borderBottom: "2px solid var(--border-color, #E2E8F0)" },
  h3: { fontSize: 16, fontWeight: 600, marginTop: 28, marginBottom: 12, color: "var(--text-primary)" },
  p: { fontSize: 14, lineHeight: 1.8, color: "var(--text-secondary, #475569)", marginBottom: 12 },
  updatedAt: { fontSize: 13, color: "var(--text-secondary, #94A3B8)", marginBottom: 20 },
  img: { width: "100%", borderRadius: 8, border: "1px solid var(--border-color, #E2E8F0)", marginBottom: 16, boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
  ol: { fontSize: 14, lineHeight: 2, paddingLeft: 20, marginBottom: 16 },
  ul: { fontSize: 14, lineHeight: 2, paddingLeft: 20, marginBottom: 16 },
  infoBox: { fontSize: 14, lineHeight: 1.8, padding: "16px 20px", borderRadius: 8, backgroundColor: "var(--bg-card, #EFF6FF)", border: "1px solid #BFDBFE", marginBottom: 16 },
  tipBox: { fontSize: 13, lineHeight: 1.7, padding: "12px 16px", borderRadius: 8, backgroundColor: "#F0FDF4", border: "1px solid #86EFAC", marginBottom: 16, color: "#166534" },
  warnBox: { fontSize: 13, lineHeight: 1.7, padding: "12px 16px", borderRadius: 8, backgroundColor: "#FFFBEB", border: "1px solid #FCD34D", marginBottom: 16, color: "#92400E" },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: 13, marginBottom: 20 },
  th: { padding: "10px 12px", backgroundColor: "#1E293B", color: "#fff", textAlign: "left" as const, fontWeight: 600, borderBottom: "2px solid #334155" },
  td: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", verticalAlign: "top" as const },
  tdCode: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", fontFamily: "monospace", fontWeight: 600, backgroundColor: "var(--bg-input, #F8FAFC)" },
  tdCheck: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", textAlign: "center" as const, color: "#16A34A", fontWeight: 700 },
  tdX: { padding: "10px 12px", borderBottom: "1px solid var(--border-color, #E2E8F0)", textAlign: "center" as const, color: "#DC2626" },
  featureGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 },
  featureCard: { display: "flex", gap: 12, padding: 16, borderRadius: 8, border: "1px solid var(--border-color, #E2E8F0)", backgroundColor: "var(--bg-card, #fff)" },
  featureIcon: { fontSize: 24, minWidth: 36, textAlign: "center" as const },
  featureDesc: { fontSize: 13, color: "var(--text-secondary, #64748B)", marginTop: 4, lineHeight: 1.5 },
  adminLinkBox: { textAlign: "center" as const, padding: "20px", borderRadius: 8, backgroundColor: "#FEF2F2", border: "1px solid #FCA5A5", marginBottom: 20, fontSize: 14, color: "#991B1B" },
  adminLink: { color: "#DC2626", fontWeight: 700, cursor: "pointer", textDecoration: "underline" },
  footer: { textAlign: "center" as const, padding: "32px 0", color: "var(--text-secondary, #94A3B8)", fontSize: 13, borderTop: "1px solid var(--border-color, #E2E8F0)", marginTop: 40 },
};
