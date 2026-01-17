import { defineMiddleware } from 'astro:middleware';

const LOGIN_HTML = (error = false) => `<!DOCTYPE html>
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
    .error { color: #e74c3c; font-size: 0.875rem; margin-bottom: 1rem; text-align: center; display: none; }
    .error.show { display: block; }
  </style>
</head>
<body>
  <div class="container">
    <h1>請輸入密碼</h1>
    <p class="error ${error ? 'show' : ''}" id="error">密碼錯誤</p>
    <form id="form">
      <input type="password" id="password" placeholder="密碼" autofocus required>
      <button type="submit">進入</button>
    </form>
  </div>
  <script>
    document.getElementById('form').addEventListener('submit', function(e) {
      e.preventDefault();
      const pwd = document.getElementById('password').value;
      const hash = btoa(pwd);
      document.cookie = 'site_auth=' + hash + '; path=/; max-age=2592000; samesite=strict';
      location.reload();
    });
  </script>
</body>
</html>`;

export const onRequest = defineMiddleware(async (context, next) => {
	const password = import.meta.env.SITE_PASSWORD;

	// 未設定密碼則不啟用保護
	if (!password) {
		return next();
	}

	// 檢查 cookie
	const cookies = context.request.headers.get('cookie') || '';
	const authCookie = cookies.split(';').find(c => c.trim().startsWith('site_auth='));
	if (authCookie) {
		const token = authCookie.split('=')[1]?.trim();
		const expected = btoa(password);
		if (token === expected) {
			return next();
		}
		// 密碼錯誤，顯示錯誤訊息
		return new Response(LOGIN_HTML(true), {
			status: 401,
			headers: { 'Content-Type': 'text/html; charset=utf-8' },
		});
	}

	// 顯示登入頁
	return new Response(LOGIN_HTML(false), {
		status: 401,
		headers: { 'Content-Type': 'text/html; charset=utf-8' },
	});
});
