import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: '/admin/',
  plugins: [react(), tailwindcss()],
  envDir: path.resolve(import.meta.dirname, '../..'),
  envPrefix: 'MABINOGI_',
  server: {
    allowedHosts: true,
    watch: {
      followSymlinks: true,
    },
  },
})
