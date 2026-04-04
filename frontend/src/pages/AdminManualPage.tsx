import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

export default function AdminManualPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("adminManual");

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
          <span style={s.badge}>{t("badge")}</span>
        </div>
        <div style={s.topRight}>
          <span style={s.userName}>{user.display_name}</span>
          <button style={s.backBtn} onClick={() => navigate(-1)}>
            {t("backBtn")}
          </button>
        </div>
      </div>

      <div style={s.container}>
        {/* 사이드 목차 */}
        <nav style={s.toc}>
          <div style={s.tocTitle}>{t("toc.title")}</div>
          <a href="#architecture" style={s.tocItem}>{t("toc.architecture")}</a>
          <a href="#install" style={s.tocItem}>{t("toc.install")}</a>
          <a href="#env" style={s.tocItem}>{t("toc.env")}</a>
          <a href="#database" style={s.tocItem}>{t("toc.database")}</a>
          <a href="#user-mgmt" style={s.tocItem}>{t("toc.userMgmt")}</a>
          <a href="#role-system" style={s.tocItem}>{t("toc.roleSystem")}</a>
          <a href="#project-mgmt" style={s.tocItem}>{t("toc.projectMgmt")}</a>
          <a href="#file-mgmt" style={s.tocItem}>{t("toc.fileMgmt")}</a>
          <a href="#security" style={s.tocItem}>{t("toc.security")}</a>
          <a href="#api-ref" style={s.tocItem}>{t("toc.apiRef")}</a>
          <a href="#troubleshoot" style={s.tocItem}>{t("toc.troubleshoot")}</a>
          <a href="#backup" style={s.tocItem}>{t("toc.backup")}</a>
        </nav>

        <main style={s.main}>
          {/* 1. 시스템 구성 */}
          <section id="architecture" style={s.section}>
            <h1 style={s.h1}>{t("title")}</h1>
            <p style={s.updatedAt}>{t("updatedAt")}</p>

            <h2 style={s.h2}>{t("architecture.title")}</h2>
            <div style={s.archGrid}>
              <div style={s.archCard}>
                <div style={s.archTitle}>Backend</div>
                <ul style={s.archList}>
                  <li>FastAPI (Python 3.12)</li>
                  <li>SQLAlchemy 2 ORM</li>
                  <li>{t("architecture.li1")}</li>
                  <li>{t("architecture.li2")}</li>
                  <li>{t("architecture.li3")}</li>
                  <li>Uvicorn ASGI</li>
                </ul>
              </div>
              <div style={s.archCard}>
                <div style={s.archTitle}>Frontend</div>
                <ul style={s.archList}>
                  <li>React 19 + TypeScript 5.9</li>
                  <li>{t("architecture.li4")}</li>
                  <li>{t("architecture.li5")}</li>
                  <li>{t("architecture.li6")}</li>
                  <li>{t("architecture.li7")}</li>
                  <li>React Router v7</li>
                </ul>
              </div>
              <div style={s.archCard}>
                <div style={s.archTitle}>{t("architecture.infraTitle")}</div>
                <ul style={s.archList}>
                  <li>{t("architecture.li8")}</li>
                  <li>{t("architecture.li9")}</li>
                  <li>{t("architecture.li10")}</li>
                  <li>{t("architecture.li11")}</li>
                  <li>{t("architecture.li12")}</li>
                </ul>
              </div>
            </div>
          </section>

          {/* 2. 설치 및 실행 */}
          <section id="install" style={s.section}>
            <h2 style={s.h2}>{t("install.title")}</h2>

            <h3 style={s.h3}>{t("install.devTitle")}</h3>
            <div style={s.codeBlock}>
              <div style={s.codeTitle}>run_dev.bat (Windows)</div>
              <pre style={s.code}>{`# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8008

# Frontend
cd frontend
npm install
npm run dev`}</pre>
            </div>

            <h3 style={s.h3}>{t("install.macTitle")}</h3>
            <div style={s.codeBlock}>
              <div style={s.codeTitle}>run_dev.sh</div>
              <pre style={s.code}>{`bash run_dev.sh

# or manual
cd backend && python -m uvicorn main:app --reload --port 8008 &
cd frontend && npm run dev &`}</pre>
            </div>

            <h3 style={s.h3}>{t("install.prodTitle")}</h3>
            <div style={s.codeBlock}>
              <pre style={s.code}>{`# Frontend production build
cd frontend
npm run build

# TypeScript type check
npx tsc --noEmit`}</pre>
            </div>
          </section>

          {/* 3. 환경 변수 */}
          <section id="env" style={s.section}>
            <h2 style={s.h2}>{t("env.title")}</h2>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>{t("env.th1")}</th>
                  <th style={s.th}>{t("env.th2")}</th>
                  <th style={s.th}>{t("env.th3")}</th>
                  <th style={s.th}>{t("env.th4")}</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style={s.tdCode}>SECRET_KEY</td><td style={s.td}>{t("env.secretKeyDefault")}</td><td style={s.td}>{t("env.secretKeyDesc")}</td><td style={s.tdWarn}>{t("env.secretKeyRequired")}</td></tr>
                <tr><td style={s.tdCode}>ENV</td><td style={s.td}>development</td><td style={s.td}>{t("env.envDesc")}</td><td style={s.td}>{t("env.optional")}</td></tr>
                <tr><td style={s.tdCode}>DATABASE_URL</td><td style={s.td}>sqlite:///./tc_manager.db</td><td style={s.td}>{t("env.dbDesc")}</td><td style={s.td}>{t("env.optional")}</td></tr>
                <tr><td style={s.tdCode}>TOKEN_EXPIRE_HOURS</td><td style={s.td}>2</td><td style={s.td}>{t("env.tokenDesc")}</td><td style={s.td}>{t("env.optional")}</td></tr>
                <tr><td style={s.tdCode}>CORS_ORIGINS</td><td style={s.td}>http://localhost:5173, http://localhost:3000</td><td style={s.td}>{t("env.corsDesc")}</td><td style={s.td}>{t("env.optional")}</td></tr>
                <tr><td style={s.tdCode}>UPLOAD_DIR</td><td style={s.td}>./uploads</td><td style={s.td}>{t("env.uploadDesc")}</td><td style={s.td}>{t("env.optional")}</td></tr>
              </tbody>
            </table>
            <div style={s.warnBox} dangerouslySetInnerHTML={{ __html: t("env.warn1") }} />
          </section>

          {/* 4. 데이터베이스 */}
          <section id="database" style={s.section}>
            <h2 style={s.h2}>{t("database.title")}</h2>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("database.li1") }} />
              <li>{t("database.li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("database.li3") }} />
            </ul>

            <h3 style={s.h3}>{t("database.tablesTitle")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("database.th1")}</th><th style={s.th}>{t("database.th2")}</th><th style={s.th}>{t("database.th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.tdCode}>users</td><td style={s.td}>{t("database.usersDesc")}</td><td style={s.td}>{t("database.usersRel")}</td></tr>
                <tr><td style={s.tdCode}>projects</td><td style={s.td}>{t("database.projectsDesc")}</td><td style={s.td}>{t("database.projectsRel")}</td></tr>
                <tr><td style={s.tdCode}>test_cases</td><td style={s.td}>{t("database.testCasesDesc")}</td><td style={s.td}>{t("database.testCasesRel")}</td></tr>
                <tr><td style={s.tdCode}>test_runs</td><td style={s.td}>{t("database.testRunsDesc")}</td><td style={s.td}>{t("database.testRunsRel")}</td></tr>
                <tr><td style={s.tdCode}>test_results</td><td style={s.td}>{t("database.testResultsDesc")}</td><td style={s.td}>{t("database.testResultsRel")}</td></tr>
                <tr><td style={s.tdCode}>attachments</td><td style={s.td}>{t("database.attachmentsDesc")}</td><td style={s.td}>{t("database.attachmentsRel")}</td></tr>
                <tr><td style={s.tdCode}>project_members</td><td style={s.td}>{t("database.projectMembersDesc")}</td><td style={s.td}>{t("database.projectMembersRel")}</td></tr>
                <tr><td style={s.tdCode}>test_case_history</td><td style={s.td}>{t("database.testCaseHistoryDesc")}</td><td style={s.td}>{t("database.testCaseHistoryRel")}</td></tr>
                <tr><td style={s.tdCode}>test_case_sheets</td><td style={s.td}>{t("database.testCaseSheetsDesc")}</td><td style={s.td}>{t("database.testCaseSheetsRel")}</td></tr>
                <tr><td style={s.tdCode}>custom_field_defs</td><td style={s.td}>{t("database.customFieldDefsDesc")}</td><td style={s.td}>{t("database.customFieldDefsRel")}</td></tr>
                <tr><td style={s.tdCode}>test_plans</td><td style={s.td}>{t("database.testPlansDesc")}</td><td style={s.td}>{t("database.testPlansRel")}</td></tr>
                <tr><td style={s.tdCode}>saved_filters</td><td style={s.td}>{t("database.savedFiltersDesc")}</td><td style={s.td}>{t("database.savedFiltersRel")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("database.softDeleteTitle")}</h3>
            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("database.softDeleteInfo") }} />
          </section>

          {/* 5. 사용자 관리 */}
          <section id="user-mgmt" style={s.section}>
            <h2 style={s.h2}>{t("userMgmt.title")}</h2>
            <img src="/manual-images/22_admin_page.png" alt={t("userMgmt.imgAlt")} style={s.img} />

            <h3 style={s.h3}>{t("userMgmt.listTitle")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("userMgmt.li1") }} />
              <li>{t("userMgmt.li2")}</li>
            </ul>

            <h3 style={s.h3}>{t("userMgmt.roleChangeTitle")}</h3>
            <ol style={s.ol}>
              <li>{t("userMgmt.ol1")}</li>
              <li>{t("userMgmt.ol2")}</li>
              <li>{t("userMgmt.ol3")}</li>
            </ol>
            <div style={s.warnBox} dangerouslySetInnerHTML={{ __html: t("userMgmt.roleChangeWarn") }} />

            <h3 style={s.h3}>{t("userMgmt.resetPwTitle")}</h3>
            <img src="/manual-images/25_admin_page_with_reset.png" alt={t("userMgmt.resetPwImgAlt")} style={s.img} />
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("userMgmt.resetOl1") }} />
              <li>{t("userMgmt.resetOl2")}</li>
              <li>{t("userMgmt.resetOl3")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("userMgmt.resetOl4") }} />
            </ol>
            <div style={s.warnBox} dangerouslySetInnerHTML={{ __html: t("userMgmt.resetPwWarn") }} />

            <h3 style={s.h3}>{t("userMgmt.initialAccountTitle")}</h3>
            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("userMgmt.initialAccountInfo") }} />
          </section>

          {/* 6. 역할/권한 체계 */}
          <section id="role-system" style={s.section}>
            <h2 style={s.h2}>{t("roleSystem.title")}</h2>

            <h3 style={s.h3}>{t("roleSystem.systemRoleTitle")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("roleSystem.th1")}</th><th style={s.th}>{t("roleSystem.th2")}</th><th style={s.th}>{t("roleSystem.th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={{ ...s.td, color: "#CF222E", fontWeight: 700 }}>Admin</td><td style={s.td}>{t("roleSystem.adminLevel")}</td><td style={s.td}>{t("roleSystem.adminPerms")}</td></tr>
                <tr><td style={{ ...s.td, color: "#BF8700", fontWeight: 700 }}>QA Manager</td><td style={s.td}>{t("roleSystem.qaLevel")}</td><td style={s.td}>{t("roleSystem.qaPerms")}</td></tr>
                <tr><td style={{ ...s.td, color: "#6B7280", fontWeight: 700 }}>User</td><td style={s.td}>{t("roleSystem.userLevel")}</td><td style={s.td}>{t("roleSystem.userPerms")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("roleSystem.projectRoleTitle")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("roleSystem.projTh1")}</th><th style={s.th}>{t("roleSystem.projTh2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={{ ...s.td, fontWeight: 700 }}>Project Admin</td><td style={s.td}>{t("roleSystem.projAdminDesc")}</td></tr>
                <tr><td style={{ ...s.td, fontWeight: 700 }}>Project Tester</td><td style={s.td}>{t("roleSystem.projTesterDesc")}</td></tr>
              </tbody>
            </table>
            <ul style={s.ul}>
              <li>{t("roleSystem.projLi1")}</li>
              <li>{t("roleSystem.projLi2")}</li>
              <li>{t("roleSystem.projLi3")}</li>
            </ul>

            <h3 style={s.h3}>{t("roleSystem.passwordTitle")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("roleSystem.pwTh1")}</th><th style={s.th}>{t("roleSystem.pwTh2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("roleSystem.pwMinLength")}</td><td style={s.td}>{t("roleSystem.pwMinLengthVal")}</td></tr>
                <tr><td style={s.td}>{t("roleSystem.pwReuse")}</td><td style={s.td}>{t("roleSystem.pwReuseVal")}</td></tr>
                <tr><td style={s.td}>{t("roleSystem.pwForceChange")}</td><td style={s.td}>{t("roleSystem.pwForceChangeVal")}</td></tr>
                <tr><td style={s.td}>{t("roleSystem.pwTemp")}</td><td style={s.td}>{t("roleSystem.pwTempVal")}</td></tr>
              </tbody>
            </table>
          </section>

          {/* 7. 프로젝트 운영 */}
          <section id="project-mgmt" style={s.section}>
            <h2 style={s.h2}>{t("projectMgmt.title")}</h2>

            <h3 style={s.h3}>{t("projectMgmt.deleteTitle")}</h3>
            <div style={s.warnBox}>
              <span dangerouslySetInnerHTML={{ __html: t("projectMgmt.deleteWarn") }} />
              <ul style={{ margin: "8px 0 0 20px" }}>
                <li>{t("projectMgmt.deleteLi1")}</li>
                <li>{t("projectMgmt.deleteLi2")}</li>
                <li>{t("projectMgmt.deleteLi3")}</li>
                <li>{t("projectMgmt.deleteLi4")}</li>
                <li>{t("projectMgmt.deleteLi5")}</li>
              </ul>
            </div>

            <h3 style={s.h3}>{t("projectMgmt.jiraTitle")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("projectMgmt.jiraLi1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("projectMgmt.jiraLi2") }} />
              <li>{t("projectMgmt.jiraLi3")}</li>
            </ul>
          </section>

          {/* 8. 파일/첨부 관리 */}
          <section id="file-mgmt" style={s.section}>
            <h2 style={s.h2}>{t("fileMgmt.title")}</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("fileMgmt.th1")}</th><th style={s.th}>{t("fileMgmt.th2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("fileMgmt.storagePath")}</td><td style={s.td} dangerouslySetInnerHTML={{ __html: t("fileMgmt.storagePathVal") }} /></tr>
                <tr><td style={s.td}>{t("fileMgmt.fileSize")}</td><td style={s.td}>{t("fileMgmt.fileSizeVal")}</td></tr>
                <tr><td style={s.td}>{t("fileMgmt.imageExt")}</td><td style={s.td}>{t("fileMgmt.imageExtVal")}</td></tr>
                <tr><td style={s.td}>{t("fileMgmt.docExt")}</td><td style={s.td}>{t("fileMgmt.docExtVal")}</td></tr>
                <tr><td style={s.td}>{t("fileMgmt.otherExt")}</td><td style={s.td}>{t("fileMgmt.otherExtVal")}</td></tr>
                <tr><td style={s.td}>{t("fileMgmt.fileName")}</td><td style={s.td}>{t("fileMgmt.fileNameVal")}</td></tr>
                <tr><td style={s.td}>{t("fileMgmt.downloadSec")}</td><td style={s.td}>{t("fileMgmt.downloadSecVal")}</td></tr>
              </tbody>
            </table>
            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("fileMgmt.tip1") }} />
          </section>

          {/* 9. 보안 설정 */}
          <section id="security" style={s.section}>
            <h2 style={s.h2}>{t("security.title")}</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("security.th1")}</th><th style={s.th}>{t("security.th2")}</th><th style={s.th}>{t("security.th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("security.pwPolicy")}</td><td style={s.td}>{t("security.pwPolicyImpl")}</td><td style={s.td}>{t("security.pwPolicySetting")}</td></tr>
                <tr><td style={s.td}>{t("security.pwStorage")}</td><td style={s.td}>{t("security.pwStorageImpl")}</td><td style={s.td}>{t("security.pwPolicySetting")}</td></tr>
                <tr><td style={s.td}>{t("security.pwReset")}</td><td style={s.td}>{t("security.pwResetImpl")}</td><td style={s.td}>{t("security.pwResetSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.authToken")}</td><td style={s.td}>{t("security.authTokenImpl")}</td><td style={s.td}>{t("security.authTokenSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.csrf")}</td><td style={s.td}>{t("security.csrfImpl")}</td><td style={s.td}>{t("security.csrfSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.loginLimit")}</td><td style={s.td}>{t("security.loginLimitImpl")}</td><td style={s.td}>{t("security.loginLimitSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.cors")}</td><td style={s.td}>{t("security.corsImpl")}</td><td style={s.td}>{t("security.corsSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.fileUpload")}</td><td style={s.td}>{t("security.fileUploadImpl")}</td><td style={s.td}>{t("security.fileUploadSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.xss")}</td><td style={s.td}>{t("security.xssImpl")}</td><td style={s.td}>{t("security.xssSetting")}</td></tr>
                <tr><td style={s.td}>{t("security.apiAuth")}</td><td style={s.td}>{t("security.apiAuthImpl")}</td><td style={s.td}>{t("security.apiAuthSetting")}</td></tr>
              </tbody>
            </table>
          </section>

          {/* 10. API 엔드포인트 */}
          <section id="api-ref" style={s.section}>
            <h2 style={s.h2}>{t("apiRef.title")}</h2>
            <div style={s.infoBox}>
              {t("apiRef.swaggerInfo")} <a href="http://localhost:8008/docs" target="_blank" rel="noreferrer" style={{ color: "#2563EB" }}>http://localhost:8008/docs</a> {t("apiRef.swaggerInfoSuffix")}
            </div>

            {[
              { title: t("apiRef.auth.title"), endpoints: [
                ["GET", "/api/auth/check-username", t("apiRef.auth.checkUsername")],
                ["POST", "/api/auth/register", t("apiRef.auth.register")],
                ["POST", "/api/auth/login", t("apiRef.auth.login")],
                ["GET", "/api/auth/me", t("apiRef.auth.me")],
                ["PUT", "/api/auth/change-password", t("apiRef.auth.changePassword")],
                ["GET", "/api/auth/users", t("apiRef.auth.users")],
                ["PUT", "/api/auth/users/{user_id}/role", t("apiRef.auth.changeRole")],
                ["PUT", "/api/auth/users/{user_id}/reset-password", t("apiRef.auth.resetPassword")],
              ]},
              { title: t("apiRef.projects.title"), endpoints: [
                ["GET", "/api/projects", t("apiRef.projects.list")],
                ["POST", "/api/projects", t("apiRef.projects.create")],
                ["GET", "/api/projects/{id}", t("apiRef.projects.detail")],
                ["PUT", "/api/projects/{id}", t("apiRef.projects.update")],
                ["DELETE", "/api/projects/{id}", t("apiRef.projects.delete")],
              ]},
              { title: t("apiRef.testCases.title"), endpoints: [
                ["GET", "/api/projects/{id}/testcases", t("apiRef.testCases.list")],
                ["POST", "/api/projects/{id}/testcases", t("apiRef.testCases.create")],
                ["PUT", "/api/projects/{id}/testcases/{tc_id}", t("apiRef.testCases.update")],
                ["PUT", "/api/projects/{id}/testcases/bulk", t("apiRef.testCases.bulkUpdate")],
                ["DELETE", "/api/projects/{id}/testcases/{tc_id}", t("apiRef.testCases.delete")],
                ["POST", "/api/projects/{id}/testcases/{tc_id}/restore", t("apiRef.testCases.restore")],
                ["DELETE", "/api/projects/{id}/testcases/bulk?ids=1,2,3", t("apiRef.testCases.bulkDelete")],
                ["GET", "/api/projects/{id}/testcases/sheets", t("apiRef.testCases.sheets")],
                ["POST", "/api/projects/{id}/testcases/sheets", t("apiRef.testCases.sheetCreate")],
                ["DELETE", "/api/projects/{id}/testcases/sheets/{name}", t("apiRef.testCases.sheetDelete")],
                ["PUT", "/api/projects/{id}/testcases/sheets/{sheet_id}/rename", t("apiRef.testCases.sheetRename")],
                ["PUT", "/api/projects/{id}/testcases/sheets/{sheet_id}/move", t("apiRef.testCases.sheetMove")],
                ["POST", "/api/projects/{id}/testcases/import/preview", t("apiRef.testCases.importPreview")],
                ["POST", "/api/projects/{id}/testcases/import", t("apiRef.testCases.import")],
                ["GET", "/api/projects/{id}/testcases/export", t("apiRef.testCases.export")],
              ]},
              { title: t("apiRef.testRuns.title"), endpoints: [
                ["GET", "/api/projects/{id}/testruns", t("apiRef.testRuns.list")],
                ["POST", "/api/projects/{id}/testruns", t("apiRef.testRuns.create")],
                ["GET", "/api/projects/{id}/testruns/{run_id}", t("apiRef.testRuns.detail")],
                ["PUT", "/api/projects/{id}/testruns/{run_id}", t("apiRef.testRuns.update")],
                ["POST", "/api/projects/{id}/testruns/{run_id}/results", t("apiRef.testRuns.saveResults")],
                ["PUT", "/api/projects/{id}/testruns/{run_id}/complete", t("apiRef.testRuns.complete")],
                ["PUT", "/api/projects/{id}/testruns/{run_id}/reopen", t("apiRef.testRuns.reopen")],
                ["POST", "/api/projects/{id}/testruns/{run_id}/clone", t("apiRef.testRuns.clone")],
                ["DELETE", "/api/projects/{id}/testruns/{run_id}", t("apiRef.testRuns.delete")],
                ["GET", "/api/projects/{id}/testruns/{run_id}/export", t("apiRef.testRuns.export")],
              ]},
              { title: t("apiRef.dashboard.title"), endpoints: [
                ["GET", "/api/projects/{id}/dashboard/summary", t("apiRef.dashboard.summary")],
                ["GET", "/api/projects/{id}/dashboard/priority", t("apiRef.dashboard.priority")],
                ["GET", "/api/projects/{id}/dashboard/category", t("apiRef.dashboard.category")],
                ["GET", "/api/projects/{id}/dashboard/rounds", t("apiRef.dashboard.rounds")],
                ["GET", "/api/projects/{id}/dashboard/assignee", t("apiRef.dashboard.assignee")],
                ["GET", "/api/projects/{id}/dashboard/heatmap", t("apiRef.dashboard.heatmap")],
              ]},
              { title: t("apiRef.customFields.title"), endpoints: [
                ["GET", "/api/projects/{id}/custom-fields", t("apiRef.customFields.list")],
                ["POST", "/api/projects/{id}/custom-fields", t("apiRef.customFields.create")],
                ["PUT", "/api/projects/{id}/custom-fields/{field_id}", t("apiRef.customFields.update")],
                ["DELETE", "/api/projects/{id}/custom-fields/{field_id}", t("apiRef.customFields.delete")],
              ]},
              { title: t("apiRef.testPlans.title"), endpoints: [
                ["GET", "/api/projects/{id}/testplans", t("apiRef.testPlans.list")],
                ["POST", "/api/projects/{id}/testplans", t("apiRef.testPlans.create")],
                ["GET", "/api/projects/{id}/testplans/{plan_id}", t("apiRef.testPlans.detail")],
                ["PUT", "/api/projects/{id}/testplans/{plan_id}", t("apiRef.testPlans.update")],
                ["DELETE", "/api/projects/{id}/testplans/{plan_id}", t("apiRef.testPlans.delete")],
                ["GET", "/api/projects/{id}/testplans/{plan_id}/runs", t("apiRef.testPlans.runs")],
              ]},
              { title: t("apiRef.filters.title"), endpoints: [
                ["GET", "/api/projects/{id}/filters", t("apiRef.filters.list")],
                ["POST", "/api/projects/{id}/filters", t("apiRef.filters.create")],
                ["PUT", "/api/projects/{id}/filters/{filter_id}", t("apiRef.filters.update")],
                ["DELETE", "/api/projects/{id}/filters/{filter_id}", t("apiRef.filters.delete")],
                ["POST", "/api/projects/{id}/filters/apply", t("apiRef.filters.apply")],
              ]},
              { title: t("apiRef.misc.title"), endpoints: [
                ["GET", "/api/projects/{id}/reports", t("apiRef.misc.reportJson")],
                ["GET", "/api/projects/{id}/reports/pdf", t("apiRef.misc.reportPdf")],
                ["GET", "/api/projects/{id}/reports/excel", t("apiRef.misc.reportExcel")],
                ["GET", "/api/attachments/{result_id}", t("apiRef.misc.attachmentList")],
                ["POST", "/api/attachments/{result_id}", t("apiRef.misc.attachmentUpload")],
                ["GET", "/api/attachments/download/{id}", t("apiRef.misc.attachmentDownload")],
                ["DELETE", "/api/attachments/{id}", t("apiRef.misc.attachmentDelete")],
                ["GET", "/api/search?q=...", t("apiRef.misc.globalSearch")],
                ["GET", "/api/dashboard/overview", t("apiRef.misc.overview")],
              ]},
            ].map((group, gi) => (
              <div key={gi} style={{ marginBottom: 20 }}>
                <h3 style={s.h3}>{group.title}</h3>
                <table style={s.table}>
                  <thead>
                    <tr><th style={{ ...s.th, width: 70 }}>Method</th><th style={s.th}>Endpoint</th><th style={s.th}>{t("apiRef.descTh")}</th></tr>
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
            <h2 style={s.h2}>{t("troubleshoot.title")}</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("troubleshoot.th1")}</th><th style={s.th}>{t("troubleshoot.th2")}</th><th style={s.th}>{t("troubleshoot.th3")}</th></tr>
              </thead>
              <tbody>
                {([1,2,3,4,5,6,7,8,9,10,11] as const).map(n => (
                  <tr key={n}><td style={s.td}>{t(`troubleshoot.r${n}s`)}</td><td style={s.td}>{t(`troubleshoot.r${n}c`)}</td><td style={s.td}>{t(`troubleshoot.r${n}f`)}</td></tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* 12. 백업/복구 */}
          <section id="backup" style={s.section}>
            <h2 style={s.h2}>{t("backup.title")}</h2>

            <h3 style={s.h3}>{t("backup.backupTitle")}</h3>
            <div style={s.codeBlock}>
              <div style={s.codeTitle}>{t("backup.backupCodeTitle")}</div>
              <pre style={s.code}>{`# Database backup
cp backend/tc_manager.db backup/tc_manager_$(date +%Y%m%d).db

# Attachments backup
cp -r backend/uploads backup/uploads_$(date +%Y%m%d)`}</pre>
            </div>

            <h3 style={s.h3}>{t("backup.restoreTitle")}</h3>
            <div style={s.codeBlock}>
              <pre style={s.code}>{`# Database recovery
cp backup/tc_manager_20260316.db backend/tc_manager.db

# Attachments recovery
cp -r backup/uploads_20260316/* backend/uploads/

# Restart server
docker-compose restart backend`}</pre>
            </div>

            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("backup.tip1") }} />
          </section>

          <div style={s.footer}>
            <p>{t("footer")}</p>
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
