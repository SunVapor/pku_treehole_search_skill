# Treehole CLI App

面向命令行的北大树洞检索工具。

## 功能

- 账号密码登录（含短信/令牌二次验证），会话 Cookie 持久化
- 关键词搜索帖子，支持全量翻页（上限可配）
- 获取帖子详情，可选附带评论
- 持久化配置（`thcli set` / `thcli get`）
- 结果写文件（`-o`）
- Cookie 和 profile 文件均为 0600 权限

## 安装

### 依赖

```bash
cd app && pip install -r requirements.txt
```

### 链接到 PATH

```bash
sudo ln -sf "$(pwd)/app/thcli" /usr/local/bin/thcli
thcli --help
```

首次运行自动创建 `~/.treehole_search_skill.json`，注入出厂默认配置。

## 快速开始

```bash
thcli init                              # 登录
thcli search "选课"                     # 搜索
thcli search "选课" -c                  # 紧凑模式
thcli search "选课" --all -o out.md     # 全量搜索写文件
thcli post 8001234                      # 帖子详情
thcli post 8001234 --with-comments      # 帖子 + 评论
thcli comments 8001234 --all            # 全部评论
```

## 命令参考

### `thcli init`

初始化配置并登录。交互输入学号、密码，按需完成短信/令牌二次验证。

```
thcli init [--username 学号] [--cookies-file 路径]
```

Cookie 保存至 `~/.treehole_cookies.json`，profile 保存至 `~/.treehole_search_skill.json`。

### `thcli login`

使用账号密码重新登录。

```
thcli login [--username 学号] [--cookies-file 路径]
```

### `thcli whoami`

查看当前登录状态。

```
thcli whoami [--cookies-file 路径]
```

### `thcli search`

按关键词搜索帖子。

```
thcli search <关键词> [选项]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `keyword` | str | 必填 | 搜索关键词 |
| `--page` | int | 1 | 起始页码 |
| `--limit` | int | 见 `thcli get` | 每页返回条数 |
| `--comment-limit` | int | 见 `thcli get` | 每帖附带评论数 |
| `--all` | flag | 否 | 翻页拉取全部结果，上限见 `all_limit` |
| `-c, --compact` | flag | 否 | 紧凑输出（无评论，一行一帖） |
| `-o, --output` | path | — | 结果写入文件 |

**输出模式**：默认结构化 Markdown（H2 标题、时间戳、点赞回复数、评论，正文 400 字截断）。`-c` 紧凑模式为一行一帖（140 字截断）。

**翻页行为**：`--all` 时自动翻页直到 API 无更多数据或达到 `all_limit`。单次不传 `--all` 仅返回第一页。

### `thcli post`

获取帖子详情。

```
thcli post <pid> [选项]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pid` | int | 必填 | 帖子 ID |
| `--with-comments` | flag | 否 | 同时拉取评论 |
| `--comment-limit` | int | 见 `thcli get` | 评论总数上限 |
| `-o, --output` | path | — | 结果写入文件 |

`--comment-limit` 在 `post` 中作为评论总数上限（非每页大小），API 调用按需分批（每批 ≤20）。

### `thcli comments`

获取帖子评论。

```
thcli comments <pid> [选项]
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pid` | int | 必填 | 帖子 ID |
| `--page` | int | 1 | 起始页码 |
| `--limit` | int | 见 `thcli get` | 每页条数 |
| `--sort` | asc/desc | asc | 排序 |
| `--all` | flag | 否 | 翻页拉取全部，上限见 `all_limit` |
| `-o, --output` | path | — | 结果写入文件 |

### `thcli set`

持久化修改默认参数。

```
thcli set <key> <value>
```

| key | 说明 | 出厂值 |
|-----|------|--------|
| `limit` | 每页返回条数 | 20 |
| `comment-limit` | 每帖/页附带评论数 | 5 |
| `all-limit` | 翻页总上限 | 100 |

修改立即写入 profile，下次执行生效。CLI 传参（如 `--limit 30`）始终覆盖持久化值。

### `thcli get`

查看当前配置。

```
thcli get [key]
```

不带参数显示全部配置及中文说明。带参数显示单项值。

## 数据文件

| 文件 | 路径 | 权限 | 内容 |
|------|------|------|------|
| Profile | `~/.treehole_search_skill.json` | 0600 | 用户名、cookie 路径、defaults |
| Cookie | `~/.treehole_cookies.json` | 0600 | 会话 cookie（Bearer token） |

可通过参数覆盖默认路径：

```bash
thcli --profile-file /path/to/profile.json search "计网"
thcli search "计网" --cookies-file /path/to/cookies.json
```

## 配置系统

出厂默认仅在首次创建 profile 时写入一次。之后所有默认值从 profile 读取。`--help` 显示 `(默认值见 thcli get)` 而非硬编码数字。

`_resolve_defaults` 用哨兵值 `_UNSET=-1` 区分"未传参"和"显式传入"。仅当 argparse 未收到参数时才从 profile 注入默认值。

## 截断规则

| 场景 | 帖子正文 | 评论 |
|------|---------|------|
| `search` 默认模式 | 400 字 + "…" | 200 字 + "…" |
| `search` 紧凑模式 (`-c`) | 140 字（不标省略号） | 不显示 |
| `post` | 全文 | 200 字 + "…" |
| `comments` | — | 全文 |

## 目录结构

```
app/
├── thcli                  # Shell 包装脚本
├── treehole_cli.py        # CLI 入口 (argparse)
├── requirements.txt       # Python 依赖
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   └── treehole_client.py # API 客户端
└── examples/
    └── quick_search.py    # Python API 示例
```

## Python API

```python
from src import TreeholeClient

client = TreeholeClient(cookies_file="~/.treehole_cookies.json")
client.load_cookies()

result = client.search_posts("选课", limit=10, comment_limit=5)
print(result)
```
