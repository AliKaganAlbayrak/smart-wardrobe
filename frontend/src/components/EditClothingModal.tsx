import { useState, type FormEvent } from "react";
import { updateClothing } from "../services/api";
import type { Clothing, ClothingDraft, ClothingUpdate } from "../types";
import { ClothingFields, validateDraft } from "./ClothingFields";
import { ClothingImage } from "./ClothingImage";
import { ErrorNotice } from "./Feedback";
import { Modal } from "./Modal";

export function EditClothingModal({ clothing, onClose, onSaved }: {
  clothing: Clothing; onClose: () => void; onSaved: (clothing: Clothing) => void;
}) {
  const [draft, setDraft] = useState<ClothingDraft>({ ...clothing, style: clothing.style ?? "", fit: clothing.fit ?? "", material: clothing.material ?? "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const change = <K extends keyof ClothingDraft>(key: K, value: ClothingDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const problem = validateDraft(draft);
    if (problem) { setError(problem); return; }
    const patch: ClothingUpdate = {};
    for (const key of ["name", "category", "color"] as const) {
      // Do not normalize legacy values unless the user actually edits them.
      if (draft[key] !== clothing[key]) patch[key] = draft[key].trim();
    }
    for (const key of ["style", "fit", "material"] as const) {
      if (draft[key] !== (clothing[key] ?? "")) patch[key] = draft[key].trim() || null;
    }
    if (JSON.stringify(draft.seasons) !== JSON.stringify(clothing.seasons)) patch.seasons = draft.seasons;
    if (draft.formality !== clothing.formality && draft.formality !== null) patch.formality = draft.formality;
    setSaving(true); setError(null);
    try { onSaved(await updateClothing(clothing.id, patch)); }
    catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Değişiklikler kaydedilemedi."); }
    finally { setSaving(false); }
  };
  return <Modal title="Kıyafeti düzenle" onClose={onClose} busy={saving}>
    <div className="edit-preview"><div><ClothingImage path={clothing.image_path} alt={clothing.name} compact /></div><p><strong>{clothing.name}</strong><span>Fotoğrafın korunur. Yalnızca değiştirdiğin bilgiler kaydedilir.</span></p></div>
    <form onSubmit={save} aria-busy={saving}>
      <fieldset className="form-fields" disabled={saving}><ClothingFields value={draft} onChange={change} /></fieldset>
      {error && <ErrorNotice message={error} />}
      <footer className="modal-actions"><button type="button" className="secondary-button" disabled={saving} onClick={onClose}>Vazgeç</button><button className="primary-button" disabled={saving}>{saving ? "Kaydediliyor…" : "Değişiklikleri kaydet"}</button></footer>
    </form>
  </Modal>;
}
