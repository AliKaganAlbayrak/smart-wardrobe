import { useState } from "react";
import type { FormEvent } from "react";
import { authStore } from "../services/auth";
import type { AuthState } from "../services/auth";

export function AuthPage({ state }: { state: AuthState }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const configured = state.status !== "configuration_error";

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setConfirmation(null);
    try {
      if (mode === "login") await authStore.login(email, password);
      else {
        const signedIn = await authStore.register(email, password, window.location.origin + "/");
        if (!signedIn) setConfirmation("Kayıt başarılı. E-postanıza gelen bağlantıyla hesabınızı doğrulayın, ardından giriş yapın.");
      }
      setPassword("");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "İşlem tamamlanamadı. Lütfen tekrar deneyin.");
    } finally { setBusy(false); }
  }

  return <main className="auth-shell">
    <section className="auth-intro"><span className="brand-mark">SW</span><p className="eyebrow">SMART WARDROBE</p>
      <h1>Kendi stilin.<br />Sana özel bir alan.</h1><p>Gardırobunu düzenle, parçalarını keşfet ve sana uygun kombinler oluştur.</p>
      <small>Hesabındaki kıyafetler ve fotoğraflar yalnızca sana aittir.</small></section>
    <section className="auth-panel">
      <div className="auth-tabs" aria-label="Hesap işlemleri">
        <button type="button" aria-pressed={mode === "login"} onClick={() => { setMode("login"); setError(null); setConfirmation(null); }}>Giriş Yap</button>
        <button type="button" aria-pressed={mode === "register"} onClick={() => { setMode("register"); setError(null); setConfirmation(null); }}>Kayıt Ol</button>
      </div>
      <h2>{mode === "login" ? "Tekrar hoş geldin." : "Gardırobuna bir yer aç."}</h2>
      <p>{mode === "login" ? "Kişisel koleksiyonuna kaldığın yerden devam et." : "E-posta ve şifrenle kendi hesabını oluştur."}</p>
      {(error || state.error) && <div className="alert error" role="alert">{error || state.error}</div>}
      {confirmation && <div className="auth-confirmation" role="status">{confirmation}</div>}
      <form onSubmit={submit} className="auth-form">
        <label><span>E-posta</span><input type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required disabled={busy || !configured} /></label>
        <label><span>Şifre</span><input type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={mode === "register" ? 8 : 1} value={password} onChange={(event) => setPassword(event.target.value)} required disabled={busy || !configured} /></label>
        {mode === "register" && <small>En az 8 karakter kullanın. E-posta doğrulaması istenebilir.</small>}
        <button className="primary-button" type="submit" disabled={busy || !configured}>{busy ? "Lütfen bekleyin..." : mode === "login" ? "Giriş Yap" : "Hesap Oluştur"}</button>
      </form>
    </section>
  </main>;
}
