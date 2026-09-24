// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightAutoSidebar from 'starlight-auto-sidebar';

// ============================================
// 遊戲文件設定
// ============================================

const SITE_CONFIG = {
	// 網站標題（顯示在導航列）：由 generate_nav.py 依 style-decisions.json 的 site.title 寫入
	title: '遊戲規則文件',
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
			],
			defaultLocale: 'root',
			locales: {
				root: { label: SITE_CONFIG.localeLabel, lang: SITE_CONFIG.defaultLocale },
			},
			// ============================================
			// 側邊欄設定
			// TODO: 根據您的內容結構修改
			// ============================================
			sidebar: [],
			plugins: [starlightAutoSidebar()],
			customCss: ['./src/styles/custom.css'],
		}),
	],
});
