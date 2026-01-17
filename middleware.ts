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

function getCookie(cookieHeader: string | null, name: string): string | null {
  if (!cookieHeader) return null;
  const match = cookieHeader.match(new RegExp(`(?:^|;\\s*)${name}=([^;]*)`));
  return match ? match[1] : null;
}

function getLoginHTML(redirectPath: string, error: boolean) {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>請輸入密碼</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: system-ui, sans-serif;
      background: #1a1a2e;
      color: #eee;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0;
    }
    .container {
      background: #16213e;
      padding: 2rem;
      border-radius: 8px;
      width: 100%;
      max-width: 320px;
    }
    h1 { font-size: 1.25rem; margin: 0 0 1.5rem; text-align: center; }
    input {
      width: 100%;
      padding: 0.75rem;
      border: 1px solid #333;
      border-radius: 4px;
      background: #0f0f1a;
      color: #eee;
      font-size: 1rem;
      margin-bottom: 1rem;
    }
    input:focus { outline: none; border-color: #4a6fa5; }
    button {
      width: 100%;
      padding: 0.75rem;
      background: #4a6fa5;
      color: #fff;
      border: none;
      border-radius: 4px;
      font-size: 1rem;
      cursor: pointer;
    }
    button:hover { background: #3d5a80; }
    .error { color: #e74c3c; font-size: 0.875rem; margin-bottom: 1rem; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <h1>請輸入密碼</h1>
    ${error ? '<p class="error">密碼錯誤</p>' : ''}
    <form method="POST" action="/api/site-auth">
      <input type="hidden" name="redirect" value="${redirectPath}" />
      <input type="password" name="password" placeholder="密碼" autofocus required />
      <button type="submit">進入</button>
    </form>
  </div>
</body>
</html>`;
}

// Social media crawlers for OG preview
const SOCIAL_CRAWLERS = [
  /facebookexternalhit/i,
  /Twitterbot/i,
  /LinkedInBot/i,
  /Slackbot/i,
  /Discordbot/i,
  /TelegramBot/i,
  /WhatsApp/i,
];

function isSocialCrawler(userAgent: string | null): boolean {
  if (!userAgent) return false;
  return SOCIAL_CRAWLERS.some((pattern) => pattern.test(userAgent));
}

export default function middleware(request: Request) {
  // Skip if no password configured
  if (!PASSWORD) {
    return;
  }

  const url = new URL(request.url);
  const { pathname, search } = url;

  // Skip API routes
  if (pathname.startsWith("/api/")) {
    return;
  }

  // Skip for social media crawlers (OG preview)
  const userAgent = request.headers.get("user-agent");
  if (isSocialCrawler(userAgent)) {
    return;
  }

  const cookieHeader = request.headers.get("cookie");
  const authCookie = getCookie(cookieHeader, COOKIE_NAME);
  const expectedHash = hashPassword(PASSWORD);

  if (authCookie === expectedHash) {
    return;
  }

  const error = url.searchParams.get("error") === "1";
  return new Response(getLoginHTML(pathname + search.replace(/[?&]error=1/, ''), error), {
    status: 401,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

export const config = {
  matcher: ["/((?!_astro|favicon|robots|api).*)"],
};
