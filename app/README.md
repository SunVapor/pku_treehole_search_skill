# Treehole CLI App

一个面向命令行的北大树洞检索工具，支持：

- 账号密码登录（含短信/令牌二次验证）
- 会话 Cookie 持久化
- 关键词搜索帖子
- 获取帖子详情与评论

## 快速开始

### 1. 安装依赖

在 `app` 目录执行：

```bash
pip install -r requirements.txt
```

### 1.1 安装 `thcli`

如果你想在任意目录直接使用 `thcli`，在仓库根目录执行下面这条命令把包装脚本链接到系统路径：

```bash
sudo ln -sf "$(pwd)/app/thcli" /usr/local/bin/thcli
```

安装后可以用下面的命令验证：

```bash
thcli --help
```

### 2. 初始化登录

推荐方式（全局命令）：

```bash
thcli init
```

等价方式（在 `app` 目录）：

```bash
python treehole_cli.py init
```

执行后会交互输入学号、密码，并在需要时继续要求短信验证码或手机令牌验证码。

## 常用命令

```bash
# 查看登录状态
thcli whoami

# 重新登录
thcli login

# 搜索帖子
thcli search "选课" --limit 10 --comment-limit 3

# 获取帖子详情
thcli post 8001234

# 获取评论（全部分页）
thcli comments 8001234 --all --limit 50

# 输出完整 JSON
thcli search "数据库" --json
```

## 配置与数据文件

- Profile 文件默认路径：`~/.treehole_search_skill.json`
- Cookie 文件默认路径：`~/.treehole_cookies.json`

可通过参数覆盖：

```bash
thcli --profile-file /path/to/profile.json search "计网"
thcli search "计网" --cookies-file /path/to/cookies.json
```

## 目录说明

- `treehole_cli.py`: CLI 入口
- `thcli`: 命令包装脚本
- `src/treehole_client.py`: 树洞 API 交互封装
- `examples/quick_search.py`: Python API 示例

## Python API（可选）

```python
from src import TreeholeClient

client = TreeholeClient(cookies_file="./user_cookies/demo.json")
ok = client.ensure_login(username="你的学号", password="你的密码", interactive=True)
if ok:
    result = client.search_posts("选课", limit=10, comment_limit=5)
    print(result)
```
