import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist', 'src/api/types.gen.ts'] },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
  {
    // 这几处故意跟组件同文件写:shadcn 约定的 cva variants、布局的右侧面板 hook、
    // 静态预览入口里的角标组件。代价只是热更新退化成整页刷新,不值得为它拆文件。
    files: ['src/components/ui/**/*.tsx', 'src/layouts/**/*.tsx', 'demo/main.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
)
