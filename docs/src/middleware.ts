import { defineMiddleware } from 'astro:middleware';

const LOGIN_HTML = `<!DOCTYPE html>
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
    <p style="font-size:0.875rem;color:#888;margin:0 0 1rem;text-align:center;">密碼找洪偉要</p>
    {{ERROR}}
    <form method="POST">
      <input type="password" name="password" placeholder="密碼" autofocus required>
      <button type="submit">進入</button>
    </form>
  </div>
</body>
</html>`;

export const onRequest = defineMiddleware(async (context, next) => {
	const password = import.meta.env.SITE_PASSWORD;

	// 未設定密碼則不啟用保護
	if (!password) {
		return next();
	}

	const url = new URL(context.request.url);

	// 檢查 cookie
	const cookies = context.request.headers.get('cookie') || '';
	const authCookie = cookies.split(';').find(c => c.trim().startsWith('site_auth='));
	if (authCookie) {
		const token = authCookie.split('=')[1];
		if (token === Buffer.from(password).toString('base64')) {
			return next();
		}
	}

	// 處理 POST（登入）
	if (context.request.method === 'POST') {
		const formData = await context.request.formData();
		const inputPassword = formData.get('password');

		if (inputPassword === password) {
			const token = Buffer.from(password).toString('base64');
			return new Response(null, {
				status: 302,
				headers: {
					'Location': url.pathname,
					'Set-Cookie': `site_auth=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400`,
				},
			});
		}

		// 密碼錯誤
		const html = LOGIN_HTML.replace('{{ERROR}}', '<p class="error">密碼錯誤</p>');
		return new Response(html, {
			status: 401,
			headers: { 'Content-Type': 'text/html; charset=utf-8' },
		});
	}

	// 顯示登入頁
	const html = LOGIN_HTML.replace('{{ERROR}}', '');
	return new Response(html, {
		status: 401,
		headers: { 'Content-Type': 'text/html; charset=utf-8' },
	});
});
