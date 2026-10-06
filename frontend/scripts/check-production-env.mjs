// Public build settings only. Never print environment values or credentials.
import { pathToFileURL } from "node:url";
export function validateProductionEnvironment(env) {
  const publicOrigin = (value) => {
    try {
      const url = new URL(value?.trim());
      return url.protocol === "https:" && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
        && !url.username && !url.password && !url.search && !url.hash && url.pathname === "/";
    } catch { return false; }
  };
  if (!publicOrigin(env.VITE_API_BASE_URL)) throw new Error("Set a public HTTPS VITE_API_BASE_URL origin.");
  if (!publicOrigin(env.VITE_SUPABASE_URL)) throw new Error("Set the HTTPS VITE_SUPABASE_URL project origin.");
  if (!/^sb_publishable_[A-Za-z0-9_-]+$/.test(env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() || "")) {
    throw new Error("Set VITE_SUPABASE_PUBLISHABLE_KEY to the publishable key, never a secret/service-role key.");
  }
  for (const name of Object.keys(env)) {
    if (name.startsWith("VITE_") && /secret|service_role|password|database_url/i.test(name)) {
      throw new Error("Remove server credentials from VITE_* environment settings.");
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { validateProductionEnvironment(process.env); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
