import { lazy, Suspense, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { projectsApi } from "../api";
import type { Project } from "../types";
import Header from "../components/Header";
import toast from "react-hot-toast";

const TestCaseGrid = lazy(() => import("../components/TestCaseGrid"));
const TestRunManager = lazy(() => import("../components/TestRunManager"));
const Dashboard = lazy(() => import("../components/Dashboard"));
const ReportView = lazy(() => import("../components/ReportView"));
const CompareView = lazy(() => import("../components/CompareView"));
const ProjectSettings = lazy(() => import("../components/ProjectSettings"));

const TAB_KEYS = ["tc", "run", "compare", "dashboard", "report", "settings"];

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation("project");
  const [searchParams] = useSearchParams();
  const projectId = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState(searchParams.get("tab") || "tc");
  const [loaded, setLoaded] = useState(false);
  const highlightTcId = searchParams.get("highlight") || undefined;

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    projectsApi
      .getOne(projectId)
      .then((p) => { if (!cancelled) setProject(p); })
      .catch(() => { if (!cancelled) toast.error(t("projectLoadFailed")); })
      .finally(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [projectId]);

  if (!loaded) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
        <Header />
        <div style={{ textAlign: "center", padding: 80, color: "var(--text-secondary)" }}>
          {t("common:loadingData")}
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
        <Header />
        <div style={{ textAlign: "center", padding: 80, color: "var(--text-secondary)" }}>
          {t("projectNotFound")}
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-page)" }}>
      <Header />
      <div style={styles.topBar}>
        <div style={styles.titleArea}>
          <h2 style={styles.projectName}>{project.name}</h2>
          {project.description && (
            <span style={styles.projectDesc}>{project.description}</span>
          )}
        </div>
        <div style={styles.tabArea}>
          {TAB_KEYS.map((key) => (
            <button
              key={key}
              style={{
                ...styles.tabBtn,
                ...(activeTab === key ? styles.tabActive : {}),
              }}
              onClick={() => setActiveTab(key)}
            >
              {t(`tabs.${key}`)}
            </button>
          ))}
        </div>
      </div>
      <div style={activeTab === "tc" || activeTab === "run" || activeTab === "compare" ? styles.contentWide : styles.content}>
        <Suspense fallback={<div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>{t("common:loadingData")}</div>}>
          {activeTab === "tc" && <TestCaseGrid projectId={projectId} project={project} highlightTcId={highlightTcId} />}
          {activeTab === "run" && <TestRunManager projectId={projectId} project={project} />}
          {activeTab === "compare" && <CompareView projectId={projectId} />}
          {activeTab === "dashboard" && <Dashboard projectId={projectId} />}
          {activeTab === "report" && <ReportView projectId={projectId} />}
          {activeTab === "settings" && <ProjectSettings project={project} onUpdate={setProject} />}
        </Suspense>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  topBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 16px",
    borderBottom: "1px solid var(--border-color)",
    backgroundColor: "var(--bg-card)",
  },
  titleArea: {
    display: "flex",
    alignItems: "baseline",
    gap: 12,
    padding: "10px 0",
  },
  projectName: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text-primary)",
    margin: 0,
    whiteSpace: "nowrap",
  },
  projectDesc: {
    fontSize: 13,
    color: "var(--text-secondary)",
  },
  tabArea: {
    display: "flex",
    gap: 4,
  },
  tabBtn: {
    padding: "6px 16px",
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-secondary)",
    backgroundColor: "transparent",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    transition: "all 0.15s",
  },
  tabActive: {
    color: "#fff",
    backgroundColor: "var(--accent)",
    fontWeight: 600,
  },
  content: {
    maxWidth: 1400,
    margin: "0 auto",
    padding: "20px 24px",
  },
  contentWide: {
    padding: "12px 16px",
  },
};
