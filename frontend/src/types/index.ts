export interface Clothing {
  id: number;
  name: string;
  category: string;
  color: string;
  season: string;
  seasons: string[];
  style: string | null;
  fit: string | null;
  material: string | null;
  formality: number | null;
  image_path: string | null;
}

export interface ClothingListResponse {
  clothes: Clothing[];
}

export interface ClothingCreateResponse {
  message: string;
  clothing: Clothing;
}

export interface ClothingDeleteResponse {
  message: string;
  id: number;
}

export interface RecommendationScores {
  color_score: number;
  season_score: number;
  style_score: number;
  formality_score: number;
  total_score: number;
  reasons: string[];
  penalties: string[];
  season_quality_factor?: number;
  jacket_bonus?: number;
}

export interface Recommendation {
  score: number;
  top: Clothing;
  jacket?: Clothing | null;
  bottom: Clothing;
  shoes: Clothing;
  details: RecommendationScores;
}

export interface RecommendationListResponse {
  recommendations: Recommendation[];
  message: string | null;
}

export type PageName = "wardrobe" | "add" | "recommendations";

export interface ClothingFilters {
  category: string;
  color: string;
  season: string;
  style: string;
}

export interface CreateClothingInput {
  name: string;
  category: string;
  color: string;
  seasons: string[];
  style: string;
  fit: string;
  material: string;
  formality: number;
  image: File | null;
}

export type ClothingDraft = Pick<Clothing, "name" | "category" | "color" | "seasons"> & {
  style: string;
  fit: string;
  material: string;
  formality: number | null;
};

export type ClothingUpdate = Partial<Pick<Clothing,
  "name" | "category" | "color" | "seasons" | "style" | "fit" | "material"
>> & { formality?: number };
