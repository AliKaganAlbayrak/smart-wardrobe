import { useCallback, useEffect, useMemo, useState } from "react";
import { ClothingCard } from "../components/ClothingCard";
import { EditClothingModal } from "../components/EditClothingModal";
import { EmptyState, ErrorNotice } from "../components/Feedback";
import { Modal } from "../components/Modal";
import { deleteClothing, getClothes } from "../services/api";
import { displayLabel, normalized } from "../services/display";
import type { Clothing, ClothingFilters } from "../types";

const emptyFilters: ClothingFilters = { category: "", color: "", season: "", style: "" };

export function WardrobePage({ refreshKey, onAddRequested, onSuccess }: {
  refreshKey: number; onAddRequested: () => void; onSuccess: (message: string) => void;
}) {
  const [clothes, setClothes] = useState<Clothing[]>([]);
  const [filters, setFilters] = useState<ClothingFilters>(emptyFilters);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Clothing | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Clothing | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadClothes = useCallback(async () => {
    setLoading(true); setError(null);
    try { setClothes((await getClothes()).clothes); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Gardırobun yüklenemedi."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void loadClothes(); }, [refreshKey, loadClothes]);

  const options = useMemo(() => ({
    category: [...new Set(clothes.map((i) => normalized(i.category)))].sort(),
    color: [...new Set(clothes.map((i) => normalized(i.color)))].sort(),
    season: [...new Set(clothes.flatMap((i) => i.seasons.map(normalized)))].sort(),
    style: [...new Set(clothes.flatMap((i) => i.style ? [normalized(i.style)] : []))].sort(),
  }), [clothes]);
  const filtered = useMemo(() => clothes.filter((i) => (
    (!filters.category || normalized(i.category) === filters.category)
    && (!filters.color || normalized(i.color) === filters.color)
    && (!filters.season || i.seasons.some((s) => normalized(s) === filters.season))
    && (!filters.style || normalized(i.style ?? "") === filters.style)
  )), [clothes, filters]);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true); setDeleteError(null);
    try {
      await deleteClothing(deleteTarget.id);
      setClothes((current) => current.filter((i) => i.id !== deleteTarget.id));
      setDeleteTarget(null); onSuccess("Parça gardırobundan kaldırıldı.");
    } catch (requestError) { setDeleteError(requestError instanceof Error ? requestError.message : "Kıyafet silinemedi."); }
    finally { setDeleting(false); }
  };
  const handleSaved = (item: Clothing) => {
    setClothes((current) => current.map((i) => i.id === item.id ? item : i));
    setEditing(null); onSuccess("Değişikliklerin kaydedildi.");
    void loadClothes();
  };

  return <section className="page-section">
    <header className="page-header"><div><p className="eyebrow">KİŞİSEL KOLEKSİYON</p><h1>Gardırobum.</h1><p className="page-intro">Sevdiğin parçalar, bir arada. Her güne daha bilinçli bir seçim.</p></div><button className="primary-button" onClick={onAddRequested}><span aria-hidden="true">＋</span> Yeni kıyafet</button></header>
    <div className="collection-summary"><span>{loading || (error && !clothes.length) ? "—" : clothes.length.toString().padStart(2, "0")}<small>PARÇA</small></span><p>Kendi stilinin küçük bir arşivi.</p></div>
    <div className="filter-panel">
      {(["category", "color", "season", "style"] as const).map((key) => <label key={key}><span>{{ category: "Kategori", color: "Renk", season: "Mevsim", style: "Stil" }[key]}</span><select value={filters[key]} onChange={(e) => setFilters((current) => ({ ...current, [key]: e.target.value }))}><option value="">Tümü</option>{options[key].map((o) => <option key={o} value={o}>{displayLabel(o)}</option>)}</select></label>)}
      {Object.values(filters).some(Boolean) && <button className="text-button" onClick={() => setFilters(emptyFilters)}>Temizle</button>}
    </div>
    {error && <ErrorNotice message={error} onRetry={() => void loadClothes()} />}
    {loading ? <div className="card-grid" aria-busy="true" aria-label="Kıyafetler yükleniyor">{Array.from({ length: 6 }, (_, i) => <div className="skeleton-card" key={i} />)}</div>
      : error && !clothes.length ? null : !clothes.length ? <EmptyState title="Henüz kıyafet eklenmemiş." description="İlk parçanı ekleyerek dijital gardırobunu oluşturmaya başla." action="İlk parçanı ekle" onAction={onAddRequested} />
      : !filtered.length ? <EmptyState title="Eşleşen parça bulunamadı." description="Başka bir filtre deneyebilir veya tüm koleksiyonuna dönebilirsin." action="Filtreleri temizle" onAction={() => setFilters(emptyFilters)} />
      : <><div className="result-count"><strong>{filtered.length}</strong> / {clothes.length} parça gösteriliyor</div><div className="card-grid">{filtered.map((clothing) => <ClothingCard key={clothing.id} clothing={clothing} onEdit={setEditing} onDelete={(item) => { setDeleteTarget(item); setDeleteError(null); }} />)}</div></>}
    {editing && <EditClothingModal clothing={editing} onClose={() => setEditing(null)} onSaved={handleSaved} />}
    {deleteTarget && <Modal title="Bu parçayı kaldır?" className="confirm-modal" onClose={() => setDeleteTarget(null)} busy={deleting}><p className="confirm-copy"><strong>{deleteTarget.name}</strong> ve varsa fotoğrafı silinecek. Bu işlem geri alınamaz.</p>{deleteError && <ErrorNotice message={deleteError} />}<footer className="modal-actions"><button className="secondary-button" disabled={deleting} onClick={() => setDeleteTarget(null)}>Vazgeç</button><button className="primary-button danger-button" disabled={deleting} onClick={() => void handleDelete()}>{deleting ? "Siliniyor…" : "Evet, kaldır"}</button></footer></Modal>}
  </section>;
}
