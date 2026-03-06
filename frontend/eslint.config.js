import { createRequire } from 'module'
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

const require = createRequire(import.meta.url)
const noLongClassname = require('./eslint-plugin-local/no-long-classname.cjs')

const localPlugin = {
  plugins: {
    local: { rules: { 'no-long-classname': noLongClassname } },
  },
}

export default defineConfig([
  globalIgnores(['**/dist', '**/node_modules']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    ...localPlugin,
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      'local/no-long-classname': ['warn', { max: 2 }],
    },
  },
])
