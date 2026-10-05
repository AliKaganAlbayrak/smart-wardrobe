import { useEffect, useRef, useState, type FormEvent } from "react";
import { ClothingFields, validateDraft } from "../components/ClothingFields";
import { ErrorNotice } from "../components/Feedback";
import { createClothing } from "../services/api";
import type { ClothingDraft } from "../types";

const initialForm: ClothingDraft = { name: "", category: "shirt", color: "", seasons: ["summer"], style: "casual", fit: "regular", material: "", formality: 5 };

export function AddClothingPage({ onCreated }: { onCreated: (message: string) => void }) {
  const [form, setForm] = useState<ClothingDraft>(initialForm);
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!image) { setPreview(null); return; }
    const objectUrl = URL.createObjectURL(image);
    setPreview(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [image]);

  const update = <K extends keyof ClothingDraft>(key: K, value: ClothingDraft[K]) => setForm((current) => ({ ...current, [key]: value }));
  const selectImage = (file: File | null) => {
    if (file && !file.type.startsWith("image/")) { setError("Lütfen bir görsel dosyası seçin."); if (fileInput.current) fileInput.current.value = ""; return; }
    setError(null); setImage(file);
  };
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const problem = validateDraft(form);
    if (problem) { setError(problem); return; }
    setSubmitting(true); setError(null);
    try {
      await createClothing({ ...form, formality: form.formality ?? 5, image });
      setForm(initialForm); setImage(null);
      onCreated("Yeni parçan gardırobuna eklendi.");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Kıyafet eklenemedi."); }
    finally { setSubmitting(false); }
  };

  return <section className="page-section narrow-page">
    <header className="page-header"><div><p className="eyebrow">KOLEKSİYONUNU BÜYÜT</p><h1>Yeni bir parça.</h1><p className="page-intro">Bir fotoğraf ve birkaç detay. Gardırobunun yeni üyesini tanıyalım.</p></div><span className="page-note">İsim, renk ve mevsim zorunlu</span></header>
    <form className="clothing-form" onSubmit={handleSubmit} aria-busy={submitting}>
      <div className="form-main"><fieldset className="form-fields" disabled={submitting}><ClothingFields value={form} onChange={update} /></fieldset></div>
      <aside className="upload-panel">
        <p className="eyebrow">PARÇANIN PORTRESİ</p><h2>Fotoğrafını ekle</h2><p className="field-hint">Doğal ışık ve sade bir arka plan iyi bir başlangıç.</p>
        <label className={`upload-box ${preview ? "has-preview" : ""}`}>
          {preview ? <img src={preview} alt="Yüklenecek kıyafet önizlemesi" /> : <><span className="upload-icon" aria-hidden="true">＋</span><strong>Fotoğraf seç</strong><small>Görsel yüklemek isteğe bağlıdır</small></>}
          <input ref={fileInput} type="file" aria-label="Kıyafet fotoğrafı" accept="image/*" disabled={submitting} onChange={(e) => selectImage(e.target.files?.[0] ?? null)} />
        </label>
        {preview && <div className="upload-caption"><span>{image?.name}</span><button type="button" className="text-button" disabled={submitting} onClick={() => { setImage(null); if (fileInput.current) fileInput.current.value = ""; }}>Kaldır</button></div>}
        <div className="form-summary"><span>Seçilen mevsim</span><strong>{form.seasons.length}</strong><span>Resmiyet</span><strong>{form.formality ?? 5} / 10</strong></div>
        {error && <ErrorNotice message={error} />}
        <button className="primary-button submit-button" type="submit" disabled={submitting}>{submitting ? "Gardırobuna ekleniyor…" : "Gardıroba ekle"}</button>
        <p className="privacy-note">Bilgilerini daha sonra düzenleyebilirsin.</p>
      </aside>
    </form>
  </section>;
}
