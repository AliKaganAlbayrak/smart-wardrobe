import { useEffect, useState } from "react";
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
  const [activePage, setActivePage] = useState<PageName>("wardrobe");
  const [refreshKey, setRefreshKey] = useState(0);
  const [toast, setToast] = useState<{ message: string } | null>(null);
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
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="main-content">
        {activePage === "wardrobe" && <WardrobePage refreshKey={refreshKey} onAddRequested={() => setActivePage("add")} onSuccess={showSuccess} />}
        {activePage === "add" && <AddClothingPage onCreated={handleCreated} />}
        {activePage === "recommendations" && <RecommendationsPage />}
      </main>
      {toast && <div className="toast" role="status"><span aria-hidden="true">✓</span>{toast.message}<button aria-label="Bildirimi kapat" onClick={() => setToast(null)}>×</button></div>}
    </div>
  );
}
