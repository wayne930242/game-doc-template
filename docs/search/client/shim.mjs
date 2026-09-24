// Pagefind shim：建置期取代 dist/pagefind/pagefind.js。
// 官方 UI 以動態 import 載入此路徑，藉此在不改動 Starlight 元件的前提下
// 加上查詢斷詞、子字串展開與摘要清理。
// 禁止使用 Node API 或 npm 相依。
import * as core from './pagefind-core.js';
import { createSegmenter, HAN_ONLY } from './segment.mjs';
import { expansionCandidates, mergeResults, withCleanExcerpt } from './expand.mjs';

let basePath = null;
let vocabPromise = null;
let hanVocab = null;
let segmenter = null;
let coreQueue = Promise.resolve();

// Pagefind's WASM calls exchange a shared pointer. Keep every public core operation in
// one queue, including UI calls made while another search is loading index chunks.
function withCore(operation) {
	const result = coreQueue.then(operation);
	coreQueue = result.catch(() => {});
	return result;
}

/**
 * core 只會用 `import.meta.url.match(/^(.*\/)pagefind.js.*$/)` 推導自己的 basePath，
 * 而它在建置產物裡已被改名為 pagefind-core.js，正則永遠配不上 → 退回建構子預設值
 * `"/pagefind/"`。官方 UI 只傳 bundlePath（決定動態 import 路徑），不傳 basePath，
 * 因此站台一旦部署在子路徑（Astro `base`），core 會去抓 `/pagefind/pagefind-entry.json` 而 404。
 * shim 自己就住在 bundle 目錄裡，import.meta.url 的目錄即為正確的 basePath。
 */
function ownBasePath() {
	return new URL('./', import.meta.url).href;
}

/**
 * 確保 core 拿到 basePath。UI 的流程是先 options() 再 filters()，而 filters() 就會建構
 * Pagefind 實例並開始抓 pagefind-entry.json——basePath 必須在那之前就送到 core。
 * 所有呼叫都由 withCore 排序，因此只需在首次呼叫時補上。
 */
async function ensureBasePath() {
	if (basePath) return;
	const nextBasePath = ownBasePath();
	await core.options({ basePath: nextBasePath });
	basePath = nextBasePath;
}

/** 詞彙表與索引同目錄。 */
function vocabUrl() {
	return `${basePath || ownBasePath()}vocab.json`;
}

function loadVocab() {
	if (!vocabPromise) {
		vocabPromise = fetch(vocabUrl())
			.then((res) => {
				if (!res.ok) throw new Error(`vocab.json 回應 ${res.status}`);
				return res.json();
			})
			.catch((err) => {
				console.warn('[search] 詞彙表載入失敗，退回未強化的搜尋', err);
				return null;
			});
	}
	return vocabPromise;
}

function prepare(vocab) {
	if (segmenter) return;
	hanVocab = vocab.filter((word) => word.length > 1 && HAN_ONLY.test(word));
	segmenter = createSegmenter(hanVocab);
}

function decorate(base, results) {
	return Object.assign({}, base, { results: results.map(withCleanExcerpt) });
}

/** 篩選專用查詢或詞彙表不可用時的退路：不斷詞、不展開，直接查詢。 */
async function passthroughSearch(term, opts) {
	const raw = await core.search(term, opts);
	return decorate(raw, raw.results);
}

export async function options(opts = {}) {
	return withCore(async () => {
		const nextBasePath = opts.basePath || ownBasePath();
		await core.options(Object.assign({}, opts, { basePath: nextBasePath }));
		basePath = nextBasePath;
	});
}

export async function search(term, opts = {}) {
	return withCore(() => searchCore(term, opts));
}

async function searchCore(term, opts) {
	await ensureBasePath();

	// 篩選專用查詢（無關鍵字，只帶 filters）：無詞可斷、無可展開，直接查詢。
	if (term === null || term === undefined || !String(term).trim()) {
		return passthroughSearch(term, opts);
	}

	const vocab = await loadVocab();
	if (!vocab) {
		return passthroughSearch(term, opts);
	}
	prepare(vocab);

	const query = String(term).trim();
	// 查詢端以詞彙表本身做最長匹配，切出的詞必定存在於索引。
	const direct = await core.search(segmenter.segment(query).join(' '), opts);
	const candidates = expansionCandidates(query, hanVocab);
	const expanded = [];
	for (const word of candidates) expanded.push(await core.search(word, opts));

	return decorate(direct, mergeResults(direct, expanded));
}

/** 官方 UI 在真正查詢前用此暖快取；斷詞方式須與 search() 一致，暖到的 chunk 才對得上。 */
export async function preload(term, opts = {}) {
	return withCore(() => preloadCore(term, opts));
}

async function preloadCore(term, opts) {
	await ensureBasePath();

	if (term === null || term === undefined || !String(term).trim()) {
		return core.preload(term, opts);
	}

	const vocab = await loadVocab();
	if (!vocab) return core.preload(term, opts);
	prepare(vocab);

	const query = String(term).trim();
	return core.preload(segmenter.segment(query).join(' '), opts);
}

/**
 * 官方 UI 自己做防抖動，不會呼叫這個函式；此匯出僅為維持 Pagefind 模組的介面相容，
 * 讓直接使用 Pagefind API 的呼叫端不會少一個方法。
 */
export async function debouncedSearch(term, opts = {}, wait = 300) {
	const token = Symbol('search');
	debouncedSearch.latest = token;
	await new Promise((resolve) => setTimeout(resolve, wait));
	if (debouncedSearch.latest !== token) return null;
	return search(term, opts);
}

export const init = (...args) => withCore(async () => {
	await ensureBasePath();
	return core.init(...args);
});
export const destroy = (...args) => withCore(async () => {
	const result = await core.destroy(...args);
	basePath = null;
	return result;
});
export const filters = (...args) => withCore(async () => {
	await ensureBasePath();
	return core.filters(...args);
});
export const mergeIndex = (...args) => withCore(async () => {
	await ensureBasePath();
	return core.mergeIndex(...args);
});
