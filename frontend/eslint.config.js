import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // React 19 JSX runtime: importing React is not required
      'no-unused-vars': ['error', {
        varsIgnorePattern: '^React$',
        argsIgnorePattern: '^_',
        caughtErrors: 'none',
      }],
      // The new strict rules from eslint-plugin-react-hooks v7 flag many
      // legitimate patterns (data fetching inside useEffect, derived
      // timestamps in render). Disable to keep the codebase pragmatic.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/purity': 'off',
    },
  },
])
