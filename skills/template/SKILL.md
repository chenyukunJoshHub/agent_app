---
name: template
description: >
  这是一个 Skill 模板，用于创建新的自定义技能。

  使用本模板作为起点，修改 description、Instructions 和 Examples
  来创建你自己的 Skill。
version: 1.0.0
status: draft
disable-model-invocation: false
tools: []
---

# Skill 名称

## Instructions

当用户请求 [描述触发条件] 时，按以下步骤执行：

Step 1: [第一步操作说明]
  - [详细说明]
  - [注意事项]

Step 2: [第二步操作说明]
  - [详细说明]
  - [注意事项]

Step 3: [第三步操作说明]
  - [详细说明]
  - [注意事项]

## Examples

Input: "[示例输入 1]"
Output: |
  [示例输出 1]

Input: "[示例输入 2]"
Output: |
  [示例输出 2]

Input: "[示例输入 3]"
Output: |
  [示例输出 3]

---

## 模板使用说明

### YAML Frontmatter 字段

```yaml
---
name: my-skill              # Skill 唯一标识符（必填）
description: >             # Skill 描述（必填，最多 1024 字符）
  清晰描述 Skill 的用途、
  触发条件和使用场景

version: 1.0.0             # 版本号（必填）
status: active             # 状态：active/disabled/draft（必填）
mutex_group: group-name    # 互斥组（可选，同组只能激活一个）
priority: 10               # 优先级（可选，数字越大越优先）
disable-model-invocation: false  # 禁止 LLM 自动调用（可选）
tools:                     # 依赖的工具列表（可选）
  - web_search
  - read_file
---
```

### 状态说明

- **active**: 激活状态，SkillManager 会扫描并加载
- **disabled**: 禁用状态，不加载
- **draft**: 草稿状态，不加载（用于开发中）

### 互斥组（mutex_group）

同一互斥组的 Skills 只能激活一个，避免 Token 消耗过大。

例如：
- `document-analysis`: legal-search, contract-review
- `data-analysis`: csv-reporter, json-analyzer

### 优先级（priority）

当多个 Skills 可能被激活时，优先选择 priority 值高的。

### 工具声明（tools）

声明 Skill 需要使用的工具，用于：
1. 提示 LLM 可用哪些工具
2. 验证工具是否已注册
3. 生成 System Prompt 时列出

### Instructions 编写建议

1. **具体明确**：告诉 LLM 确切的操作步骤
2. **编号清晰**：使用 Step 1, Step 2, Step 3
3. **包含细节**：说明参数、格式、注意事项
4. **工具使用**：明确何时使用哪些工具

### Examples 编写建议

1. **Few-shot**：提供 2-4 个示例
2. **真实场景**：模拟真实用户输入
3. **完整输出**：展示期望的完整响应
4. **格式一致**：保持输出格式统一

### 创建新 Skill 步骤

1. 复制本模板到新目录：`skills/my-skill/SKILL.md`
2. 修改 YAML frontmatter（name, description, status=active）
3. 编写 Instructions（操作步骤）
4. 添加 Examples（输入输出示例）
5. 运行测试：`pytest tests/unit/skills/test_manager.py`
6. 重启服务，LLM 即可使用新 Skill
