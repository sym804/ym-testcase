import { Component, type ReactNode, type ErrorInfo } from "react";
import i18n from "../i18n";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = "/projects";
  };

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          gap: 16,
          fontFamily: "sans-serif",
          color: "#334155",
        }}
      >
        <h2 style={{ margin: 0, fontSize: 22 }}>{i18n.t("common:errorBoundary.title")}</h2>
        <p style={{ color: "#64748B", margin: 0, maxWidth: 480, textAlign: "center" }}>
          {this.state.error?.message || i18n.t("common:errorBoundary.unknownError")}
        </p>
        <div style={{ display: "flex", gap: 12 }}>
          <button
            onClick={this.handleReload}
            style={{
              padding: "8px 20px",
              borderRadius: 6,
              border: "1px solid #cbd5e1",
              background: "#fff",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            {i18n.t("common:errorBoundary.reload")}
          </button>
          <button
            onClick={this.handleGoHome}
            style={{
              padding: "8px 20px",
              borderRadius: 6,
              border: "none",
              background: "#3b82f6",
              color: "#fff",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            {i18n.t("common:errorBoundary.goToProjects")}
          </button>
        </div>
      </div>
    );
  }
}
