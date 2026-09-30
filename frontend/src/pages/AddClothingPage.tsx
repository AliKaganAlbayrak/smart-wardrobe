import { useEffect, useState, type FormEvent } from "react";
import { createClothing } from "../services/api";
import type { CreateClothingInput } from "../types";

interface AddClothingPageProps {
  onCreated: (message: string) => void;
}

const categories = ["tshirt", "shirt", "polo", "sweater", "hoodie", "jacket", "coat", "pants", "jeans", "shorts", "shoes"];
const styles = ["casual", "smart_casual", "formal", "sport"];
const fits = ["slim", "regular", "relaxed", "oversized"];
const seasons = ["spring", "summer", "autumn", "winter", "all-season"];

const initialForm: CreateClothingInput = {
  name: "",
  category: "shirt",
  color: "",
  seasons: ["summer"],
  style: "casual",
  fit: "regular",
  material: "",
  formality: 5,
  image: null,
};

export function AddClothingPage({ onCreated }: AddClothingPageProps) {
  const [form, setForm] = useState<CreateClothingInput>(initialForm);
  const [preview, setPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!form.image) {
      setPreview(null);
      return;
    }
    const objectUrl = URL.createObjectURL(form.image);
    setPreview(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [form.image]);

  const update = <K extends keyof CreateClothingInput>(key: K, value: CreateClothingInput[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const toggleSeason = (season: string) => {
    setForm((current) => {
      const selected = current.seasons.includes(season)
        ? current.seasons.filter((value) => value !== season)
        : [...current.seasons, season];
      return { ...current, seasons: selected };
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form.seasons.length) {
      setError("En az bir mevsim seçmelisin.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const response = await createClothing(form);
      setForm(initialForm);
      onCreated(response.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Kıyafet eklenemedi.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="page-section narrow-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">YENİ PARÇA</p>
          <h1>Kıyafet Ekle</h1>
          <p className="page-intro">Parçanın detaylarını ekle; kombin motorun onu daha doğru tanısın.</p>
        </div>
      </header>

      <form className="clothing-form" onSubmit={handleSubmit}>
        <div className="form-main">
          <div className="form-section-heading"><span>01</span><div><h2>Temel bilgiler</h2><p>Parçanı tanımlayan ana detaylar.</p></div></div>
          <div className="form-grid">
            <label className="full-width"><span>Kıyafet adı</span><input required value={form.name} onChange={(event) => update("name", event.target.value)} placeholder="Örn. Krem keten gömlek" /></label>
            <label><span>Kategori</span><select value={form.category} onChange={(event) => update("category", event.target.value)}>{categories.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label><span>Renk</span><input required value={form.color} onChange={(event) => update("color", event.target.value)} placeholder="Örn. cream / krem" /></label>
            <label><span>Stil</span><select value={form.style} onChange={(event) => update("style", event.target.value)}>{styles.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></label>
            <label><span>Kalıp</span><select value={form.fit} onChange={(event) => update("fit", event.target.value)}>{fits.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label className="full-width"><span>Materyal</span><input value={form.material} onChange={(event) => update("material", event.target.value)} placeholder="Örn. pamuk, keten, yün" /></label>
          </div>

          <div className="form-section-heading"><span>02</span><div><h2>Mevsim ve resmiyet</h2><p>Birden fazla mevsim seçebilirsin.</p></div></div>
          <fieldset className="season-selector">
            <legend>Mevsimler</legend>
            {seasons.map((season) => (
              <label key={season} className={form.seasons.includes(season) ? "selected" : ""}>
                <input type="checkbox" checked={form.seasons.includes(season)} onChange={() => toggleSeason(season)} />
                {season}
              </label>
            ))}
          </fieldset>

          <label className="range-field">
            <div><span>Resmiyet seviyesi</span><strong>{form.formality}/10</strong></div>
            <input type="range" min="1" max="10" value={form.formality} onChange={(event) => update("formality", Number(event.target.value))} />
            <div className="range-labels"><small>Günlük</small><small>Resmi</small></div>
          </label>
        </div>

        <aside className="upload-panel">
          <div className="form-section-heading"><span>03</span><div><h2>Fotoğraf</h2><p>Net ve sade bir görsel seç.</p></div></div>
          <label className={`upload-box ${preview ? "has-preview" : ""}`}>
            {preview ? <img src={preview} alt="Yüklenecek kıyafet önizlemesi" /> : <><span className="upload-icon">＋</span><strong>Fotoğraf seç</strong><small>JPG, PNG veya WEBP</small></>}
            <input type="file" accept="image/*" onChange={(event) => update("image", event.target.files?.[0] ?? null)} />
          </label>
          {preview && <button type="button" className="text-button centered" onClick={() => update("image", null)}>Fotoğrafı kaldır</button>}
          <div className="form-summary"><span>Seçilen mevsim</span><strong>{form.seasons.length}</strong><span>Resmiyet</span><strong>{form.formality}/10</strong></div>
          {error && <div className="alert error"><span>!</span>{error}</div>}
          <button className="primary-button submit-button" type="submit" disabled={submitting}>{submitting ? "Kaydediliyor…" : "Gardıroba ekle"}</button>
        </aside>
      </form>
    </section>
  );
}
