import { defineMiddleware } from 'astro:middleware';

export const onRequest = defineMiddleware((context, next) => {
	const password = import.meta.env.SITE_PASSWORD;

	// 未設定密碼則不啟用保護
	if (!password) {
		return next();
	}

	const authHeader = context.request.headers.get('authorization');

	if (authHeader) {
		const [scheme, encoded] = authHeader.split(' ');
		if (scheme === 'Basic' && encoded) {
			const decoded = atob(encoded);
			const [, inputPassword] = decoded.split(':');

			if (inputPassword === password) {
				return next();
			}
		}
	}

	return new Response('Authentication required', {
		status: 401,
		headers: {
			'WWW-Authenticate': 'Basic realm="Protected"',
		},
	});
});
