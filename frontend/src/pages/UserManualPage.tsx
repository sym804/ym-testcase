import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTranslation } from "react-i18next";

export default function UserManualPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation("manual");

  return (
    <div style={s.page}>
      {/* 상단 바 */}
      <div style={s.topBar}>
        <div style={s.topLeft}>
          <span style={s.logo} onClick={() => navigate("/projects")}>
            YM TestCase
          </span>
          <span style={s.badge}>{t("topBar.badge")}</span>
        </div>
        <div style={s.topRight}>
          {user && <span style={s.userName}>{user.display_name}</span>}
          <button style={s.backBtn} onClick={() => navigate(-1)}>
            {t("topBar.backBtn")}
          </button>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <div style={s.container}>
        {/* 사이드 목차 */}
        <nav style={s.toc}>
          <div style={s.tocTitle}>{t("toc.title")}</div>
          <a href="#overview" style={s.tocItem}>{t("toc.overview")}</a>
          <a href="#login" style={s.tocItem}>{t("toc.login")}</a>
          <a href="#project-list" style={s.tocItem}>{t("toc.projectList")}</a>
          <a href="#project-detail" style={s.tocItem}>{t("toc.projectDetail")}</a>
          <a href="#tc-manage" style={s.tocItem}>{t("toc.tcManage")}</a>
          <a href="#sheet-tree" style={s.tocItem}>{t("toc.sheetTree")}</a>
          <a href="#import" style={s.tocItem}>{t("toc.import")}</a>
          <a href="#advanced-filter" style={s.tocItem}>{t("toc.advancedFilter")}</a>
          <a href="#testrun" style={s.tocItem}>{t("toc.testrun")}</a>
          <a href="#test-plans" style={s.tocItem}>{t("toc.testPlans")}</a>
          <a href="#compare" style={s.tocItem}>{t("toc.compare")}</a>
          <a href="#dashboard" style={s.tocItem}>{t("toc.dashboard")}</a>
          <a href="#report" style={s.tocItem}>{t("toc.report")}</a>
          <a href="#settings" style={s.tocItem}>{t("toc.settings")}</a>
          <a href="#roles" style={s.tocItem}>{t("toc.roles")}</a>
          <a href="#header" style={s.tocItem}>{t("toc.header")}</a>
          <a href="#theme" style={s.tocItem}>{t("toc.theme")}</a>
          <a href="#shortcuts" style={s.tocItem}>{t("toc.shortcuts")}</a>
        </nav>

        {/* 본문 */}
        <main style={s.main}>
          {/* 1. 개요 */}
          <section id="overview" style={s.section}>
            <h1 style={s.h1}>{t("overview.title")}</h1>
            <p style={s.updatedAt}>{t("overview.updatedAt")}</p>
            <div style={s.infoBox}>
              <span dangerouslySetInnerHTML={{ __html: t("overview.info1") }} />
              <br /><br />
              {t("overview.featuresIntro")}
              <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
                <li>{t("overview.li1")}</li>
                <li>{t("overview.li2")}</li>
                <li>{t("overview.li3")}</li>
                <li>{t("overview.li4")}</li>
                <li>{t("overview.li5")}</li>
                <li>{t("overview.li6")}</li>
                <li>{t("overview.li7")}</li>
                <li>{t("overview.li8")}</li>
                <li>{t("overview.li9")}</li>
                <li>{t("overview.li10")}</li>
                <li>{t("overview.li11")}</li>
              </ul>
            </div>
          </section>

          {/* 1. 로그인/회원가입 */}
          {/* 1. 로그인/회원가입 */}
          <section id="login" style={s.section}>
            <h2 style={s.h2}>{t("login.title")}</h2>

            <h3 style={s.h3}>{t("login.h3_login")}</h3>
            <img src="/manual-images/01_login_page.png" alt={t("login.imgAlt_login")} style={s.img} />
            <ol style={s.ol}>
              <li>{t("login.li1")}</li>
              <li>{t("login.li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("login.li3") }} />
              <li>{t("login.li4")}</li>
            </ol>
            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("login.tip1") }} />
            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("login.info1") }} />

            <h3 style={s.h3}>{t("login.h3_register")}</h3>
            <img src="/manual-images/02_register_page.png" alt={t("login.imgAlt_register")} style={s.img} />
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("login.reg_li1") }} />
              <li>{t("login.reg_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("login.reg_li3") }} />
            </ol>
            <div style={s.warnBox} dangerouslySetInnerHTML={{ __html: t("login.warn1") }} />
            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("login.info2") }} />

            <h3 style={s.h3}>{t("login.h3_password")}</h3>
            <img src="/manual-images/24_password_change_modal.png" alt={t("login.imgAlt_password")} style={s.img} />
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("login.pw_li1") }} />
              <li>{t("login.pw_li2")}</li>
              <li>{t("login.pw_li3")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("login.pw_li4") }} />
            </ol>
            <div style={s.infoBox}>
              <span dangerouslySetInnerHTML={{ __html: t("login.info3") }} />
              <br /><br />
              <img src="/manual-images/26_force_password_change.png" alt={t("login.imgAlt_forcePassword")} style={{ width: "100%", borderRadius: 8, border: "1px solid #E2E8F0" }} />
            </div>
          </section>

          {/* 1. 프로젝트 목록 */}
          {/* 1. 프로젝트 목록 */}
          <section id="project-list" style={s.section}>
            <h2 style={s.h2}>{t("projectList.title")}</h2>
            <p style={s.p}>{t("projectList.p1")}</p>

            <h3 style={s.h3}>{t("projectList.h3_overview")}</h3>
            <img src="/manual-images/04_project_list_overview.png" alt={t("projectList.imgAlt_overview")} style={s.img} />
            <div style={s.featureGrid}>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📊</div>
                <div>
                  <strong>{t("projectList.feat_summary_title")}</strong>
                  <p style={s.featureDesc}>{t("projectList.feat_summary_desc")}</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📈</div>
                <div>
                  <strong>{t("projectList.feat_progress_title")}</strong>
                  <p style={s.featureDesc}>{t("projectList.feat_progress_desc")}</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📋</div>
                <div>
                  <strong>{t("projectList.feat_table_title")}</strong>
                  <p style={s.featureDesc}>{t("projectList.feat_table_desc")}</p>
                </div>
              </div>
            </div>

            <h3 style={s.h3}>{t("projectList.h3_cards")}</h3>
            <img src="/manual-images/05_project_list_cards.png" alt={t("projectList.imgAlt_cards")} style={s.img} />
            <ul style={s.ul}>
              <li>{t("projectList.cards_li1")}</li>
              <li>{t("projectList.cards_li2")}</li>
            </ul>

            <h3 style={s.h3}>{t("projectList.h3_create")}</h3>
            <img src="/manual-images/06_project_create_modal.png" alt={t("projectList.imgAlt_create")} style={s.img} />
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("projectList.create_li1") }} />
              <li>{t("projectList.create_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("projectList.create_li3") }} />
            </ol>
            <div style={s.warnBox} dangerouslySetInnerHTML={{ __html: t("projectList.warn1") }} />

            <h3 style={s.h3}>{t("projectList.h3_bulkDelete")}</h3>
            <ul style={s.ul}>
              <li>{t("projectList.bulk_li1")}</li>
              <li>{t("projectList.bulk_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("projectList.bulk_li3") }} />
            </ul>
          </section>

          {/* 16. 헤더 */}
          {/* 2. 프로젝트 상세 */}
          <section id="project-detail" style={s.section}>
            <h2 style={s.h2}>{t("projectDetail.title")}</h2>
            <p style={s.p}>{t("projectDetail.p1")}</p>
            <img src="/manual-images/07_project_detail_tc_tab.png" alt={t("projectDetail.imgAlt")} style={s.img} />
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("projectDetail.th1")}</th><th style={s.th}>{t("projectDetail.th2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}><strong>{t("projectDetail.tab_tc")}</strong></td><td style={s.td}>{t("projectDetail.tab_tc_desc")}</td></tr>
                <tr><td style={s.td}><strong>{t("projectDetail.tab_testrun")}</strong></td><td style={s.td}>{t("projectDetail.tab_testrun_desc")}</td></tr>
                <tr><td style={s.td}><strong>{t("projectDetail.tab_compare")}</strong></td><td style={s.td}>{t("projectDetail.tab_compare_desc")}</td></tr>
                <tr><td style={s.td}><strong>{t("projectDetail.tab_dashboard")}</strong></td><td style={s.td}>{t("projectDetail.tab_dashboard_desc")}</td></tr>
                <tr><td style={s.td}><strong>{t("projectDetail.tab_report")}</strong></td><td style={s.td}>{t("projectDetail.tab_report_desc")}</td></tr>
                <tr><td style={s.td}><strong>{t("projectDetail.tab_settings")}</strong></td><td style={s.td}>{t("projectDetail.tab_settings_desc")}</td></tr>
              </tbody>
            </table>
          </section>

          {/* 16. TC 관리 */}
          {/* 16. TC 관리 */}
          <section id="tc-manage" style={s.section}>
            <h2 style={s.h2}>{t("tcManage.title")}</h2>
            <img src="/manual-images/23_tc_toolbar.png" alt={t("tcManage.imgAlt_toolbar")} style={s.img} />

            <h3 style={s.h3}>{t("tcManage.h3_toolbar")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("tcManage.th1")}</th><th style={s.th}>{t("tcManage.th2")}</th><th style={s.th}>{t("tcManage.th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("tcManage.row_addRow_btn")}</td><td style={s.td}>{t("tcManage.row_addRow_func")}</td><td style={s.td}>{t("tcManage.row_addRow_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_multiAdd_btn")}</td><td style={s.td}>{t("tcManage.row_multiAdd_func")}</td><td style={s.td}>{t("tcManage.row_multiAdd_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_clone_btn")}</td><td style={s.td}>{t("tcManage.row_clone_func")}</td><td style={s.td}>{t("tcManage.row_clone_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_delete_btn")}</td><td style={s.td}>{t("tcManage.row_delete_func")}</td><td style={s.td}>{t("tcManage.row_delete_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_undo_btn")}</td><td style={s.td}>{t("tcManage.row_undo_func")}</td><td style={s.td}>{t("tcManage.row_undo_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_autoId_btn")}</td><td style={s.td}>{t("tcManage.row_autoId_func")}</td><td style={s.td} dangerouslySetInnerHTML={{ __html: t("tcManage.row_autoId_desc") }} /></tr>
                <tr><td style={s.td}>{t("tcManage.row_bulkEdit_btn")}</td><td style={s.td}>{t("tcManage.row_bulkEdit_func")}</td><td style={s.td}>{t("tcManage.row_bulkEdit_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_import_btn")}</td><td style={s.td}>{t("tcManage.row_import_func")}</td><td style={s.td}>{t("tcManage.row_import_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_export_btn")}</td><td style={s.td}>{t("tcManage.row_export_func")}</td><td style={s.td}>{t("tcManage.row_export_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_history_btn")}</td><td style={s.td}>{t("tcManage.row_history_func")}</td><td style={s.td}>{t("tcManage.row_history_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_changelog_btn")}</td><td style={s.td}>{t("tcManage.row_changelog_func")}</td><td style={s.td}>{t("tcManage.row_changelog_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_replace_btn")}</td><td style={s.td}>{t("tcManage.row_replace_func")}</td><td style={s.td}>{t("tcManage.row_replace_desc")}</td></tr>
                <tr><td style={s.td}>{t("tcManage.row_search_btn")}</td><td style={s.td}>{t("tcManage.row_search_func")}</td><td style={s.td}>{t("tcManage.row_search_desc")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("tcManage.h3_folderSheet")}</h3>
            <p style={s.p} dangerouslySetInnerHTML={{ __html: t("tcManage.folderSheet_p1") }} />
            <div style={s.infoBox}>
              <span dangerouslySetInnerHTML={{ __html: t("tcManage.info_folderDiff") }} />
              <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
                <li dangerouslySetInnerHTML={{ __html: t("tcManage.info_folder") }} />
                <li dangerouslySetInnerHTML={{ __html: t("tcManage.info_sheet") }} />
              </ul>
            </div>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li3") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li4") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li5") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li6") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li7") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.fs_li8") }} />
            </ul>

            <h3 style={s.h3}>{t("tcManage.h3_gridEdit")}</h3>
            <img src="/manual-images/08_tc_grid_detail.png" alt={t("tcManage.imgAlt_grid")} style={s.img} />
            <ul style={s.ul}>
              <li>{t("tcManage.grid_li1")}</li>
              <li>{t("tcManage.grid_li2")}</li>
              <li>{t("tcManage.grid_li3")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.grid_li4") }} />
              <li>{t("tcManage.grid_li5")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.grid_li6") }} />
            </ul>

            <h3 style={s.h3}>{t("tcManage.h3_deleteRestore")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.dr_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.dr_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("tcManage.dr_li3") }} />
            </ul>
            <div style={s.warnBox} dangerouslySetInnerHTML={{ __html: t("tcManage.warn1") }} />

            <h3 style={s.h3}>{t("tcManage.h3_fields")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("tcManage.fields_th1")}</th><th style={s.th}>{t("tcManage.fields_th2")}</th><th style={s.th}>{t("tcManage.fields_th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>No</td><td style={s.td}>{t("tcManage.field_no")}</td><td style={s.td}>{t("tcManage.field_no_ex")}</td></tr>
                <tr><td style={s.td}>TC ID</td><td style={s.td}>{t("tcManage.field_tcid")}</td><td style={s.td}>{t("tcManage.field_tcid_ex")}</td></tr>
                <tr><td style={s.td}>Type</td><td style={s.td}>{t("tcManage.field_type")}</td><td style={s.td}>{t("tcManage.field_type_ex")}</td></tr>
                <tr><td style={s.td}>Category</td><td style={s.td}>{t("tcManage.field_category")}</td><td style={s.td}>{t("tcManage.field_category_ex")}</td></tr>
                <tr><td style={s.td}>Depth 1</td><td style={s.td}>{t("tcManage.field_depth1")}</td><td style={s.td}>{t("tcManage.field_depth1_ex")}</td></tr>
                <tr><td style={s.td}>Depth 2</td><td style={s.td}>{t("tcManage.field_depth2")}</td><td style={s.td}>{t("tcManage.field_depth2_ex")}</td></tr>
                <tr><td style={s.td}>Priority</td><td style={s.td}>{t("tcManage.field_priority")}</td><td style={s.td}>{t("tcManage.field_priority_ex")}</td></tr>
                <tr><td style={s.td}>Platform</td><td style={s.td}>{t("tcManage.field_platform")}</td><td style={s.td}>{t("tcManage.field_platform_ex")}</td></tr>
                <tr><td style={s.td}>Precondition</td><td style={s.td}>{t("tcManage.field_precondition")}</td><td style={s.td}>{t("tcManage.field_precondition_ex")}</td></tr>
                <tr><td style={s.td}>Test Steps</td><td style={s.td}>{t("tcManage.field_steps")}</td><td style={s.td}>{t("tcManage.field_steps_ex")}</td></tr>
                <tr><td style={s.td}>Expected Result</td><td style={s.td}>{t("tcManage.field_expected")}</td><td style={s.td}>{t("tcManage.field_expected_ex")}</td></tr>
                <tr><td style={s.td}>Issue Link</td><td style={s.td}>{t("tcManage.field_issueLink")}</td><td style={s.td}>{t("tcManage.field_issueLink_ex")}</td></tr>
                <tr><td style={s.td}>Assignee</td><td style={s.td}>{t("tcManage.field_assignee")}</td><td style={s.td}>{t("tcManage.field_assignee_ex")}</td></tr>
                <tr><td style={s.td}>Remarks</td><td style={s.td}>{t("tcManage.field_remarks")}</td><td style={s.td}>{t("tcManage.field_remarks_ex")}</td></tr>
              </tbody>
            </table>
          </section>

          {/* 17. 테스트 수행 */}
          {/* 5. 폴더/시트 트리 구조 (VS Code 스타일 사이드바) */}
          <section id="sheet-tree" style={s.section}>
            <h2 style={s.h2}>{t("sheetTree.title")}</h2>
            <img src="/manual-images/30_sheet_tree_tabs.png" alt={t("sheetTree.imgAlt")} style={s.img} />
            <p style={s.p} dangerouslySetInnerHTML={{ __html: t("sheetTree.p1") }} />

            <h3 style={s.h3}>{t("sheetTree.h3_diff")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("sheetTree.th1")}</th><th style={s.th}>{t("sheetTree.th2")}</th><th style={s.th}>{t("sheetTree.th3")}</th><th style={s.th}>{t("sheetTree.th4")}</th><th style={s.th}>{t("sheetTree.th5")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("sheetTree.folder_name")}</td><td style={s.td}>{t("sheetTree.folder_icon")}</td><td style={s.td}>{t("sheetTree.folder_role")}</td><td style={s.td}>{t("sheetTree.folder_tc")}</td><td style={s.td}>{t("sheetTree.folder_children")}</td></tr>
                <tr><td style={s.td}>{t("sheetTree.sheet_name")}</td><td style={s.td}>{t("sheetTree.sheet_icon")}</td><td style={s.td}>{t("sheetTree.sheet_role")}</td><td style={s.td}>{t("sheetTree.sheet_tc")}</td><td style={s.td}>{t("sheetTree.sheet_children")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("sheetTree.h3_sidebar")}</h3>
            <ul style={s.ul}>
              <li>{t("sheetTree.sb_li1")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.sb_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.sb_li3") }} />
              <li>{t("sheetTree.sb_li4")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.sb_li5") }} />
            </ul>

            <h3 style={s.h3}>{t("sheetTree.h3_add")}</h3>
            <img src="/manual-images/31_sheet_tree_add_child.png" alt={t("sheetTree.imgAlt_add")} style={s.img} />
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.add_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.add_li2") }} />
              <li>{t("sheetTree.add_li3")}</li>
              <li>{t("sheetTree.add_li4")}</li>
            </ul>

            <h3 style={s.h3}>{t("sheetTree.h3_delete")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.del_li1") }} />
              <li>{t("sheetTree.del_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("sheetTree.del_li3") }} />
            </ul>

            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("sheetTree.info1") }} />
          </section>


          {/* 18. 테스트 플랜 */}
          {/* 17. CSV Import */}
          <section id="import" style={s.section}>
            <h2 style={s.h2}>{t("import.title")}</h2>
            <img src="/manual-images/34_tc_toolbar_with_filter.png" alt={t("import.imgAlt")} style={s.img} />
            <p style={s.p}>{t("import.p1")}</p>

            <h3 style={s.h3}>{t("import.h3_usage")}</h3>
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("import.usage_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("import.usage_li2") }} />
              <li>{t("import.usage_li3")}</li>
            </ol>

            <h3 style={s.h3}>{t("import.h3_jiraMapping")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("import.jira_th1")}</th><th style={s.th}>{t("import.jira_th2")}</th></tr>
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

            <h3 style={s.h3}>{t("import.h3_encoding")}</h3>
            <ul style={s.ul}>
              <li>{t("import.enc_li1")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("import.enc_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("import.enc_li3") }} />
            </ul>

            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("import.tip1") }} />
          </section>

          {/* 7-1. Markdown Import */}
          {/* 7-1. Markdown Import */}
          <section id="md-import" style={s.section}>
            <h2 style={s.h2}>{t("mdImport.title")}</h2>
            <p style={s.p}>{t("mdImport.p1")}</p>

            <h3 style={s.h3}>{t("mdImport.h3_usage")}</h3>
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("mdImport.usage_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("mdImport.usage_li2") }} />
              <li>{t("mdImport.usage_li3")}</li>
              <li>{t("mdImport.usage_li4")}</li>
            </ol>

            <h3 style={s.h3}>{t("mdImport.h3_format")}</h3>
            <p style={s.p} dangerouslySetInnerHTML={{ __html: t("mdImport.format_p1") }} />
            <pre style={{...s.p, backgroundColor: "var(--bg-secondary)", padding: "16px", borderRadius: "8px", fontFamily: "monospace", fontSize: "13px", whiteSpace: "pre", overflowX: "auto"}}>{t("mdImport.format_example")}</pre>

            <h3 style={s.h3}>{t("mdImport.h3_sheetName")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("mdImport.sn_li1") }} />
              <li>{t("mdImport.sn_li2")}</li>
              <li>{t("mdImport.sn_li3")}</li>
              <li>{t("mdImport.sn_li4")}</li>
            </ul>

            <h3 style={s.h3}>{t("mdImport.h3_headerMapping")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("mdImport.hm_th1")}</th><th style={s.th}>{t("mdImport.hm_th2")}</th></tr>
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
            <p style={s.p}>{t("mdImport.hm_p1")}</p>

            <h3 style={s.h3}>{t("mdImport.h3_notes")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("mdImport.notes_li1") }} />
              <li>{t("mdImport.notes_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("mdImport.notes_li3") }} />
              <li>{t("mdImport.notes_li4")}</li>
              <li>{t("mdImport.notes_li5")}</li>
            </ul>

            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("mdImport.tip1") }} />
          </section>

          {/* 15. 고급 필터 */}
          {/* 15. 고급 필터 */}
          <section id="advanced-filter" style={s.section}>
            <h2 style={s.h2}>{t("advancedFilter.title")}</h2>
            <img src="/manual-images/33_advanced_filter_panel.png" alt={t("advancedFilter.imgAlt")} style={s.img} />
            <p style={s.p}>{t("advancedFilter.p1")}</p>

            <h3 style={s.h3}>{t("advancedFilter.h3_open")}</h3>
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("advancedFilter.open_li1") }} />
              <li>{t("advancedFilter.open_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("advancedFilter.open_li3") }} />
            </ol>

            <h3 style={s.h3}>{t("advancedFilter.h3_conditions")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("advancedFilter.cond_th1")}</th><th style={s.th}>{t("advancedFilter.cond_th2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("advancedFilter.cond_field")}</td><td style={s.td}>{t("advancedFilter.cond_field_desc")}</td></tr>
                <tr><td style={s.td}>{t("advancedFilter.cond_operator")}</td><td style={s.td}>{t("advancedFilter.cond_operator_desc")}</td></tr>
                <tr><td style={s.td}>{t("advancedFilter.cond_value")}</td><td style={s.td}>{t("advancedFilter.cond_value_desc")}</td></tr>
                <tr><td style={s.td}>{t("advancedFilter.cond_logic")}</td><td style={s.td} dangerouslySetInnerHTML={{ __html: t("advancedFilter.cond_logic_desc") }} /></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("advancedFilter.h3_saveLoad")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("advancedFilter.sl_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("advancedFilter.sl_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("advancedFilter.sl_li3") }} />
            </ul>

            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("advancedFilter.tip1") }} />
          </section>
          {/* 17. 테스트 수행 */}
          <section id="testrun" style={s.section}>
            <h2 style={s.h2}>{t("testrun.title")}</h2>
            <img src="/manual-images/09_testrun_tab.png" alt={t("testrun.imgAlt")} style={s.img} />

            <h3 style={s.h3}>{t("testrun.h3_create")}</h3>
            <ol style={s.ol}>
              <li dangerouslySetInnerHTML={{ __html: t("testrun.create_li1") }} />
              <li>{t("testrun.create_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("testrun.create_li3") }} />
            </ol>

            <h3 style={s.h3}>{t("testrun.h3_list")}</h3>
            <ul style={s.ul}>
              <li>{t("testrun.list_li1")}</li>
              <li>{t("testrun.list_li2")}</li>
              <li>{t("testrun.list_li3")}</li>
            </ul>

            <h3 style={s.h3}>{t("testrun.h3_result")}</h3>
            <div style={s.featureGrid}>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>🖱️</div>
                <div>
                  <strong>{t("testrun.feat_mouse_title")}</strong>
                  <p style={s.featureDesc}>{t("testrun.feat_mouse_desc")}</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>⌨️</div>
                <div>
                  <strong>{t("testrun.feat_keyboard_title")}</strong>
                  <p style={s.featureDesc}>{t("testrun.feat_keyboard_desc")}</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>📋</div>
                <div>
                  <strong>{t("testrun.feat_fill_title")}</strong>
                  <p style={s.featureDesc}>{t("testrun.feat_fill_desc")}</p>
                </div>
              </div>
              <div style={s.featureCard}>
                <div style={s.featureIcon}>↩️</div>
                <div>
                  <strong>{t("testrun.feat_undo_title")}</strong>
                  <p style={s.featureDesc}>{t("testrun.feat_undo_desc")}</p>
                </div>
              </div>
            </div>

            <h3 style={s.h3}>{t("testrun.h3_attachment")}</h3>
            <ul style={s.ul}>
              <li>{t("testrun.att_li1")}</li>
              <li>{t("testrun.att_li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("testrun.att_li3") }} />
              <li>{t("testrun.att_li4")}</li>
            </ul>

            <h3 style={s.h3}>{t("testrun.h3_runManage")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("testrun.rm_th1")}</th><th style={s.th}>{t("testrun.rm_th2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("testrun.rm_complete")}</td><td style={s.td}>{t("testrun.rm_complete_desc")}</td></tr>
                <tr><td style={s.td}>{t("testrun.rm_reopen")}</td><td style={s.td}>{t("testrun.rm_reopen_desc")}</td></tr>
                <tr><td style={s.td}>{t("testrun.rm_clone")}</td><td style={s.td}>{t("testrun.rm_clone_desc")}</td></tr>
                <tr><td style={s.td}>{t("testrun.rm_delete")}</td><td style={s.td}>{t("testrun.rm_delete_desc")}</td></tr>
                <tr><td style={s.td}>{t("testrun.rm_export")}</td><td style={s.td}>{t("testrun.rm_export_desc")}</td></tr>
              </tbody>
            </table>
            <h3 style={s.h3}>{t("testrun.h3_timer")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("testrun.timer_li1") }} />
              <li>{t("testrun.timer_li2")}</li>
              <li>{t("testrun.timer_li3")}</li>
            </ul>
            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("testrun.tip1") }} />
          </section>

          {/* 15. 비교 */}
          {/* 18. 테스트 플랜 */}
          <section id="test-plans" style={s.section}>
            <h2 style={s.h2}>{t("testPlans.title")}</h2>
            <img src="/manual-images/35_dashboard_with_plan.png" alt={t("testPlans.imgAlt")} style={s.img} />
            <p style={s.p}>{t("testPlans.p1")}</p>

            <h3 style={s.h3}>{t("testPlans.h3_create")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("testPlans.create_li1") }} />
              <li>{t("testPlans.create_li2")}</li>
            </ul>

            <h3 style={s.h3}>{t("testPlans.h3_link")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("testPlans.link_li1") }} />
              <li>{t("testPlans.link_li2")}</li>
            </ul>

            <h3 style={s.h3}>{t("testPlans.h3_progress")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("testPlans.progress_li1") }} />
              <li>{t("testPlans.progress_li2")}</li>
            </ul>

            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("testPlans.info1") }} />
          </section>

          {/* 17. CSV Import */}
          {/* 15. 비교 */}
          <section id="compare" style={s.section}>
            <h2 style={s.h2}>{t("compare.title")}</h2>
            <img src="/manual-images/12_compare_tab.png" alt={t("compare.imgAlt")} style={s.img} />
            <p style={s.p}>{t("compare.p1")}</p>
            <ol style={s.ol}>
              <li>{t("compare.li1")}</li>
              <li>{t("compare.li2")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("compare.li3") }} />
            </ol>
            <div style={s.infoBox} dangerouslySetInnerHTML={{ __html: t("compare.info1") }} />
          </section>

          {/* 17. 대시보드 */}
          {/* 17. 대시보드 */}
          <section id="dashboard" style={s.section}>
            <h2 style={s.h2}>{t("dashboard.title")}</h2>
            <img src="/manual-images/13_dashboard_top.png" alt={t("dashboard.imgAlt_top")} style={s.img} />
            <p style={s.p}>{t("dashboard.p1")}</p>

            <h3 style={s.h3}>{t("dashboard.h3_summary")}</h3>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.sum_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.sum_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.sum_li3") }} />
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.sum_li4") }} />
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.sum_li5") }} />
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.sum_li6") }} />
            </ul>

            <h3 style={s.h3}>{t("dashboard.h3_charts")}</h3>
            <img src="/manual-images/14_dashboard_charts.png" alt={t("dashboard.imgAlt_charts")} style={s.img} />
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("dashboard.chart_th1")}</th><th style={s.th}>{t("dashboard.chart_th2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("dashboard.chart_donut")}</td><td style={s.td}>{t("dashboard.chart_donut_desc")}</td></tr>
                <tr><td style={s.td}>{t("dashboard.chart_bar")}</td><td style={s.td}>{t("dashboard.chart_bar_desc")}</td></tr>
                <tr><td style={s.td}>{t("dashboard.chart_priority")}</td><td style={s.td}>{t("dashboard.chart_priority_desc")}</td></tr>
                <tr><td style={s.td}>{t("dashboard.chart_category")}</td><td style={s.td}>{t("dashboard.chart_category_desc")}</td></tr>
                <tr><td style={s.td}>{t("dashboard.chart_assignee")}</td><td style={s.td}>{t("dashboard.chart_assignee_desc")}</td></tr>
                <tr><td style={s.td}>{t("dashboard.chart_heatmap")}</td><td style={s.td}>{t("dashboard.chart_heatmap_desc")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("dashboard.h3_dateFilter")}</h3>
            <p style={s.p}>{t("dashboard.df_p1")}</p>
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.df_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("dashboard.df_li2") }} />
              <li>{t("dashboard.df_li3")}</li>
              <li>{t("dashboard.df_li4")}</li>
            </ul>
          </section>

          {/* 18. 리포트 */}
          {/* 18. 리포트 */}
          <section id="report" style={s.section}>
            <h2 style={s.h2}>{t("report.title")}</h2>
            <img src="/manual-images/16_report_tab.png" alt={t("report.imgAlt")} style={s.img} />
            <p style={s.p}>{t("report.p1")}</p>
            <ol style={s.ol}>
              <li>{t("report.li1")}</li>
              <li>{t("report.li2")}</li>
              <li>{t("report.li3")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("report.li4") }} />
              <li dangerouslySetInnerHTML={{ __html: t("report.li5") }} />
            </ol>
          </section>

          {/* 15. 설정 */}
          {/* 15. 설정 */}
          <section id="settings" style={s.section}>
            <h2 style={s.h2}>{t("settings.title")}</h2>
            <img src="/manual-images/17_settings_tab.png" alt={t("settings.imgAlt")} style={s.img} />

            <h3 style={s.h3}>{t("settings.h3_projectInfo")}</h3>
            <ul style={s.ul}>
              <li>{t("settings.pi_li1")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("settings.pi_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("settings.pi_li3") }} />
            </ul>

            <h3 style={s.h3}>{t("settings.h3_defaultFields")}</h3>
            <p style={s.p} dangerouslySetInnerHTML={{ __html: t("settings.df_p1") }} />
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("settings.df_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("settings.df_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("settings.df_li3") }} />
              <li dangerouslySetInnerHTML={{ __html: t("settings.df_li4") }} />
              <li>{t("settings.df_li5")}</li>
            </ul>

          {/* 16. 커스텀 필드 */}
          {/* 16. 커스텀 필드 */}
          <div id="custom-fields">
            <h3 style={s.h3}>{t("settings.h3_customFields")}</h3>
            <img src="/manual-images/32_custom_fields_grid.png" alt={t("settings.imgAlt_customFields")} style={s.img} />
            <p style={s.p}>{t("settings.cf_p1")}</p>

            <p style={{...s.p, fontWeight: 700, marginTop: 16}}>{t("settings.cf_fieldTypes")}</p>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("settings.cf_th1")}</th><th style={s.th}>{t("settings.cf_th2")}</th><th style={s.th}>{t("settings.cf_th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>text</td><td style={s.td}>{t("settings.cf_text")}</td><td style={s.td}>{t("settings.cf_text_ex")}</td></tr>
                <tr><td style={s.td}>number</td><td style={s.td}>{t("settings.cf_number")}</td><td style={s.td}>{t("settings.cf_number_ex")}</td></tr>
                <tr><td style={s.td}>select</td><td style={s.td}>{t("settings.cf_select")}</td><td style={s.td}>{t("settings.cf_select_ex")}</td></tr>
                <tr><td style={s.td}>multiselect</td><td style={s.td}>{t("settings.cf_multiselect")}</td><td style={s.td}>{t("settings.cf_multiselect_ex")}</td></tr>
                <tr><td style={s.td}>checkbox</td><td style={s.td}>{t("settings.cf_checkbox")}</td><td style={s.td}>{t("settings.cf_checkbox_ex")}</td></tr>
                <tr><td style={s.td}>date</td><td style={s.td}>{t("settings.cf_date")}</td><td style={s.td}>{t("settings.cf_date_ex")}</td></tr>
              </tbody>
            </table>

            <p style={{...s.p, fontWeight: 700, marginTop: 16}}>{t("settings.cf_management")}</p>
            <img src="/manual-images/32_custom_fields_grid.png" alt={t("settings.imgAlt_cfSettings")} style={s.img} />
            <ul style={s.ul}>
              <li dangerouslySetInnerHTML={{ __html: t("settings.cf_mgmt_li1") }} />
              <li dangerouslySetInnerHTML={{ __html: t("settings.cf_mgmt_li2") }} />
              <li dangerouslySetInnerHTML={{ __html: t("settings.cf_mgmt_li3") }} />
              <li>{t("settings.cf_mgmt_li4")}</li>
              <li>{t("settings.cf_mgmt_li5")}</li>
            </ul>

            <div style={s.tipBox} dangerouslySetInnerHTML={{ __html: t("settings.tip1") }} />
          </div>


            <h3 style={s.h3}>{t("settings.h3_members")}</h3>
            <img src="/manual-images/18_settings_members.png" alt={t("settings.imgAlt_members")} style={s.img} />
            <ul style={s.ul}>
              <li>{t("settings.mem_li1")}</li>
              <li dangerouslySetInnerHTML={{ __html: t("settings.mem_li2") }} />
              <li>{t("settings.mem_li3")}</li>
            </ul>
          </section>

          {/* 17. 테마 */}
          {/* 5. 역할별 권한 */}
          <section id="roles" style={s.section}>
            <h2 style={s.h2}>{t("roles.title")}</h2>

            <h3 style={s.h3}>{t("roles.h3_systemRoles")}</h3>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>{t("roles.th_feature")}</th>
                  <th style={{ ...s.th, backgroundColor: "#CF222E", color: "#fff" }}>{t("roles.th_admin")}</th>
                  <th style={{ ...s.th, backgroundColor: "#BF8700", color: "#fff" }}>{t("roles.th_qaManager")}</th>
                  <th style={{ ...s.th, backgroundColor: "#6B7280", color: "#fff" }}>{t("roles.th_user")}</th>
                </tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("roles.role_createProject")}</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>{t("roles.role_manageUsers")}</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>{t("roles.role_resetPassword")}</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>{t("roles.role_viewUsers")}</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.tdX}>X</td></tr>
                <tr><td style={s.td}>{t("roles.role_tcCrud")}</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>{t("roles.role_tcCrud_user")}</td></tr>
                <tr><td style={s.td}>{t("roles.role_testResult")}</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>{t("roles.role_testResult_user")}</td></tr>
                <tr><td style={s.td}>{t("roles.role_dashboard")}</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>{t("roles.role_dashboard_user")}</td></tr>
                <tr><td style={s.td}>{t("roles.role_download")}</td><td style={s.tdCheck}>O</td><td style={s.tdCheck}>O</td><td style={s.td}>{t("roles.role_download_user")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("roles.h3_accessRules")}</h3>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("roles.access_th1")}</th><th style={s.th}>{t("roles.access_th2")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.td}>{t("roles.access_public")}</td><td style={s.td}>{t("roles.access_public_desc")}</td></tr>
                <tr><td style={s.td}>{t("roles.access_private")}</td><td style={s.td}>{t("roles.access_private_desc")}</td></tr>
                <tr><td style={s.td}>-</td><td style={s.td}>{t("roles.access_admin_desc")}</td></tr>
              </tbody>
            </table>

            <h3 style={s.h3}>{t("roles.h3_dualRoles")}</h3>
            <div style={s.infoBox}>
              <span dangerouslySetInnerHTML={{ __html: t("roles.info1") }} />
              <ul style={{ margin: "8px 0 0 20px", lineHeight: 1.8 }}>
                <li dangerouslySetInnerHTML={{ __html: t("roles.dual_li1") }} />
                <li dangerouslySetInnerHTML={{ __html: t("roles.dual_li2") }} />
                <li dangerouslySetInnerHTML={{ __html: t("roles.dual_li3") }} />
                <li dangerouslySetInnerHTML={{ __html: t("roles.dual_li4") }} />
                <li dangerouslySetInnerHTML={{ __html: t("roles.dual_li5") }} />
              </ul>
            </div>
          </section>

          {/* 5. 폴더/시트 트리 구조 (VS Code 스타일 사이드바) */}
          {/* 16. 헤더 */}
          <section id="header" style={s.section}>
            <h2 style={s.h2}>{t("header.title")}</h2>
            <img src="/manual-images/19_global_search.png" alt={t("header.imgAlt")} style={s.img} />

            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>{t("header.th1")}</th>
                  <th style={s.th}>{t("header.th2")}</th>
                  <th style={s.th}>{t("header.th3")}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={s.td}>{t("header.row_logo_area")}</td>
                  <td style={s.td}>{t("header.row_logo_func")}</td>
                  <td style={s.td}>{t("header.row_logo_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_selector_area")}</td>
                  <td style={s.td}>{t("header.row_selector_func")}</td>
                  <td style={s.td}>{t("header.row_selector_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_search_area")}</td>
                  <td style={s.td}>{t("header.row_search_func")}</td>
                  <td style={s.td}>{t("header.row_search_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_notification_area")}</td>
                  <td style={s.td}>{t("header.row_notification_func")}</td>
                  <td style={s.td}>{t("header.row_notification_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_theme_area")}</td>
                  <td style={s.td}>{t("header.row_theme_func")}</td>
                  <td style={s.td}>{t("header.row_theme_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_admin_area")}</td>
                  <td style={s.td}>{t("header.row_admin_func")}</td>
                  <td style={s.td}>{t("header.row_admin_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_user_area")}</td>
                  <td style={s.td}>{t("header.row_user_func")}</td>
                  <td style={s.td}>{t("header.row_user_desc")}</td>
                </tr>
                <tr>
                  <td style={s.td}>{t("header.row_logout_area")}</td>
                  <td style={s.td}>{t("header.row_logout_func")}</td>
                  <td style={s.td}>{t("header.row_logout_desc")}</td>
                </tr>
              </tbody>
            </table>
          </section>

          {/* 2. 프로젝트 상세 */}
          {/* 17. 테마 */}
          <section id="theme" style={s.section}>
            <h2 style={s.h2}>{t("theme.title")}</h2>
            <img src="/manual-images/20_dark_mode_project.png" alt={t("theme.imgAlt_project")} style={s.img} />
            <p style={s.p}>{t("theme.p1")}</p>
            <img src="/manual-images/21_dark_mode_dashboard.png" alt={t("theme.imgAlt_dashboard")} style={s.img} />
            <ul style={s.ul}>
              <li>{t("theme.li1")}</li>
              <li>{t("theme.li2")}</li>
            </ul>
          </section>

          {/* 18. 단축키 */}
          {/* 18. 단축키 */}
          <section id="shortcuts" style={s.section}>
            <h2 style={s.h2}>{t("shortcuts.title")}</h2>
            <table style={s.table}>
              <thead>
                <tr><th style={s.th}>{t("shortcuts.th1")}</th><th style={s.th}>{t("shortcuts.th2")}</th><th style={s.th}>{t("shortcuts.th3")}</th></tr>
              </thead>
              <tbody>
                <tr><td style={s.tdCode}>P</td><td style={s.td}>{t("shortcuts.key_p")}</td><td style={s.td}>{t("shortcuts.key_p_loc")}</td></tr>
                <tr><td style={s.tdCode}>F</td><td style={s.td}>{t("shortcuts.key_f")}</td><td style={s.td}>{t("shortcuts.key_f_loc")}</td></tr>
                <tr><td style={s.tdCode}>B</td><td style={s.td}>{t("shortcuts.key_b")}</td><td style={s.td}>{t("shortcuts.key_b_loc")}</td></tr>
                <tr><td style={s.tdCode}>N</td><td style={s.td}>{t("shortcuts.key_n")}</td><td style={s.td}>{t("shortcuts.key_n_loc")}</td></tr>
                <tr><td style={s.tdCode}>Ctrl + Z</td><td style={s.td}>{t("shortcuts.key_undo")}</td><td style={s.td}>{t("shortcuts.key_undo_loc")}</td></tr>
                <tr><td style={s.tdCode}>Ctrl + Shift + Z</td><td style={s.td}>{t("shortcuts.key_redo")}</td><td style={s.td}>{t("shortcuts.key_redo_loc")}</td></tr>
                <tr><td style={s.tdCode}>Ctrl + D</td><td style={s.td}>{t("shortcuts.key_fillDown")}</td><td style={s.td}>{t("shortcuts.key_fillDown_loc")}</td></tr>
                <tr><td style={s.tdCode}>Shift + Click</td><td style={s.td}>{t("shortcuts.key_rangeSelect")}</td><td style={s.td}>{t("shortcuts.key_rangeSelect_loc")}</td></tr>
                <tr><td style={s.tdCode}>Ctrl + C / V</td><td style={s.td}>{t("shortcuts.key_copyPaste")}</td><td style={s.td}>{t("shortcuts.key_copyPaste_loc")}</td></tr>
                <tr><td style={s.tdCode}>Enter</td><td style={s.td}>{t("shortcuts.key_enter")}</td><td style={s.td}>{t("shortcuts.key_enter_loc")}</td></tr>
                <tr><td style={s.tdCode}>Escape</td><td style={s.td}>{t("shortcuts.key_escape")}</td><td style={s.td}>{t("shortcuts.key_escape_loc")}</td></tr>
              </tbody>
            </table>
          </section>

          {/* 5. 역할별 권한 */}

          {user?.role === "admin" && (
            <div style={s.adminLinkBox}>
              <span style={{ marginRight: 8 }}>{t("adminLink.question")}</span>
              <span
                style={s.adminLink}
                onClick={() => navigate("/admin-manual")}
              >
                {t("adminLink.link")}
              </span>
            </div>
          )}

          <div style={s.footer}>
            <p>{t("footer.text")}</p>
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
