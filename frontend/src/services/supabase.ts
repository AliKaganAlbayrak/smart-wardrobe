import { createClient } from "@supabase/supabase-js";

export function validPublicAuthConfig(url: string, key: string): boolean {
  try {
    const parsed = new URL(url);
    const local = ["localhost", "127.0.0.1"].includes(parsed.hostname);
    return (parsed.protocol === "https:" || (local && parsed.protocol === "http:"))
      && !parsed.username && !parsed.password && !parsed.search && !parsed.hash
      && ["", "/"].includes(parsed.pathname) && key.startsWith("sb_publishable_");
  } catch {
    return false;
  }
}

const url = import.meta.env.VITE_SUPABASE_URL?.trim().replace(/\/+$/, "") || "";
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim() || "";

// Never accept a secret/service-role key in browser configuration.
export const supabase = validPublicAuthConfig(url, key) ? createClient(url, key, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "pkce" },
}) : null;
