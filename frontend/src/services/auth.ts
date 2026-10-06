import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export type AuthStatus = "loading" | "anonymous" | "authenticated" | "configuration_error";
export interface AuthState { status: AuthStatus; session: Session | null; error: string | null }

export function authErrorMessage(code?: string): string {
  const messages: Record<string, string> = {
    invalid_credentials: "E-posta veya şifre yanlış.",
    email_not_confirmed: "Giriş yapmadan önce e-postanızı doğrulayın.",
    user_already_exists: "Bu e-posta adresiyle kayıtlı bir hesap bulunuyor.",
    weak_password: "Daha güçlü, en az 8 karakterli bir şifre kullanın.",
    over_email_send_rate_limit: "Çok fazla e-posta isteği gönderildi. Biraz sonra tekrar deneyin.",
    over_request_rate_limit: "Çok fazla deneme yapıldı. Biraz sonra tekrar deneyin.",
    signup_disabled: "Yeni hesap kaydı şu anda kullanılamıyor.",
  };
  return messages[code || ""] || "İşlem tamamlanamadı. Bağlantınızı kontrol edip tekrar deneyin.";
}

export class AuthStore {
  private state: AuthState = { status: "loading", session: null, error: null };
  private listeners = new Set<() => void>();
  private started: Promise<void> | null = null;
  private refresh: Promise<string | null> | null = null;
  private unsubscribe: (() => void) | null = null;
  private revision = 0;

  constructor(private client: SupabaseClient | null) {}
  getSnapshot = (): AuthState => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private setSession(session: Session | null, error: string | null = null) {
    this.revision++;
    this.state = { status: session ? "authenticated" : "anonymous", session, error };
    this.listeners.forEach((listener) => listener());
  }
  start(): Promise<void> {
    if (this.started) return this.started;
    this.started = this.initialize();
    return this.started;
  }
  private async initialize() {
    if (!this.client) {
      this.state = { status: "configuration_error", session: null,
        error: "Giriş hizmeti henüz yapılandırılmamış. Lütfen daha sonra tekrar deneyin." };
      this.listeners.forEach((listener) => listener());
      return;
    }
    // Keep this callback synchronous: awaiting other auth methods here can deadlock the SDK lock.
    const { data: { subscription } } = this.client.auth.onAuthStateChange((_event, session) => this.setSession(session));
    this.unsubscribe = () => subscription.unsubscribe();
    const revision = this.revision;
    try {
      const { data, error } = await this.client.auth.getSession();
      if (this.revision === revision) this.setSession(error ? null : data.session, error ? authErrorMessage(error.code) : null);
    } catch {
      if (this.revision === revision) this.setSession(null, authErrorMessage());
    }
  }
  async login(email: string, password: string) {
    if (!this.client) throw new Error("Giriş hizmeti henüz yapılandırılmamış.");
    const { data, error } = await this.client.auth.signInWithPassword({ email: email.trim(), password });
    if (error) throw new Error(authErrorMessage(error.code));
    this.setSession(data.session);
  }
  async register(email: string, password: string, redirectTo: string): Promise<boolean> {
    if (!this.client) throw new Error("Giriş hizmeti henüz yapılandırılmamış.");
    const { data, error } = await this.client.auth.signUp({ email: email.trim(), password,
      options: { emailRedirectTo: redirectTo } });
    if (error) throw new Error(authErrorMessage(error.code));
    this.setSession(data.session);
    return data.session !== null;
  }
  async logout() {
    if (!this.client) { this.setSession(null); return; }
    const { error } = await this.client.auth.signOut({ scope: "local" });
    if (error) throw new Error(authErrorMessage(error.code));
    this.setSession(null);
  }
  async accessToken(): Promise<string | null> {
    await this.start();
    if (!this.client || this.state.status !== "authenticated") return null;
    const userId = this.state.session?.user.id;
    const { data, error } = await this.client.auth.getSession();
    if (this.state.status !== "authenticated" || this.state.session?.user.id !== userId) return null;
    if (error || !data.session) { this.setSession(null); return null; }
    if (data.session.user.id !== userId) return null;
    this.setSession(data.session);
    return data.session.access_token;
  }
  refreshAccessToken(): Promise<string | null> {
    if (this.refresh) return this.refresh;
    this.refresh = this.doRefresh().finally(() => { this.refresh = null; });
    return this.refresh;
  }
  private async doRefresh(): Promise<string | null> {
    if (!this.client) return null;
    const userId = this.state.session?.user.id;
    try {
      const { data, error } = await this.client.auth.refreshSession();
      if (this.state.session?.user.id !== userId) return null;
      if (error || !data.session || data.session.user.id !== userId) { await this.expire(userId); return null; }
      this.setSession(data.session);
      return data.session.access_token;
    } catch {
      if (this.state.session?.user.id === userId) await this.expire(userId);
      return null;
    }
  }
  async expire(expectedUserId = this.state.session?.user.id) {
    if (this.state.session?.user.id !== expectedUserId) return;
    try { await this.client?.auth.signOut({ scope: "local" }); }
    catch { /* Invalid sessions must not keep protected UI visible. */ }
    finally {
      if (!this.state.session || this.state.session.user.id === expectedUserId) {
        this.setSession(null, "Oturumunuz sona erdi. Lütfen tekrar giriş yapın.");
      }
    }
  }
  dispose() { this.unsubscribe?.(); this.listeners.clear(); }
}

export const authStore = new AuthStore(supabase);
