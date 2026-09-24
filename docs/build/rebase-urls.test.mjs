import assert from 'node:assert/strict';
import { test } from 'node:test';
import { rebaseContent, rebaseUrl } from './rebase-urls.mjs';

test('rebases local links and images but preserves external and already based URLs', () => {
	const html = '<a href="/rules/x/">rule</a><img src="/image.png"><a href="//cdn/x">cdn</a><a href="/books/x/rules/">ok</a>';
	assert.equal(rebaseContent(html, '/books/x', '.html'), '<a href="/books/x/rules/x/">rule</a><img src="/books/x/image.png"><a href="//cdn/x">cdn</a><a href="/books/x/rules/">ok</a>');
});

test('rebases srcset and CSS URLs; root deployment is unchanged', () => {
	const html = '<img srcset="/a.png 1x, /b.png 2x"><div style="background:url(/bg.png)">';
	assert.equal(rebaseContent(html, '/books/x', '.html'), '<img srcset="/books/x/a.png 1x, /books/x/b.png 2x"><div style="background:url(/books/x/bg.png)">');
	assert.equal(rebaseContent('a{background:url("/bg.png")}', '/books/x', '.css'), 'a{background:url("/books/x/bg.png")}');
	assert.equal(rebaseContent(html, '', '.html'), html);
	assert.equal(rebaseUrl('/books/x?query=1', '/books/x'), '/books/x?query=1');
});
