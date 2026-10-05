import type { Clothing, Recommendation } from "../types";

type OutfitPart = "top" | "jacket" | "bottom" | "shoes";

export interface OutfitPiece {
  part: OutfitPart;
  label: string;
  item: Clothing;
}

const partLabels: Record<OutfitPart, string> = {
  top: "Üst",
  jacket: "Dış katman",
  bottom: "Alt",
  shoes: "Ayakkabı",
};

export function getOutfitPieces(recommendation: Recommendation): OutfitPiece[] {
  const parts: OutfitPart[] = ["top", "jacket", "bottom", "shoes"];
  return parts.flatMap((part) => {
    const item = recommendation[part];
    return item ? [{ part, label: partLabels[part], item }] : [];
  });
}
