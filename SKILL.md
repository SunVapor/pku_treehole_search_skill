---
name: treehole-search-skill
description: 使用 thcli 命令行工具完成北大树洞登录、搜索、帖子详情和评论抓取。适用于“查询树洞信息、检索课程评价、获取帖子原文与评论”的任务。
---

# Treehole Search Skill

## 何时使用

当用户需要以下能力时使用本 Skill：

- 通过命令行登录树洞并保持会话
- 按关键词检索树洞帖子
- 查看帖子详情
- 拉取评论并做分页
- 为后续分析任务准备原始数据

## 核心原则

1. 该 Skill 的标准入口是 `thcli`。
2. agent 在执行任何检索前，必须先确认 `thcli` 可用。
3. 如果 `thcli` 不存在或不可执行，先安装/链接它，再继续检索。
4. 检索、帖子详情、评论获取都应优先通过 `thcli`。

## 运行前检查

在开始前确认以下条件：

- `thcli` 已安装并在 `PATH` 中可用
- 如果未安装，先执行仓库中的安装方式，或将 `app/thcli` 链接到系统路径
- 登录所需的 cookie/profile 文件可写

### 安装 `thcli`

如果环境中没有 `thcli`，先在仓库根目录下运行：

```bash
sudo ln -sf "$(pwd)/app/thcli" /usr/local/bin/thcli
```

然后用下面命令确认可用：

```bash
thcli --help
```

推荐检查命令：

```bash
thcli --help
```

如果命令不可用，再进行安装/链接后重试。

## 标准工作流

### 1. 初始化登录

第一次使用或会话失效时，先运行：

```bash
thcli init
```

该命令会：

- 交互输入学号和密码
- 自动处理短信验证码或手机令牌验证码等二次验证
- 保存 cookie 和 profile 信息

### 2. 登录状态检查

在执行检索前，如果不确定登录是否有效，运行：

```bash
thcli whoami
```

### 3. 搜索帖子

用关键词检索：

```bash
thcli search "关键词" --limit 10 --comment-limit 3
```

如果需要结构化数据，使用 JSON 输出：

```bash
thcli search "关键词" --json
```

### 4. 获取帖子详情

```bash
thcli post 8001234
```

### 5. 获取评论

```bash
thcli comments 8001234 --all --limit 50
```

## 失败处理

当命令失败时，优先按下面顺序处理：

1. 检查 `thcli` 是否存在：`thcli --help`
2. 检查 cookie/profile 是否有效
3. 重新执行 `thcli init` 或 `thcli login`
4. 如果仍提示验证码错误，视为登录态过期，重新初始化

## 代码入口

- CLI 入口：`app/treehole_cli.py`
- 命令包装：`app/thcli`
- 树洞 API 封装：`app/src/treehole_client.py`
- 示例脚本：`app/examples/quick_search.py`

## 示例

```bash
thcli init
thcli search "数据库" --limit 10 --comment-limit 5
thcli post 8001234
thcli comments 8001234 --all
```
