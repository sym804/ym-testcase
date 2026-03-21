import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../contexts/AuthContext";
import { type ReactElement, type ReactNode } from "react";

/**
 * 테스트용 wrapper: MemoryRouter + AuthProvider
 */
function AllProviders({ children }: { children: ReactNode }) {
  return (
    <MemoryRouter>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
}

export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper"> & { route?: string }
) {
  const { route, ...rest } = options ?? {};
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={route ? [route] : undefined}>
      <AuthProvider>{children}</AuthProvider>
    </MemoryRouter>
  );
  return render(ui, { wrapper: Wrapper, ...rest });
}

export { render };
