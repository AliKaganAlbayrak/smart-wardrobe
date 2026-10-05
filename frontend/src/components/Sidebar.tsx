import type { PageName } from "../types";

interface SidebarProps {
  activePage: PageName;
  onNavigate: (page: PageName) => void;
}

const navItems: Array<{ id: PageName; label: string; icon: string }> = [
  { id: "wardrobe", label: "Gardırobum", icon: "▦" },
  { id: "add", label: "Kıyafet Ekle", icon: "+" },
  { id: "recommendations", label: "Kombin Önerileri", icon: "✦" },
];

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar">
      <button className="brand" onClick={() => onNavigate("wardrobe")}>
        <span className="brand-mark">SW</span>
        <span>
          <strong>Smart</strong>
          <small>Wardrobe</small>
        </span>
      </button>

      <nav className="nav-list" aria-label="Ana navigasyon">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activePage === item.id ? "active" : ""}`}
            aria-current={activePage === item.id ? "page" : undefined}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot" />
        Kişisel stil arşivin
      </div>
    </aside>
  );
}
