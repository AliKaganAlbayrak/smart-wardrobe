import type { Clothing } from "../types";
import { ClothingImage } from "./ClothingImage";

interface ClothingCardProps {
  clothing: Clothing;
  deleting: boolean;
  onDelete: (clothing: Clothing) => void;
}

const label = (value: string | null) => value?.replaceAll("_", " ") || "—";

export function ClothingCard({ clothing, deleting, onDelete }: ClothingCardProps) {
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
          <button
            className="delete-button"
            onClick={() => onDelete(clothing)}
            disabled={deleting}
            aria-label={`${clothing.name} kıyafetini sil`}
            title="Kıyafeti sil"
          >
            {deleting ? "…" : "×"}
          </button>
        </div>

        <div className="metadata-grid">
          <div><span>Mevsim</span><strong>{clothing.seasons.join(", ") || "—"}</strong></div>
          <div><span>Stil</span><strong>{label(clothing.style)}</strong></div>
          <div><span>Materyal</span><strong>{label(clothing.material)}</strong></div>
          <div><span>Resmiyet</span><strong>{clothing.formality ? `${clothing.formality}/10` : "—"}</strong></div>
        </div>
      </div>
    </article>
  );
}
