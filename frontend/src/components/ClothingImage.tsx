import { useEffect, useState } from "react";
import { getClothingImage } from "../services/api";

interface ClothingImageProps {
  path: string | null;
  alt: string;
  compact?: boolean;
}

export function ClothingImage({ path, alt, compact = false }: ClothingImageProps) {
  const [failed, setFailed] = useState(false);
  const [source, setSource] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setFailed(false); setSource(null);
    if (path) void getClothingImage(path).then((blob) => {
      if (!active) return;
      objectUrl = URL.createObjectURL(blob); setSource(objectUrl);
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [path]);

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
