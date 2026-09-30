import { useState } from "react";
import { imageUrl } from "../services/api";

interface ClothingImageProps {
  path: string | null;
  alt: string;
  compact?: boolean;
}

export function ClothingImage({ path, alt, compact = false }: ClothingImageProps) {
  const [failed, setFailed] = useState(false);
  const source = imageUrl(path);

  if (!source || failed) {
    return (
      <div className={`image-placeholder ${compact ? "compact" : ""}`}>
        <span aria-hidden="true">◇</span>
        {!compact && <small>Görsel yok</small>}
      </div>
    );
  }

  return <img src={source} alt={alt} onError={() => setFailed(true)} />;
}
