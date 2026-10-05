import { useCallback, useEffect, useRef, useState } from "react";
import { ClothingImage } from "../components/ClothingImage";
import { ScoreBar } from "../components/ScoreBar";
import { getRecommendations } from "../services/api";
import type { Recommendation } from "../types";

const seasonOptions = ["", "spring", "summer", "autumn", "winter"];

export function RecommendationsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [season, setSeason] = useState("");
  const [limit, setLimit] = useState(3);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const initialRequestStarted = useRef(false);

  const loadRecommendations = useCallback(async (requestedSeason: string, requestedLimit: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await getRecommendations(requestedSeason || undefined, requestedLimit);
      setRecommendations(response.recommendations);
      setMessage(response.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Öneriler yüklenemedi.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Avoid duplicate initial requests during StrictMode's development effect replay.
    if (initialRequestStarted.current) return;
    initialRequestStarted.current = true;
    void loadRecommendations("", 3);
  }, [loadRecommendations]);

  return (
    <section className="page-section">
      <header className="page-header recommendation-header">
        <div>
          <p className="eyebrow">AKILLI EŞLEŞTİRME</p>
          <h1>Kombin Önerileri</h1>
          <p className="page-intro">Renk, mevsim, stil ve resmiyet uyumuna göre gardırobundan seçildi.</p>
        </div>
        <div className="recommendation-controls">
          <label><span>Mevsim</span><select value={season} onChange={(event) => setSeason(event.target.value)}>{seasonOptions.map((value) => <option key={value} value={value}>{value || "Tüm mevsimler"}</option>)}</select></label>
          <label><span>Sonuç</span><select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>{[3, 5, 8].map((value) => <option key={value}>{value}</option>)}</select></label>
          <button
            type="button"
            className="primary-button recommendation-create-button"
            disabled={loading}
            onClick={() => void loadRecommendations(season, limit)}
          >
            {loading ? "Kombinler hazırlanıyor..." : "Kombin Oluştur"}
          </button>
        </div>
      </header>

      {error && <div className="alert error"><span>!</span>{error}<button onClick={() => void loadRecommendations(season, limit)}>Tekrar dene</button></div>}

      {loading ? (
        <div className="recommendation-list" aria-busy="true">
          <p className="recommendation-loading" role="status">Kombinler hazırlanıyor...</p>
          {[1, 2].map((value) => <div className="recommendation-skeleton" key={value} />)}
        </div>
      ) : error ? null : recommendations.length === 0 ? (
        <div className="empty-state"><span>✦</span><h2>Bu kombin için yeterli kıyafet bulunamadı.</h2><p>{message || "En az bir üst, bir alt ve bir ayakkabı eklemelisin."}</p></div>
      ) : (
        <div className="recommendation-list">
          {recommendations.map((recommendation, index) => (
            <article className="recommendation-card" key={`${recommendation.top.id}-${recommendation.bottom.id}-${recommendation.shoes.id}`}>
              <div className="recommendation-topline"><span>ÖNERİ {String(index + 1).padStart(2, "0")}</span><strong>{Math.round(recommendation.details.total_score * 100)}<small>% uyum</small></strong></div>
              <div className="outfit-layout">
                <div className="outfit-pieces">
                  {(["top", "bottom", "shoes"] as const).map((part) => {
                    const item = recommendation[part];
                    return <div className="outfit-piece" key={part}><div><ClothingImage path={item.image_path} alt={item.name} compact /></div><span>{{ top: "Üst", bottom: "Alt", shoes: "Ayakkabı" }[part]}</span><strong>{item.name}</strong><small>{item.color} · {item.style?.replaceAll("_", " ") || "stil yok"}</small></div>;
                  })}
                </div>
                <div className="score-panel">
                  <ScoreBar label="Renk" value={recommendation.details.color_score} />
                  <ScoreBar label="Mevsim" value={recommendation.details.season_score} />
                  <ScoreBar label="Stil" value={recommendation.details.style_score} />
                  <ScoreBar label="Resmiyet" value={recommendation.details.formality_score} />
                </div>
              </div>
              <div className="explanation-grid">
                <div><h3><span className="positive-dot" />Neden uyumlu?</h3>{recommendation.details.reasons.length ? <ul>{recommendation.details.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>Belirgin bir uyum gerekçesi bulunamadı.</p>}</div>
                {recommendation.details.penalties.length > 0 && <div><h3><span className="warning-dot" />Dikkat edilmesi gerekenler</h3><ul>{recommendation.details.penalties.map((penalty) => <li key={penalty}>{penalty}</li>)}</ul></div>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
