import type { VercelRequest, VercelResponse } from "@vercel/node";

const PASSWORD = process.env.SITE_PASSWORD || "";
const COOKIE_NAME = "site_auth";

function hashPassword(pass: string): string {
  let hash = 0;
  for (let i = 0; i < pass.length; i++) {
    const char = pass.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(36);
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const body = req.body as Record<string, string> | string;
  let password = "";
  let redirect = "/";

  if (typeof body === "string") {
    const params = new URLSearchParams(body);
    password = params.get("password") || "";
    redirect = params.get("redirect") || "/";
  } else if (body) {
    password = body.password || "";
    redirect = body.redirect || "/";
  }

  if (password === PASSWORD) {
    const hash = hashPassword(PASSWORD);
    res.setHeader(
      "Set-Cookie",
      `${COOKIE_NAME}=${hash}; HttpOnly; Secure; SameSite=Lax; Max-Age=${60 * 60 * 24 * 30}; Path=/`
    );
    res.setHeader("Location", redirect);
    return res.status(302).end();
  }

  // Wrong password
  const errorUrl = new URL(redirect, `https://${req.headers.host}`);
  errorUrl.searchParams.set("error", "1");
  res.setHeader("Location", errorUrl.toString());
  return res.status(302).end();
}
