# Skills Directory

此目录用于存放项目特定的 Agent Skills。

## 目录结构

```
skills/
├── examples/           # 示例 Skills
│   ├── web_search/    # 网络搜索技能
│   └── code_analyzer/ # 代码分析技能
└── custom/            # 自定义 Skills（用户创建）
    └── your_skill/
```

## Skill 结构

每个 Skill 目录必须包含 `SKILL.md` 文件：

```markdown
# Skill Name

## Metadata
- Name: skill_name
- Version: 1.0.0
- Author: Your Name
- Description: 简短描述

## Instructions
详细说明 Skill 的使用方法和行为

## Tools
- tool1
- tool2

## Examples
示例对话场景
```

## 优先级

- **项目 Skills** (`skills/`): 优先级更高，覆盖全局 Skills
- **全局 Skills** (`~/.agents/skills/`): 默认 Skills，可被项目覆盖

## 加载机制

1. 扫描 `~/.agents/skills/` 目录
2. 扫描项目 `skills/` 目录
3. 项目 Skills 覆盖全局同名 Skills
4. LLM 可通过 `read_file` 工具激活 Skill

## 创建新 Skill

1. 在 `skills/custom/` 下创建新目录
2. 创建 `SKILL.md` 文件
3. 重启后端服务或使用热重载 API
