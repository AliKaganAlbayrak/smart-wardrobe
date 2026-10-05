import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Exercise the real TypeScript modules using the compiler already in devDependencies.
async function loadModule(path, apiBase = "http://127.0.0.1:8001") {
  const source = (await readFile(new URL(path, import.meta.url), "utf8"))
    .replace("import.meta.env.VITE_API_BASE_URL", JSON.stringify(apiBase));
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`);
}
const display = await loadModule("../src/services/display.ts");
const api = await loadModule("../src/services/api.ts");

test("display labels handle whitespace and missing legacy metadata", () => {
  assert.equal(display.displayLabel(" polo"), "Polo");
  assert.equal(display.displayLabel("smart_casual"), "Şık günlük");
  assert.equal(display.displayLabel(null), "Belirtilmedi");
  assert.equal(display.displayLabel("custom_material"), "custom material");
});
test("recommendation messages are user-friendly without changing scores", () => {
  assert.equal(display.friendlyExplanation("Eksik stil metadata'sı için tarafsız skor kullanıldı."), "Bu parçada bazı stil bilgileri eksik.");
  assert.equal(display.friendlyExplanation("Renk uyumu yüksek (0.89)."), "Renk uyumu yüksek.");
});
test("PATCH client sends only explicit fields as JSON", async (t) => {
  const patch = { name: "Demo Shirt", formality: 5 };
  t.mock.method(globalThis, "fetch", async (url, init) => {
    assert.equal(url, "http://127.0.0.1:8001/clothes/7");
    assert.equal(init.method, "PATCH");
    assert.equal(init.headers["Content-Type"], "application/json");
    assert.deepEqual(JSON.parse(init.body), patch);
    return new Response(JSON.stringify({ id: 7, ...patch }));
  });
  assert.equal((await api.updateClothing(7, patch)).id, 7);
});
test("API validation arrays and network errors produce readable messages", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: [{ loc: ["body", "formality"], msg: "bad" }] }), { status: 422 }));
  await assert.rejects(api.updateClothing(7, { formality: 0 }), /1–10/);
  fetch.mock.mockImplementation(async () => { throw new TypeError("offline"); });
  await assert.rejects(api.getClothes(), /Sunucuya bağlanılamadı/);
});
test("recommendation URL and static image URLs remain compatible", async (t) => {
  t.mock.method(globalThis, "fetch", async (url) => {
    assert.equal(url, "http://127.0.0.1:8001/recommendations?limit=5&season=summer");
    return new Response(JSON.stringify({ recommendations: [], message: null }));
  });
  assert.deepEqual((await api.getRecommendations("summer", 5)).recommendations, []);
  assert.equal(api.imageUrl("uploads/demo.jpg"), "http://127.0.0.1:8001/uploads/demo.jpg");
});

test("production API URL is trimmed and used for requests and images", async (t) => {
  const production = await loadModule("../src/services/api.ts", " https://wardrobe-api.example/// ");
  t.mock.method(globalThis, "fetch", async (url) => {
    assert.equal(url, "https://wardrobe-api.example/clothes");
    return new Response(JSON.stringify({ clothes: [] }));
  });
  assert.deepEqual(await production.getClothes(), { clothes: [] });
  assert.equal(production.imageUrl("uploads/demo.jpg"), "https://wardrobe-api.example/uploads/demo.jpg");
  const fallback = await loadModule("../src/services/api.ts", "");
  assert.equal(fallback.API_BASE_URL, "http://127.0.0.1:8001");
});

test("multipart creation preserves seasons and photo; failed requests can retry", async (t) => {
  const image = new File(["demo"], "demo.jpg", { type: "image/jpeg" });
  let calls = 0;
  t.mock.method(globalThis, "fetch", async (url, init) => {
    calls++;
    assert.equal(url, "http://127.0.0.1:8001/clothes");
    assert.equal(init.method, "POST");
    assert.ok(init.body instanceof FormData);
    assert.deepEqual(init.body.getAll("seasons"), ["spring", "summer"]);
    assert.equal(init.body.get("image").name, "demo.jpg");
    if (calls === 1) return new Response(JSON.stringify({ detail: "Temporary failure" }), { status: 503 });
    return new Response(JSON.stringify({ message: "ok", clothing: { id: 7 } }));
  });
  const input = { name: "Demo", category: "shirt", color: "cream", seasons: ["spring", "summer"],
    style: "smart_casual", fit: "regular", material: "cotton", formality: 5, image };
  await assert.rejects(api.createClothing(input), /Temporary failure/);
  assert.equal((await api.createClothing(input)).clothing.id, 7);
});
