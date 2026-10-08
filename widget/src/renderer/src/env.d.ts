/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string
  readonly VITE_REBORN_TOKEN?: string
  readonly VITE_SUPABASE_URL?: string
  readonly VITE_SUPABASE_ANON_KEY?: string
  readonly VITE_DEMO_MODE?: string
}

declare module '*.png' {
  const src: string
  export default src
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface Window {
  reborn?: {
    platform: string
    setInteractive?: (interactive: boolean) => void
    quit?: () => void
  }
}
