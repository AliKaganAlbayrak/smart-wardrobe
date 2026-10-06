import type { ReactNode } from "react";
import type { AuthState } from "../services/auth";

export function AuthGate({ state, children, anonymous }: { state: AuthState; children: ReactNode; anonymous: ReactNode }) {
  if (state.status === "loading") return <main className="auth-loading" role="status">Oturum kontrol ediliyor...</main>;
  return state.status === "authenticated" && state.session ? children : anonymous;
}
