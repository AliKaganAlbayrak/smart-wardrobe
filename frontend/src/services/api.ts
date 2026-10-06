import type {
  ClothingCreateResponse,
  Clothing,
  ClothingUpdate,
  ClothingDeleteResponse,
  ClothingListResponse,
  CreateClothingInput,
  RecommendationListResponse,
} from "../types";
import { authStore } from "./auth";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "") || "http://127.0.0.1:8001";

async function authenticatedFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = await authStore.accessToken();
  const userId = authStore.getSnapshot().session?.user.id;
  if (!token || !userId) throw new Error("Lütfen gardırobunuza erişmek için giriş yapın.");
  const send = (accessToken: string) => {
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    return fetch(`${API_BASE_URL}${path}`, { ...init, headers: Object.fromEntries(headers) });
  };
  let response: Response;
  try {
    response = await send(token);
    if (authStore.getSnapshot().session?.user.id !== userId) throw new Error("session-expired");
    if (response.status === 401) {
      const renewed = await authStore.refreshAccessToken();
      if (!renewed || authStore.getSnapshot().session?.user.id !== userId) throw new Error("session-expired");
      response = await send(renewed);
      if (authStore.getSnapshot().session?.user.id !== userId) throw new Error("session-expired");
      if (response.status === 401) { await authStore.expire(userId); throw new Error("session-expired"); }
    }
    if (authStore.getSnapshot().session?.user.id !== userId) throw new Error("session-expired");
    return response;
  } catch (error) {
    if (error instanceof Error && error.message === "session-expired") {
      throw new Error("Oturumunuz sona erdi. Lütfen tekrar giriş yapın.");
    }
    throw new Error("Sunucuya bağlanılamadı. Backend'in çalıştığından emin olun.");
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authenticatedFetch(path, init);
  const userId = authStore.getSnapshot().session?.user.id;

  if (!response.ok) {
    let message = `İstek başarısız oldu (${response.status}).`;
    try {
      const payload: unknown = await response.json();
      if (typeof payload === "object" && payload !== null && "detail" in payload) {
        if (typeof payload.detail === "string") message = payload.detail;
        else if (Array.isArray(payload.detail)) {
          message = "Bazı bilgiler geçerli değil. Zorunlu alanları, mevsimleri ve 1–10 arasındaki resmiyet değerini kontrol edin.";
        }
      }
    } catch {
      // Keep the HTTP fallback message when the response has no JSON body.
    }
    throw new Error(message);
  }

  const payload: unknown = await response.json();
  if (!userId || authStore.getSnapshot().session?.user.id !== userId) {
    throw new Error("Oturumunuz değişti. Lütfen tekrar deneyin.");
  }
  return payload as T;
}

export async function updateClothing(id: number, input: ClothingUpdate): Promise<Clothing> {
  return request<Clothing>(`/clothes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function imageUrl(imagePath: string | null): string | null {
  if (!imagePath) return null;
  if (/^https?:\/\//.test(imagePath)) return imagePath;
  return `${API_BASE_URL}/${imagePath.replace(/^\/+/, "")}`;
}

export async function getClothingImage(path: string): Promise<Blob> {
  // Never send an access token to a URL from response data or another origin.
  if (!/^\/?clothes\/[1-9]\d*\/image$/.test(path)) throw new Error("Geçersiz görsel yolu.");
  const response = await authenticatedFetch(`/${path.replace(/^\//, "")}`);
  const userId = authStore.getSnapshot().session?.user.id;
  if (!response.ok) throw new Error("Görsel yüklenemedi.");
  const blob = await response.blob();
  if (!userId || authStore.getSnapshot().session?.user.id !== userId) throw new Error("Oturumunuz değişti.");
  return blob;
}

export async function getClothes(): Promise<ClothingListResponse> {
  return request<ClothingListResponse>("/clothes");
}

export async function createClothing(
  input: CreateClothingInput,
): Promise<ClothingCreateResponse> {
  const body = new FormData();
  body.append("name", input.name.trim());
  body.append("category", input.category);
  body.append("color", input.color.trim());
  body.append("season", input.seasons[0]);
  input.seasons.forEach((season) => body.append("seasons", season));
  body.append("style", input.style);
  body.append("fit", input.fit);
  body.append("material", input.material.trim());
  body.append("formality", String(input.formality));
  if (input.image) body.append("image", input.image);

  return request<ClothingCreateResponse>("/clothes", {
    method: "POST",
    body,
  });
}

export async function deleteClothing(
  clothingId: number,
): Promise<ClothingDeleteResponse> {
  return request<ClothingDeleteResponse>(`/clothes/${clothingId}`, {
    method: "DELETE",
  });
}

export async function getRecommendations(
  season?: string,
  limit = 3,
): Promise<RecommendationListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (season) params.set("season", season);
  return request<RecommendationListResponse>(`/recommendations?${params}`);
}
