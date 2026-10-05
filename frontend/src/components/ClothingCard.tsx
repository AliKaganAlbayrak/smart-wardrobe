import type { Clothing } from "../types";
import { ClothingImage } from "./ClothingImage";
import { displayLabel } from "../services/display";

interface ClothingCardProps {
  clothing: Clothing;
  onEdit: (clothing: Clothing) => void;
  onDelete: (clothing: Clothing) => void;
}

const label = displayLabel;

export function ClothingCard({ clothing, onEdit, onDelete }: ClothingCardProps) {
  return (
    <article className="clothing-card">
      <div className="clothing-photo">
        <ClothingImage path={clothing.image_path} alt={clothing.name} />
        <span className="category-pill">{label(clothing.category)}</span>
      </div>

      <div className="clothing-card-body">
        <div className="card-heading">
          <div>
            <h3>{clothing.name}</h3>
            <p>{label(clothing.color)}</p>
          </div>
        </div>

        <div className="metadata-grid">
          <div><span>Mevsim</span><strong>{clothing.seasons.map(label).join(" · ") || "Belirtilmedi"}</strong></div>
          <div><span>Stil</span><strong>{label(clothing.style)}</strong></div>
          <div><span>Materyal</span><strong>{label(clothing.material)}</strong></div>
          <div><span>Resmiyet</span><strong>{clothing.formality ? `${clothing.formality}/10` : "—"}</strong></div>
        </div>
        <div className="card-actions"><button onClick={() => onEdit(clothing)} aria-label={`${clothing.name} kıyafetini düzenle`}>Düzenle <span aria-hidden="true">↗</span></button><button className="delete-action" onClick={() => onDelete(clothing)} aria-label={`${clothing.name} kıyafetini sil`}>Sil</button></div>
      </div>
    </article>
  );
}
