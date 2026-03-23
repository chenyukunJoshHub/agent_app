module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:@typescript-eslint/recommended-requiring-type-checking',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
    // 'prettier', // 需要安装 eslint-config-prettier
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: './tsconfig.json',
    ecmaFeatures: {
      jsx: true,
    },
  },
  plugins: ['@typescript-eslint', 'react', 'react-hooks', 'jsx-a11y', 'import'],
  rules: {
    // TypeScript 规则
    '@typescript-eslint/no-unused-vars': 'off', // 暂时关闭未使用变量检查
    '@typescript-eslint/no-explicit-any': 'off', // 暂时关闭以加快开发
    '@typescript-eslint/explicit-function-return-type': 'off',
    '@typescript-eslint/explicit-module-boundary-types': 'off',
    '@typescript-eslint/no-non-null-assertion': 'off', // 暂时关闭
    '@typescript-eslint/consistent-type-imports': 'off', // 暂时关闭
    '@typescript-eslint/no-unsafe-assignment': 'off', // 暂时关闭
    '@typescript-eslint/no-unsafe-call': 'off', // 暂时关闭
    '@typescript-eslint/no-unsafe-member-access': 'off', // 暂时关闭
    '@typescript-eslint/no-unsafe-argument': 'off', // 暂时关闭
    '@typescript-eslint/require-await': 'off', // 暂时关闭
    '@typescript-eslint/no-unnecessary-type-assertion': 'off', // 暂时关闭

    // React 规则
    'react/react-in-jsx-scope': 'off', // Next.js 不需要
    'react/prop-types': 'off', // 使用 TypeScript
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    'react/no-unescaped-entities': 'off', // 暂时关闭
    'react/no-misused-promises': 'off', // 暂时关闭

    // 导入规则（暂时降低严格度）
    'import/order': 'off', // 暂时关闭导入顺序检查

    // 通用规则
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'prefer-const': 'error',

    // 可访问性规则（暂时降低严格度）
    'jsx-a11y/label-has-associated-control': 'off', // 暂时关闭
  },
  settings: {
    react: {
      version: 'detect',
    },
    'import/resolver': {
      typescript: {
        alwaysTryTypes: true,
        project: './tsconfig.json',
      },
    },
  },
};
