import { useEffect, useState, useSyncExternalStore } from "react";
import { authStore } from "./services/auth";
import { AuthGate } from "./components/AuthGate";
import { AuthPage } from "./pages/AuthPage";
import { Sidebar } from "./components/Sidebar";
import { AddClothingPage } from "./pages/AddClothingPage";
import { RecommendationsPage } from "./pages/RecommendationsPage";
import { WardrobePage } from "./pages/WardrobePage";
import type { PageName } from "./types";

const pageTitles: Record<PageName, string> = {
  wardrobe: "Gardırobum",
  add: "Kıyafet Ekle",
  recommendations: "Kombin Önerileri",
};

export default function App() {
  const auth = useSyncExternalStore(authStore.subscribe, authStore.getSnapshot, authStore.getSnapshot);
  useEffect(() => { void authStore.start(); }, []);
  return <AuthGate state={auth} anonymous={<AuthPage state={auth} />}>
    <WardrobeApplication key={auth.session?.user.id} email={auth.session?.user.email || "Hesabım"} />
  </AuthGate>;
}

function WardrobeApplication({ email }: { email: string }) {
  const [activePage, setActivePage] = useState<PageName>("wardrobe");
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState<{ message: string } | null>(null);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);
  const showSuccess = (message: string) => setToast({ message });

  useEffect(() => {
    document.title = `${pageTitles[activePage]} · Smart Wardrobe`;
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [activePage]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const handleCreated = (message: string) => {
    setRefreshKey((value) => value + 1);
    showSuccess(message);
    setActivePage("wardrobe");
  };

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} onNavigate={setActivePage} email={email} loggingOut={loggingOut} onLogout={async () => {
        setLoggingOut(true); setLogoutError(null);
        try { await authStore.logout(); } catch (error) { setLogoutError(error instanceof Error ? error.message : "Çıkış yapılamadı."); }
        finally { setLoggingOut(false); }
      }} />
      <main className="main-content">
        {logoutError && <div className="alert error" role="alert">{logoutError}</div>}
        {activePage === "wardrobe" && <WardrobePage refreshKey={refreshKey} onAddRequested={() => setActivePage("add")} onSuccess={showSuccess} />}
        {activePage === "add" && <AddClothingPage onCreated={handleCreated} />}
        {activePage === "recommendations" && <RecommendationsPage />}
      </main>
      {toast && <div className="toast" role="status"><span aria-hidden="true">✓</span>{toast.message}<button aria-label="Bildirimi kapat" onClick={() => setToast(null)}>×</button></div>}
    </div>
  );
}
