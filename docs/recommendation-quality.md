# Real wardrobe recommendation quality

Audit: 2026-10-05. Live `GET /recommendations?season=<season>&limit=3` after the six metadata PATCH updates. Scores are fractions, not probabilities. No scoring weights, color rules or algorithm changes were made.

## spring

| Rank / pieces (top + bottom + shoes) | Total | Color | Season | Style | Formality | Reasons | Penalties |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Krem Gömlek + Siyah Pamuk Pantolon + Adidas spezial | 0.9071 | 0.8933 | 1.0000 | 0.8667 | 0.8519 | Renk uyumu yüksek (0.89).<br>Mevsim uyumu yüksek (1.00).<br>Stil uyumu yüksek (0.87).<br>Resmiyet seviyeleri uyumlu (0.85). | [] |
| 2. Krem Gömlek + Buz Mavisi Kot + Adidas spezial | 0.8890 | 0.8733 | 1.0000 | 0.8667 | 0.7778 | Renk uyumu yüksek (0.87).<br>Mevsim uyumu yüksek (1.00).<br>Stil uyumu yüksek (0.87). | [] |
| 3. Haki Polo Yaka + Siyah Pamuk Pantolon + Adidas spezial | 0.8721 | 0.7933 | 1.0000 | 0.8667 | 0.8519 | Mevsim uyumu yüksek (1.00).<br>Stil uyumu yüksek (0.87).<br>Resmiyet seviyeleri uyumlu (0.85). | [] |

## summer

| Rank / pieces (top + bottom + shoes) | Total | Color | Season | Style | Formality | Reasons | Penalties |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Krem Gömlek + Siyah Pamuk Pantolon + Adidas spezial | 0.8529 | 0.8933 | 0.7833 | 0.8667 | 0.8519 | Renk uyumu yüksek (0.89).<br>Stil uyumu yüksek (0.87).<br>Resmiyet seviyeleri uyumlu (0.85). | [] |
| 2. Krem Gömlek + Buz Mavisi Kot + Adidas spezial | 0.8348 | 0.8733 | 0.7833 | 0.8667 | 0.7778 | Renk uyumu yüksek (0.87).<br>Stil uyumu yüksek (0.87). | [] |
| 3. Haki Polo Yaka + Siyah Pamuk Pantolon + Adidas spezial | 0.8179 | 0.7933 | 0.7833 | 0.8667 | 0.8519 | Stil uyumu yüksek (0.87).<br>Resmiyet seviyeleri uyumlu (0.85). | [] |

## autumn

| Rank / pieces (top + bottom + shoes) | Total | Color | Season | Style | Formality | Reasons | Penalties |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1. Krem Gömlek + Siyah Pamuk Pantolon + Adidas spezial | 0.9071 | 0.8933 | 1.0000 | 0.8667 | 0.8519 | Renk uyumu yüksek (0.89).<br>Mevsim uyumu yüksek (1.00).<br>Stil uyumu yüksek (0.87).<br>Resmiyet seviyeleri uyumlu (0.85). | [] |
| 2. Krem Gömlek + Buz Mavisi Kot + Adidas spezial | 0.8890 | 0.8733 | 1.0000 | 0.8667 | 0.7778 | Renk uyumu yüksek (0.87).<br>Mevsim uyumu yüksek (1.00).<br>Stil uyumu yüksek (0.87). | [] |
| 3. Haki Polo Yaka + Siyah Pamuk Pantolon + Adidas spezial | 0.8179 | 0.7933 | 0.7833 | 0.8667 | 0.8519 | Stil uyumu yüksek (0.87).<br>Resmiyet seviyeleri uyumlu (0.85). | [] |

## Interpretation

- Structure: every outfit has a recognized top, bottom and shoes. The jacket is deliberately excluded; there is no layering algorithm.
- Spring: all three outfits match the supplied seasons. Cream/black/blue has strong neutral/accent color compatibility; smart-casual shirt/pants with casual sneakers gets partial style credit, not a perfect score. Formality 6/6/4 is relatively close.
- Summer: **neither existing bottom is summer-tagged**. All returned outfits have one out-of-season bottom; mean season score is (1 + 0.35 + 1) / 3 = 0.7833. The current soft-penalty design permits them; none is a fully summer-compatible outfit. The API's aggregate explanation thresholds leave `penalties=[]` for this case. Do not interpret an empty penalty list as perfect seasonal fit.
- Autumn: the cream-shirt outfits fully match; the polo is not autumn-tagged, giving the third result a season score of 0.7833.
- Ranking: the cream shirt + black pants leads under the declared rules. The jeans alternative is slightly less formal/cohesive; khaki/blue gets the generic 0.62 pair fallback rather than a strong neutral-pair score. These scores are a transparent heuristic, not an objective fashion judgment.
- Repetition: no duplicate ID triple within one response. The same outfits across seasons/repeated requests are expected with two tops, two bottoms and one pair of shoes (four unique eligible triples). Deterministic ranking has no recommendation history or diversity mechanism.
- Data limitation: the jacket still has legacy `color="jacket"`; only the user-specified metadata fields were updated. It is excluded from outfits, so this does not affect the reported scores. Fit/material are stored/displayed but not used in V2.2 scoring.

## Preservation

Six existing IDs retained; names, categories, colors and image paths preserved. All requested style/fit/material/formality/seasons values verified through the API. Six photo SHA-256 hashes and the SQLite table schema were unchanged. Legacy `season` was synchronized to the first requested season by existing PATCH behavior.
