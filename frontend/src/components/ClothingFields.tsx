import { categories, displayLabel, fits, seasons, styles } from "../services/display";
import type { ClothingDraft } from "../types";

export function validateDraft(form: ClothingDraft): string | null {
  if (!form.name.trim() || !form.color.trim() || !form.category.trim()) return "Kıyafet adı, kategori ve renk alanlarını doldurun.";
  if (!form.seasons.length) return "En az bir mevsim seçin.";
  if (form.formality !== null && (!Number.isInteger(form.formality) || form.formality < 1 || form.formality > 10)) return "Resmiyet seviyesi 1 ile 10 arasında olmalı.";
  return null;
}

export function ClothingFields({ value, onChange }: {
  value: ClothingDraft;
  onChange: <K extends keyof ClothingDraft>(key: K, value: ClothingDraft[K]) => void;
}) {
  const selectOptions = (options: string[], selected: string) => [...new Set([...options, ...(selected && !options.includes(selected) ? [selected] : [])])];
  return <>
    <div className="form-section-heading"><span>01</span><div><h2>Parçanı tanımla</h2><p>İsim, kategori ve renkle başla.</p></div></div>
    <div className="form-grid">
      <label className="full-width"><span>Kıyafet adı</span><input required maxLength={100} value={value.name} onChange={(e) => onChange("name", e.target.value)} placeholder="Örn. Krem keten gömlek" /></label>
      <label><span>Kategori</span><select value={value.category} onChange={(e) => onChange("category", e.target.value)}>{selectOptions(categories, value.category).map((v) => <option key={v} value={v}>{displayLabel(v)}</option>)}</select></label>
      <label><span>Renk</span><input required maxLength={50} value={value.color} onChange={(e) => onChange("color", e.target.value)} placeholder="Örn. krem veya cream" /></label>
    </div>
    <div className="form-section-heading"><span>02</span><div><h2>Stil ve doku</h2><p>Bu detaylar kombinlerini daha anlamlı kılar.</p></div></div>
    <div className="form-grid">
      {(["style", "fit"] as const).map((key) => <label key={key}><span>{key === "style" ? "Stil" : "Kalıp"}</span><select value={value[key]} onChange={(e) => onChange(key, e.target.value)}><option value="">Belirtilmedi</option>{selectOptions(key === "style" ? styles : fits, value[key]).map((v) => <option key={v} value={v}>{displayLabel(v)}</option>)}</select></label>)}
      <label className="full-width"><span>Materyal <small>İsteğe bağlı</small></span><input maxLength={100} value={value.material} onChange={(e) => onChange("material", e.target.value)} placeholder="Örn. pamuk, keten, yün" /></label>
    </div>
    <div className="form-section-heading"><span>03</span><div><h2>Ne zaman giyersin?</h2><p>Birden fazla mevsim seçebilirsin.</p></div></div>
    <fieldset className="season-selector">
      <legend>Mevsimler · {value.seasons.length} seçim</legend>
      {selectOptions(seasons, "").concat(value.seasons.filter((v) => !seasons.includes(v))).map((season) => <label key={season} className={value.seasons.includes(season) ? "selected" : ""}>
        <input type="checkbox" checked={value.seasons.includes(season)} onChange={() => onChange("seasons", value.seasons.includes(season) ? value.seasons.filter((v) => v !== season) : [...value.seasons, season])} />
        <span aria-hidden="true">{value.seasons.includes(season) ? "✓" : "+"}</span>{displayLabel(season)}
      </label>)}
    </fieldset>
    <label className="range-field"><span className="range-heading">Resmiyet seviyesi <strong>{value.formality === null ? "Belirtilmedi" : `${value.formality} / 10`}</strong></span>
      <input type="range" min="1" max="10" value={value.formality ?? 5} aria-valuetext={value.formality === null ? "Belirtilmedi, değiştirmek için kaydırın" : `${value.formality} / 10`} onChange={(e) => onChange("formality", Number(e.target.value))} />
      <span className="range-labels"><small>Rahat & günlük</small><small>Resmî & özenli</small></span>
    </label>
    {value.formality === null && <p className="field-hint">Mevcut resmiyet bilgisi boş; kaydırıcıyı kullanmadıkça değişmez.</p>}
  </>;
}
