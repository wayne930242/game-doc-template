/// <reference types="astro/client" />

interface ImportMetaEnv {
	readonly SITE_PASSWORD?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
