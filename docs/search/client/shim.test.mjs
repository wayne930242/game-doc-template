import test from 'node:test';
import assert from 'node:assert/strict';
import { copyFile, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VOCAB = ['預言', '苦難點', '大苦難點', '舊苦難點'];

async function withShim(run) {
	const directory = await mkdtemp(path.join(tmpdir(), 'pagefind-shim-'));
	const originalFetch = globalThis.fetch;
	try {
		for (const file of ['shim.mjs', 'segment.mjs', 'expand.mjs', 'excerpt.mjs']) {
			await copyFile(path.join(HERE, file), path.join(directory, file));
		}
		await writeFile(
			path.join(directory, 'pagefind-core.js'),
			`let busy = false;
export const calls = [];
async function operation(name, value) {
  if (busy) throw new Error('Pagefind: WASM Error (No pointer)');
  busy = true;
  calls.push(name);
  await new Promise((resolve) => setTimeout(resolve, 5));
  busy = false;
  return value;
}
export const options = () => operation('options');
export const filters = () => operation('filters', {});
export const preload = (term) => operation('preload:' + term);
export const search = (term) => operation('search:' + term, {
  results: [{ id: term, score: 1, data: async () => ({ excerpt: term }) }],
});
export const init = () => operation('init');
export const destroy = () => operation('destroy');
export const mergeIndex = () => operation('mergeIndex');
`
		);
		await writeFile(path.join(directory, 'package.json'), '{"type":"module"}');
		globalThis.fetch = async (url) => {
			assert.match(String(url), /vocab\.json$/);
			return { ok: true, json: async () => VOCAB };
		};
		const shim = await import(pathToFileURL(path.join(directory, 'shim.mjs')).href);
		const core = await import(pathToFileURL(path.join(directory, 'pagefind-core.js')).href);
		await run(shim, core);
	} finally {
		globalThis.fetch = originalFetch;
		await rm(directory, { recursive: true, force: true });
	}
}

test('UI options, filters, preload, and search share one Pagefind pointer', async () => {
	await withShim(async (shim) => {
		await shim.options({ ranking: { termSimilarity: 9 } });
		const outcomes = await Promise.allSettled([
			shim.options({ ranking: { termSimilarity: 9 } }),
			shim.filters(),
			shim.preload('預言'),
			shim.search('預言'),
		]);
		assert.deepEqual(outcomes.map((result) => result.status), Array(4).fill('fulfilled'));
		assert.equal(outcomes[3].value.results.length, 1);
	});
});

test('every expansion query completes even when Pagefind calls would overlap', async () => {
	await withShim(async (shim, core) => {
		const result = await shim.search('苦難點');
		assert.deepEqual(result.results.map((entry) => entry.id), ['苦難點', '大苦難點', '舊苦難點']);
		assert.ok(core.calls.includes('search:大苦難點'));
		assert.ok(core.calls.includes('search:舊苦難點'));
	});
});
