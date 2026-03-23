import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

/**
 * Vitest 单元测试配置
 *
 * 测试目录结构（CLAUDE.md 规范）：
 * - tests/components/ - 组件测试
 * - tests/unit/ - 单元测试
 * - tests/integration/ - 集成测试
 *
 * @see CLAUDE.md 规则二：强制 TDD — 测试分层规范
 */
export default defineConfig({
  // 插件配置
  plugins: [react()],

  // 测试配置
  test: {
    // 测试环境
    environment: "jsdom",

    // 全局变量（describe, test, expect 等）
    globals: true,

    // 设置文件
    setupFiles: [path.join(__dirname, "./test/setup.ts")],

    // 测试文件匹配模式
    include: [
      "**/__tests__/**/*.[jt]s?(x)",
      "**/?(*.)+(spec|test).[jt]s?(x)",
      "components/**/*.test.[jt]s?(x)",
      "store/**/*.test.[jt]s?(x)",
    ],

    // 排除文件和目录
    exclude: [
      "node_modules",
      "dist",
      ".next",
      "out",
      "e2e", // 排除 E2E 测试
    ],

    // 覆盖率配置
    coverage: {
      provider: "v8",
      reporter: ["text", "json", "html", "lcov"],
      // 覆盖率目标（CLAUDE.md 要求）
      lines: 60,
      functions: 60,
      branches: 60,
      statements: 60,
      exclude: [
        "node_modules/",
        "test/",
        "**/*.d.ts",
        "**/*.config.*",
        "**/mockData*",
        "**/__tests__/**",
        "e2e/**",
      ],
    },
  },

  // 路径解析配置
  resolve: {
    alias: {
      // @/* 指向前端源代码目录
      "@": path.resolve(__dirname, "../frontend/src"),
    },
  },

  // 工作目录（从 tests/ 目录运行）
  // 这样可以正确解析相对路径
  root: path.join(__dirname),
});
