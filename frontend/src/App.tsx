import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "./contexts/AuthContext";
import LoginPage from "./pages/LoginPage";
import ChangePasswordModal from "./components/ChangePasswordModal";
import type { ReactNode } from "react";

// Lazy-loaded pages
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const ProjectListPage = lazy(() => import("./pages/ProjectListPage"));
const ProjectPage = lazy(() => import("./pages/ProjectPage"));
const AdminPage = lazy(() => import("./pages/AdminPage"));
const UserManualPage = lazy(() => import("./pages/UserManualPage"));
const AdminManualPage = lazy(() => import("./pages/AdminManualPage"));

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading, mustChangePassword } = useAuth();
  const { t } = useTranslation("common");

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
          color: "#64748B",
          fontSize: 16,
        }}
      >
        {t("loading")}
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (mustChangePassword) {
    return <ChangePasswordModal />;
  }

  return <>{children}</>;
}

function PageLoader() {
  const { t } = useTranslation("common");
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh", color: "#64748B", fontSize: 16 }}>
      {t("loading")}
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route
        path="/projects"
        element={
          <ProtectedRoute>
            <ProjectListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/projects/:id"
        element={
          <ProtectedRoute>
            <ProjectPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/manual"
        element={
          <ProtectedRoute>
            <UserManualPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin-manual"
        element={
          <ProtectedRoute>
            <AdminManualPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/projects" replace />} />
    </Routes>
    </Suspense>
  );
}
