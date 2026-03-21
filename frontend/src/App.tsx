import {} from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./contexts/AuthContext";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import ProjectListPage from "./pages/ProjectListPage";
import ProjectPage from "./pages/ProjectPage";
import AdminPage from "./pages/AdminPage";
import UserManualPage from "./pages/UserManualPage";
import AdminManualPage from "./pages/AdminManualPage";
import ChangePasswordModal from "./components/ChangePasswordModal";
import type { ReactNode } from "react";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading, mustChangePassword } = useAuth();

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
        로딩 중...
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

export default function App() {
  return (
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
  );
}
