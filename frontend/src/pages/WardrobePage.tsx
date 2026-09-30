import { useEffect, useMemo, useState } from "react";
import { ClothingCard } from "../components/ClothingCard";
import { deleteClothing, getClothes } from "../services/api";
import type { Clothing, ClothingFilters } from "../types";

interface WardrobePageProps {
  refreshKey: number;
  onAddRequested: () => void;
}

const emptyFilters: ClothingFilters = { category: "", color: "", season: "", style: "" };

export function WardrobePage({ refreshKey, onAddRequested }: WardrobePageProps) {
  const [clothes, setClothes] = useState<Clothing[]>([]);
  const [filters, setFilters] = useState<ClothingFilters>(emptyFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadClothes = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getClothes();
      setClothes(response.clothes);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Kıyafetler yüklenemedi.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadClothes();
  }, [refreshKey]);

  const options = useMemo(() => ({
    category: [...new Set(clothes.map((item) => item.category))].sort(),
    color: [...new Set(clothes.map((item) => item.color))].sort(),
    season: [...new Set(clothes.flatMap((item) => item.seasons))].sort(),
    style: [...new Set(clothes.map((item) => item.style).filter(Boolean) as string[])].sort(),
  }), [clothes]);

  const filtered = useMemo(() => clothes.filter((item) => (
    (!filters.category || item.category === filters.category)
    && (!filters.color || item.color === filters.color)
    && (!filters.season || item.seasons.includes(filters.season))
    && (!filters.style || item.style === filters.style)
  )), [clothes, filters]);

  const handleDelete = async (clothing: Clothing) => {
    if (!window.confirm(`“${clothing.name}” gardırobundan silinsin mi? Bu işlem geri alınamaz.`)) return;
    setDeletingId(clothing.id);
    setError(null);
    try {
      await deleteClothing(clothing.id);
      setClothes((current) => current.filter((item) => item.id !== clothing.id));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Kıyafet silinemedi.");
    } finally {
      setDeletingId(null);
    }
  };

  const updateFilter = (key: keyof ClothingFilters, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  return (
    <section className="page-section">
      <header className="page-header">
        <div>
          <p className="eyebrow">KİŞİSEL KOLEKSİYON</p>
          <h1>Gardırobum</h1>
          <p className="page-intro">Parçalarını keşfet, filtrele ve her güne uygun seçimler yap.</p>
        </div>
        <button className="primary-button" onClick={onAddRequested}>+ Yeni kıyafet</button>
      </header>

      <div className="filter-panel">
        {(["category", "color", "season", "style"] as const).map((key) => (
          <label key={key}>
            <span>{{ category: "Kategori", color: "Renk", season: "Mevsim", style: "Stil" }[key]}</span>
            <select value={filters[key]} onChange={(event) => updateFilter(key, event.target.value)}>
              <option value="">Tümü</option>
              {options[key].map((option) => <option key={option} value={option}>{option.replaceAll("_", " ")}</option>)}
            </select>
          </label>
        ))}
        {Object.values(filters).some(Boolean) && (
          <button className="text-button" onClick={() => setFilters(emptyFilters)}>Filtreleri temizle</button>
        )}
      </div>

      {error && <div className="alert error"><span>!</span>{error}<button onClick={() => void loadClothes()}>Tekrar dene</button></div>}

      {loading ? (
        <div className="card-grid" aria-label="Kıyafetler yükleniyor">
          {Array.from({ length: 6 }, (_, index) => <div className="skeleton-card" key={index} />)}
        </div>
      ) : error && clothes.length === 0 ? null : clothes.length === 0 ? (
        <div className="empty-state"><span>◇</span><h2>Henüz kıyafet eklenmemiş.</h2><p>İlk parçanı ekleyerek dijital gardırobunu oluşturmaya başla.</p><button className="primary-button" onClick={onAddRequested}>Kıyafet ekle</button></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state compact"><span>⌕</span><h2>Bu filtrelerle eşleşen kıyafet yok.</h2><button className="text-button" onClick={() => setFilters(emptyFilters)}>Filtreleri temizle</button></div>
      ) : (
        <>
          <div className="result-count"><strong>{filtered.length}</strong> parça gösteriliyor</div>
          <div className="card-grid">
            {filtered.map((clothing) => (
              <ClothingCard key={clothing.id} clothing={clothing} deleting={deletingId === clothing.id} onDelete={handleDelete} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
