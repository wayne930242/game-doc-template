// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import vercel from '@astrojs/vercel';

// ============================================
// 遊戲文件設定
// ============================================
// TODO: 修改以下設定以符合您的遊戲

const SITE_CONFIG = {
	// 網站標題（顯示在導航列）
	title: '遊戲名稱',
	// 預設語言
	defaultLocale: 'zh-TW',
	localeLabel: '繁體中文',
	// SEO：設為 true 允許搜尋引擎索引
	allowIndexing: false,
};

// ============================================
// Astro 設定（通常不需修改）
// ============================================

export default defineConfig({
	output: 'static',
	adapter: vercel({
		edgeMiddleware: true,
	}),
	markdown: {
		smartypants: false,
	},
	integrations: [
		starlight({
			title: SITE_CONFIG.title,
			head: [
				// SEO 設定
				{
					tag: 'meta',
					attrs: {
						name: 'robots',
						content: SITE_CONFIG.allowIndexing ? 'index, follow' : 'noindex, nofollow',
					},
				},
				// Open Graph 圖片（社群分享預覽）
				{
					tag: 'meta',
					attrs: {
						property: 'og:image',
						content: '/og-image.jpg',
					},
				},
				{
					tag: 'meta',
					attrs: {
						property: 'og:image:width',
						content: '1200',
					},
				},
				{
					tag: 'meta',
					attrs: {
						property: 'og:image:height',
						content: '630',
					},
				},
				{
					tag: 'meta',
					attrs: {
						name: 'twitter:card',
						content: 'summary_large_image',
					},
				},
				{
					tag: 'meta',
					attrs: {
						name: 'twitter:image',
						content: '/og-image.jpg',
					},
				},
			],
			defaultLocale: 'root',
			locales: {
				root: { label: SITE_CONFIG.localeLabel, lang: SITE_CONFIG.defaultLocale },
			},
			// ============================================
			// 側邊欄設定
			// TODO: 根據您的內容結構修改
			// ============================================
			sidebar: [
				{
					label: '快速參考',
					autogenerate: { directory: 'reference' },
				},
				{
					label: '核心規則',
					autogenerate: { directory: 'rules' },
				},
				{
					label: '角色',
					autogenerate: { directory: 'characters' },
				},
				{
					label: '物品與裝備',
					autogenerate: { directory: 'items' },
				},
				{
					label: '世界設定',
					autogenerate: { directory: 'world' },
				},
				{
					label: '主持人指南',
					autogenerate: { directory: 'guides' },
				},
			],
			customCss: ['./src/styles/custom.css'],
		}),
	],
});
