import { useCallback, useEffect, useRef, useState } from "react";
import { ClothingImage } from "../components/ClothingImage";
import { ScoreBar } from "../components/ScoreBar";
import { EmptyState, ErrorNotice } from "../components/Feedback";
import { displayLabel, friendlyExplanation } from "../services/display";
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
          <h1>Birlikte daha iyi.</h1>
          <p className="page-intro">Gardırobundan, sana ait kombinler. Her önerinin arkasındaki uyumu keşfet.</p>
        </div>
        <div className="recommendation-controls">
          <label><span>Mevsim</span><select value={season} onChange={(event) => setSeason(event.target.value)}>{seasonOptions.map((value) => <option key={value} value={value}>{value ? displayLabel(value) : "Tüm mevsimler"}</option>)}</select></label>
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

      {error && <ErrorNotice message={error} onRetry={() => void loadRecommendations(season, limit)} />}

      {loading ? (
        <div className="recommendation-list" aria-busy="true">
          <p className="recommendation-loading" role="status">Kombinler hazırlanıyor...</p>
          {[1, 2].map((value) => <div className="recommendation-skeleton" key={value} />)}
        </div>
      ) : error ? null : recommendations.length === 0 ? (
        <EmptyState title="Bu kombin için yeterli kıyafet bulunamadı." description={message ? "Kombin oluşturmak için gardırobuna bir üst, bir alt ve bir ayakkabı ekle." : "En az bir üst, bir alt ve bir ayakkabı eklemelisin."} />
      ) : (
        <div className="recommendation-list">
          {recommendations.map((recommendation, index) => (
            <article className="recommendation-card" key={`${recommendation.top.id}-${recommendation.bottom.id}-${recommendation.shoes.id}`}>
              <div className="recommendation-topline"><div><span>ÖNERİ {String(index + 1).padStart(2, "0")}</span><p>Üç parça, tek bir bütün.</p></div><div className="total-score"><strong>{Math.round(recommendation.details.total_score * 100)}<small>%</small></strong><span>GENEL UYUM</span></div></div>
              <div className="outfit-layout">
                <div className="outfit-pieces">
                  {(["top", "bottom", "shoes"] as const).map((part) => {
                    const item = recommendation[part];
                    return <div className="outfit-piece" key={part}><div><ClothingImage path={item.image_path} alt={item.name} compact /></div><span>{{ top: "Üst", bottom: "Alt", shoes: "Ayakkabı" }[part]}</span><strong>{item.name}</strong><small>{displayLabel(item.color)}{item.style ? ` · ${displayLabel(item.style)}` : ""}</small></div>;
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
                <div><h3><span className="positive-dot" />Bu kombini öne çıkaranlar</h3>{recommendation.details.reasons.length ? <ul>{recommendation.details.reasons.map((reason) => <li key={reason}>{friendlyExplanation(reason)}</li>)}</ul> : <p>Bu parçalar için belirgin bir uyum henüz bulunamadı.</p>}</div>
                {recommendation.details.penalties.length > 0 && <div><h3><span className="warning-dot" />Küçük notlar</h3><ul>{recommendation.details.penalties.map((penalty) => <li key={penalty}>{friendlyExplanation(penalty)}</li>)}</ul></div>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
