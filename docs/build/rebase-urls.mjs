// Rebase local root URLs in generated pages after Astro and search have built.
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const docs = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

export function rebaseUrl(url, base) {
	if (!base || !url.startsWith('/') || url.startsWith('//')) return url;
	const normalized = base.replace(/\/+$/, '');
	if (url === normalized || url.startsWith(`${normalized}/`) || url.startsWith(`${normalized}?`) || url.startsWith(`${normalized}#`)) return url;
	return `${normalized}${url}`;
}

export function rebaseContent(content, base, extension) {
	if (!base) return content;
	let result = content;
	if (extension === '.html') {
		result = result.replace(/(\b(?:href|src|poster|action|content)\s*=\s*)(["'])(\/[^"']*)\2/gi,
			(_all, lead, quote, url) => `${lead}${quote}${rebaseUrl(url, base)}${quote}`);
		result = result.replace(/(\bsrcset\s*=\s*)(["'])([^"']*)\2/gi, (_all, lead, quote, urls) => {
			const revised = urls.split(',').map((candidate) => candidate.replace(/^(\s*)(\/[^\s]+)(.*)$/, (_item, space, url, rest) => `${space}${rebaseUrl(url, base)}${rest}`)).join(',');
			return `${lead}${quote}${revised}${quote}`;
		});
	}
	return result.replace(/url\(\s*(["']?)(\/[^)'"\s]+)\1\s*\)/gi,
		(_all, quote, url) => `url(${quote}${rebaseUrl(url, base)}${quote})`);
}

async function* files(dir) {
	for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) yield* files(full);
		else if (entry.name.endsWith('.html') || entry.name.endsWith('.css')) yield full;
	}
}

export async function rebaseDist(dist, base) {
	let changed = 0;
	for await (const file of files(dist)) {
		const before = await fs.readFile(file, 'utf8');
		const after = rebaseContent(before, base, path.extname(file));
		if (after !== before) {
			await fs.writeFile(file, after, 'utf8');
			changed++;
		}
	}
	return changed;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const config = await fs.readFile(path.join(docs, 'astro.config.mjs'), 'utf8');
	const base = config.match(/^\s*base:\s*['"]([^'"]+)['"],?\s*$/m)?.[1] || '';
	const changed = await rebaseDist(path.join(docs, 'dist'), base);
	console.log(`[base] Rebasing ${changed} HTML/CSS files for ${base || '/'}`);
}
