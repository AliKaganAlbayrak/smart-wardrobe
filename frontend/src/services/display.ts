export const categories = ["tshirt", "shirt", "polo", "sweater", "hoodie", "jacket", "coat", "pants", "jeans", "shorts", "shoes"];
export const styles = ["casual", "smart_casual", "formal", "sport"];
export const fits = ["slim", "regular", "relaxed", "oversized"];
export const seasons = ["spring", "summer", "autumn", "winter", "all-season"];

const labels: Record<string, string> = {
  tshirt: "Tişört", shirt: "Gömlek", polo: "Polo", sweater: "Kazak", hoodie: "Kapüşonlu",
  jacket: "Ceket", coat: "Palto", pants: "Pantolon", jeans: "Kot", shorts: "Şort", shoes: "Ayakkabı",
  casual: "Günlük", smart_casual: "Şık günlük", formal: "Resmî", sport: "Sportif",
  slim: "Dar", regular: "Standart", relaxed: "Rahat", oversized: "Bol",
  spring: "İlkbahar", summer: "Yaz", autumn: "Sonbahar", winter: "Kış", "all-season": "Dört mevsim",
  black: "Siyah", white: "Beyaz", cream: "Krem", beige: "Bej", navy: "Lacivert",
  gray: "Gri", blue: "Mavi", ice_blue: "Buz mavisi", khaki: "Haki", brown: "Kahverengi",
};

export const normalized = (value: string) => value.trim().toLowerCase();
export const displayLabel = (value: string | null) => {
  if (!value?.trim()) return "Belirtilmedi";
  return labels[normalized(value)] ?? value.trim().replaceAll("_", " ");
};

export function friendlyExplanation(message: string): string {
  if (/eksik stil metadata/i.test(message)) return "Bu parçada bazı stil bilgileri eksik.";
  if (/eksik resmiyet metadata/i.test(message)) return "Bazı parçaların resmiyet seviyesi henüz belirtilmemiş.";
  if (/bilinmeyen renk|eksik renk/i.test(message)) return "Bazı renkleri henüz değerlendiremiyoruz.";
  if (/eksik mevsim metadata/i.test(message)) return "Bazı parçaların mevsim bilgisi henüz belirtilmemiş.";
  return message.replace(/\s*\(\d\.\d+\)\.?/g, ".");
}
