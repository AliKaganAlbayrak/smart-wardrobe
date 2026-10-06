import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { validateProductionEnvironment } from "../scripts/check-production-env.mjs";

async function moduleFrom(path, replacements = []) {
  let source = await readFile(new URL(path, import.meta.url), "utf8");
  for (const [from, to] of replacements) source = source.replace(from, to);
  let output = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  } }).outputText;
  for (const name of ["react", "react/jsx-runtime"]) output = output.replaceAll(`from "${name}"`, `from ${JSON.stringify(import.meta.resolve(name))}`);
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`);
}
const { AuthStore, authErrorMessage } = await moduleFrom("../src/services/auth.ts", [
  ['import { supabase } from "./supabase";', 'const supabase = null;'],
]);
const { validPublicAuthConfig } = await moduleFrom("../src/services/supabase.ts", [
  ['import { createClient } from "@supabase/supabase-js";', 'const createClient = () => null;'],
  ['import.meta.env.VITE_SUPABASE_URL', '""'], ['import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY', '""'],
]);
const { AuthGate } = await moduleFrom("../src/components/AuthGate.tsx");
const { AuthPage } = await moduleFrom("../src/pages/AuthPage.tsx", [
  ['import { authStore } from "../services/auth";', 'const authStore = {};'],
]);

const session = (id = "user-a", token = "TEST-token-a") => ({ user: { id, email: `${id}@example.test` }, access_token: token });
function fakeClient(initial = null) {
  let stored = initial;
  let callback;
  const calls = [];
  const api = {
    onAuthStateChange(cb) { callback = cb; return { data: { subscription: { unsubscribe() { calls.push("unsubscribe"); } } } }; },
    async getSession() { return { data: { session: stored }, error: null }; },
    async signInWithPassword(input) { calls.push(["login", input.email]); stored = session(); callback("SIGNED_IN", stored); return { data: { session: stored }, error: null }; },
    async signUp(input) { calls.push(["register", input.email, input.options.emailRedirectTo]); return { data: { session: null }, error: null }; },
    async signOut() { calls.push("logout"); stored = null; callback("SIGNED_OUT", null); return { error: null }; },
    async refreshSession() { calls.push("refresh"); stored = session("user-a", "TEST-token-renewed"); callback("TOKEN_REFRESHED", stored); return { data: { session: stored }, error: null }; },
  };
  return { auth: api, calls, emit(event, value) { stored = value; callback(event, value); } };
}

test("persisted session is restored without displaying anonymous UI while loading", async () => {
  const client = fakeClient(session()); const store = new AuthStore(client);
  assert.equal(store.getSnapshot().status, "loading");
  await store.start(); assert.equal(store.getSnapshot().status, "authenticated");
  const refreshedPage = new AuthStore(fakeClient(session())); await refreshedPage.start();
  assert.equal(refreshedPage.getSnapshot().session.user.id, "user-a");
  store.dispose(); refreshedPage.dispose();
});

test("login, logout and email confirmation registration use centralized Supabase auth", async () => {
  const client = fakeClient(); const store = new AuthStore(client); await store.start();
  await store.login(" user@example.test ", "TEST-password-only");
  assert.equal(store.getSnapshot().status, "authenticated");
  await store.logout(); assert.equal(store.getSnapshot().status, "anonymous");
  assert.equal(await store.register(" user@example.test ", "TEST-password-only", "https://demo.example/"), false);
  assert.deepEqual(client.calls.filter(Array.isArray), [["login", "user@example.test"], ["register", "user@example.test", "https://demo.example/"]]);
  store.dispose();
});

test("SDK token refresh is observed and concurrent refresh requests are deduplicated", async () => {
  const client = fakeClient(session()); const store = new AuthStore(client); await store.start();
  assert.equal(await store.accessToken(), "TEST-token-a");
  const values = await Promise.all([store.refreshAccessToken(), store.refreshAccessToken()]);
  assert.deepEqual(values, ["TEST-token-renewed", "TEST-token-renewed"]);
  assert.equal(client.calls.filter((value) => value === "refresh").length, 1);
  store.dispose();
});

test("expired sessions and missing auth config fail closed", async () => {
  const client = fakeClient(session()); const store = new AuthStore(client); await store.start();
  client.auth.refreshSession = async () => ({ data: { session: null }, error: { code: "bad_jwt" } });
  assert.equal(await store.refreshAccessToken(), null); assert.equal(store.getSnapshot().status, "anonymous");
  assert.equal(await store.accessToken(), null);
  const missing = new AuthStore(null); await missing.start(); assert.equal(missing.getSnapshot().status, "configuration_error");
  store.dispose(); missing.dispose();
});

test("a delayed token read cannot restore another or logged-out user", async () => {
  const client = fakeClient(session()); const store = new AuthStore(client); await store.start();
  let complete; client.auth.getSession = () => new Promise((resolve) => { complete = resolve; });
  const pending = store.accessToken();
  await new Promise((resolve) => setImmediate(resolve));
  client.emit("SIGNED_OUT", null);
  complete({ data: { session: session() }, error: null });
  assert.equal(await pending, null); assert.equal(store.getSnapshot().status, "anonymous");
  store.dispose();
});

test("auth state subscription updates protected UI and cleanup unsubscribes", async () => {
  const client = fakeClient(); const store = new AuthStore(client); let changes = 0;
  const stop = store.subscribe(() => changes++); await store.start(); client.emit("SIGNED_IN", session("user-b"));
  assert.equal(store.getSnapshot().session.user.id, "user-b"); assert.ok(changes >= 2);
  stop(); store.dispose(); assert.ok(client.calls.includes("unsubscribe"));
});

test("actual AuthGate excludes wardrobe when anonymous or loading", () => {
  const render = (status, value = null) => renderToStaticMarkup(React.createElement(AuthGate, {
    state: { status, session: value, error: null }, anonymous: React.createElement("div", null, "LOGIN_ONLY"),
  }, React.createElement("div", null, "PRIVATE_WARDROBE")));
  assert.ok(render("loading").includes("Oturum kontrol ediliyor"));
  assert.ok(!render("loading").includes("LOGIN_ONLY"));
  assert.ok(!render("anonymous").includes("PRIVATE_WARDROBE"));
  assert.ok(render("authenticated", session()).includes("PRIVATE_WARDROBE"));
});

test("actual auth screen provides accessible email/password login and register UI", () => {
  const html = renderToStaticMarkup(React.createElement(AuthPage, { state: { status: "anonymous", session: null, error: null } }));
  assert.ok(html.includes("Giriş Yap")); assert.ok(html.includes("Kayıt Ol"));
  assert.ok(html.includes('type="email"')); assert.ok(html.includes('type="password"'));
  assert.ok(!html.includes("PRIVATE_WARDROBE"));
});

test("only publishable configuration is accepted, never secret or service-role", () => {
  assert.equal(validPublicAuthConfig("https://project.supabase.co", "sb_publishable_TEST_ONLY"), true);
  for (const key of ["", "sb_secret_TEST_ONLY", "service-role-jwt"]) assert.equal(validPublicAuthConfig("https://project.supabase.co", key), false);
  assert.equal(validPublicAuthConfig("https://user:secret@project.supabase.co", "sb_publishable_TEST_ONLY"), false);
  assert.ok(authErrorMessage("invalid_credentials").includes("yanlış"));
  assert.ok(authErrorMessage("email_not_confirmed").includes("doğrulayın"));
});

globalThis.__authenticatedApiFixture = {
  accessToken: async () => "TEST-token-a", getSnapshot: () => ({ session: { user: { id: "user-a" } } }),
  refreshAccessToken: async () => "TEST-token-renewed", expire: async () => {},
};
const api = await moduleFrom("../src/services/api.ts", [
  ['import.meta.env.VITE_API_BASE_URL', '"https://api.example"'],
  ['import { authStore } from "./auth";', 'const authStore = globalThis.__authenticatedApiFixture;'],
]);

test("all backend requests automatically use the current access token", async (t) => {
  let count = 0;
  t.mock.method(globalThis, "fetch", async (_url, init) => { count++; assert.equal(init.headers.authorization, "Bearer TEST-token-a"); return new Response(JSON.stringify({ clothes: [] })); });
  await api.getClothes(); await api.getRecommendations(); await api.updateClothing(1, { name: "Test" }); await api.deleteClothing(1);
  assert.equal(count, 4);
});

test("401 refreshes once and retries with the renewed token", async (t) => {
  const tokens = [];
  t.mock.method(globalThis, "fetch", async (_url, init) => { tokens.push(init.headers.authorization); return new Response(JSON.stringify({ clothes: [] }), { status: tokens.length === 1 ? 401 : 200 }); });
  assert.deepEqual(await api.getClothes(), { clothes: [] });
  assert.deepEqual(tokens, ["Bearer TEST-token-a", "Bearer TEST-token-renewed"]);
});

test("repeated 401 expires session instead of looping or showing protected data", async (t) => {
  let expired = 0;
  t.mock.method(globalThis.__authenticatedApiFixture, "expire", async () => { expired++; });
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response("{}", { status: 401 }));
  await assert.rejects(api.getClothes(), /Oturumunuz sona erdi/);
  assert.equal(fetch.mock.callCount(), 2); assert.equal(expired, 1);
});

test("private image requests are authenticated and reject foreign URLs before fetch", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async (url, init) => {
    assert.equal(url, "https://api.example/clothes/5/image"); assert.equal(init.headers.authorization, "Bearer TEST-token-a");
    return new Response(new Blob(["photo"], { type: "image/png" }));
  });
  assert.equal(await (await api.getClothingImage("clothes/5/image")).text(), "photo");
  await assert.rejects(api.getClothingImage("https://attacker.example/image"), /Geçersiz/);
  assert.equal(fetch.mock.callCount(), 1);
});

test("an old user's delayed 401 must not refresh or expire the newly logged-in user", async (t) => {
  let current = "user-a";
  t.mock.method(globalThis.__authenticatedApiFixture, "getSnapshot", () => ({ session: { user: { id: current } } }));
  const refresh = t.mock.method(globalThis.__authenticatedApiFixture, "refreshAccessToken", async () => "TEST-renewed");
  const expire = t.mock.method(globalThis.__authenticatedApiFixture, "expire", async () => {});
  t.mock.method(globalThis, "fetch", async () => { current = "user-b"; return new Response("{}", { status: 401 }); });
  await assert.rejects(api.getClothes(), /Oturumunuz sona erdi/);
  assert.equal(refresh.mock.callCount(), 0); assert.equal(expire.mock.callCount(), 0);
});

test("a delayed retry 401 cannot expire a different session", async (t) => {
  let current = "user-a", count = 0;
  t.mock.method(globalThis.__authenticatedApiFixture, "getSnapshot", () => ({ session: { user: { id: current } } }));
  const expire = t.mock.method(globalThis.__authenticatedApiFixture, "expire", async () => {});
  t.mock.method(globalThis, "fetch", async () => { if (++count === 2) current = "user-b"; return new Response("{}", { status: 401 }); });
  await assert.rejects(api.getClothes(), /Oturumunuz sona erdi/);
  assert.equal(expire.mock.callCount(), 0);
});

test("a body completed after logout is not returned as private wardrobe data", async (t) => {
  let current = "user-a";
  t.mock.method(globalThis.__authenticatedApiFixture, "getSnapshot", () => ({ session: current ? { user: { id: current } } : null }));
  t.mock.method(globalThis, "fetch", async () => ({ status: 200, ok: true,
    async json() { current = null; return { clothes: [{ name: "PRIVATE" }] }; } }));
  await assert.rejects(api.getClothes(), /Oturumunuz değişti/);
});

test("session expiration cannot log out an unrelated user", async () => {
  const client = fakeClient(session("user-b")); const store = new AuthStore(client); await store.start();
  await store.expire("user-a");
  assert.equal(store.getSnapshot().session.user.id, "user-b");
  assert.ok(!client.calls.includes("logout")); store.dispose();
});

test("production config fails closed and never puts provided secret values in errors", () => {
  const env = { VITE_API_BASE_URL: "https://api.example", VITE_SUPABASE_URL: "https://project.supabase.co",
    VITE_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_TEST_ONLY" };
  validateProductionEnvironment(env);
  for (const invalid of [{ VITE_API_BASE_URL: "http://127.0.0.1:8001" }, { VITE_SUPABASE_URL: "" },
    { VITE_SUPABASE_PUBLISHABLE_KEY: "" }, { VITE_SUPABASE_PUBLISHABLE_KEY: "sb_secret_TEST_ONLY" },
    { VITE_SUPABASE_SECRET_KEY: "TEST_SECRET_MUST_NOT_BE_LOGGED" }]) {
    assert.throws(() => validateProductionEnvironment({ ...env, ...invalid }), (error) =>
      !error.message.includes("TEST_SECRET_MUST_NOT_BE_LOGGED") && !error.message.includes("sb_secret_TEST_ONLY"));
  }
});
