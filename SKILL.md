---
name: treehole-search-skill
description: 使用 thcli 命令行工具完成北大树洞登录、搜索、帖子详情和评论抓取。适用于"查询树洞信息、检索课程评价、获取帖子原文与评论"的任务。
---

# Treehole Search Skill

## 何时使用

当用户需要搜索北大树洞（PKU Treehole）中的帖子时，例如：
- 搜索课程评价、考试资料、题库、答案
- 查找被试招募、课程群、刷分搭子等信息
- 获取特定帖子的完整内容和评论

## 核心原则

1. 所有树洞操作通过 `thcli` 命令完成。
2. 执行检索前先确认登录态：`thcli whoami`。
3. 默认输出即为结构化 Markdown（含元信息、评论、截断），无需额外参数。
4. 大量结果直接写文件（`-o`），避免终端刷屏。
5. 配置（limit / comment_limit / all_limit）通过 `thcli set` 持久化，通过 `thcli get` 查看。

## 安装

```bash
sudo ln -sf "$(pwd)/app/thcli" /usr/local/bin/thcli
thcli --help
```

首次运行自动创建 `~/.treehole_search_skill.json`（出厂默认：limit=20, comment_limit=5, all_limit=100）。

## 完整信息检索流程

### 步骤 1：确保登录

```bash
thcli whoami
# 若未登录：
thcli login
```

### 步骤 2：根据任务调整配置（可选）

```bash
# 精读场景：加大 limit 和上限
thcli set limit 30
thcli set all-limit 200

# 查看当前所有配置
thcli get
```

### 步骤 3：多关键词覆盖搜索

树洞搜索按单关键词匹配。用多个相关词覆盖搜索范围：

```bash
# 搜课程评价、考试资料、答案
thcli search "探心 考试" --all -o exam.md
thcli search "探心 答案" --all -o answers.md
thcli search "探索心理学的奥秘" --all -o reviews.md
```

如果只是想快速扫一眼是否有关注内容，先用紧凑模式：

```bash
thcli search "探心" -c --limit 30
```

### 步骤 4：对关键帖子获取详情

对搜索结果中感兴趣的 pid，拉取完整内容：

```bash
# 仅帖子原文
thcli post 8220065

# 帖子 + 评论
thcli post 8220065 --with-comments -o post_8220065.md
```

### 步骤 5：整理输出

所有命令均支持 `-o <file>` 写文件。Agent 应优先写文件再读取分析，避免长输出刷屏。

## 命令速查

```bash
# 认证
thcli init              # 首次登录（交互输入学号密码）
thcli login             # 重新登录
thcli whoami            # 检查登录状态

# 配置
thcli get               # 查看全部配置及中文说明
thcli get limit         # 查看单项
thcli set limit 20      # 修改默认每页条数
thcli set all-limit 200 # 修改翻页总上限

# 搜索（默认输出：结构化 Markdown，含元信息和评论）
thcli search "关键词"                   # 默认模式
thcli search "关键词" -c               # 紧凑模式（一行一帖，无评论）
thcli search "关键词" --all            # 翻页拉取全部（上限见配置）
thcli search "关键词" --all -o out.md  # 结果写文件

# 帖子详情
thcli post 8001234                      # 帖子全文
thcli post 8001234 --with-comments     # 帖子 + 评论（数量受 comment_limit 约束）

# 评论
thcli comments 8001234                  # 单页
thcli comments 8001234 --all           # 全部
```

## 输出模式

| 模式 | 触发 | 适用场景 |
|------|------|---------|
| 结构化（默认） | 无参数 | 日常使用：元信息 + 评论 + 正文截断 400 字 |
| 紧凑 | `-c` / `--compact` | 快速扫描，一行一帖 |

## 可配置参数

| 配置项 | 出厂默认 | 说明 |
|--------|---------|------|
| `limit` | 20 | 每页返回条数 |
| `comment_limit` | 5 | 每帖附带评论数 / post --with-comments 评论上限 |
| `all_limit` | 100 | `--all` 翻页总上限 |

```bash
thcli set <key> <value>   # 修改并持久化
thcli get [key]           # 查看
```

CLI 传参（如 `--limit 30`）始终覆盖持久化值。

## 失败处理

1. `thcli --help` — 确认已安装
2. `thcli whoami` — 检查登录态
3. `thcli login` — 重新登录
4. `thcli init` — 完全重来（cookie 过期等）

## 最佳实践

### Agent 检索课程资料

```bash
thcli whoami

# 紧凑模式快速浏览
thcli search "课程名" -c --limit 30

# 多关键词覆盖搜索，结果写文件
thcli search "课程名 考试" --all -o exam.md
thcli search "课程名 答案" --all -o answers.md

# 关键帖子拉详情
thcli post <pid> --with-comments -o post_<pid>.md
```

### 文件优先

```bash
# 好 — 结果进文件，终端干净
thcli search "关键词" --all -o result.md
```

### 多关键词覆盖

```bash
for kw in "探心" "探索心理学的奥秘" "DPM"; do
    thcli search "$kw" --all -o "result_${kw}.md"
done
```

### 先扫再精读

```bash
thcli search "选课" -c --limit 30          # 第一步：快速扫描
thcli post <pid> --with-comments           # 第二步：精读感兴趣的帖子
```
