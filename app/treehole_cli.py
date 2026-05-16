#!/usr/bin/env python3
"""Interactive CLI for treehole-search-skill."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src import TreeholeClient

DEFAULT_PROFILE = os.path.expanduser("~/.treehole_search_skill.json")
DEFAULT_COOKIES = os.path.expanduser("~/.treehole_cookies.json")
_UNSET = -1  # argparse 哨兵值，区分"未传参"和"显式传入"

# 硬编码兜底默认值，可被 profile 中的 defaults 覆盖
HARD_DEFAULTS: dict[str, int] = {
    "limit": 20,
    "comment_limit": 5,
    "all_limit": 100,
}
HARD_DEFAULTS_HELP: dict[str, str] = {
    "limit": "每页返回条数",
    "comment_limit": "每帖/页附带评论数",
    "all_limit": "翻页拉取时的总结果上限",
}
TRUNC_POST = 400   # 搜索结果中帖子正文截断长度
TRUNC_COMMENT = 200  # 搜索结果/评论列表中单条评论截断长度
FETCH_COMMENTS = 20  # post --with-comments 每次 API 请求的评论数


def _resolve_defaults(args: argparse.Namespace, profile_file: str) -> None:
    """用 profile 中持久化的 defaults 覆盖未显式传入的参数。"""
    profile = load_profile(profile_file)
    stored = profile.get("defaults", {})
    for key, hard_val in HARD_DEFAULTS.items():
        cur = getattr(args, key, None)
        if cur is None or cur == _UNSET:
            setattr(args, key, stored.get(key, hard_val))


def _setup_client(args: argparse.Namespace) -> tuple[TreeholeClient, bool, dict]:
    """认证 boilerplate：加载 profile、解析 cookie、创建 client、检查登录。"""
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)
    client = TreeholeClient(cookies_file=cookies_file)
    ok = ensure_authenticated(client)
    return client, ok, profile


def load_profile(profile_file: str) -> Dict[str, Any]:
    path = Path(profile_file)
    if not path.exists():
        defaults = {"defaults": dict(HARD_DEFAULTS)}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(defaults, f, ensure_ascii=False, indent=2)
        return defaults
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile_file: str, profile: Dict[str, Any]) -> None:
    path = Path(profile_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)


def resolve_cookies_file(args: argparse.Namespace, profile: Dict[str, Any]) -> str:
    if getattr(args, "cookies_file", None):
        return os.path.expanduser(args.cookies_file)
    if profile.get("cookies_file"):
        return os.path.expanduser(profile["cookies_file"])
    return DEFAULT_COOKIES


def format_ts(ts: int) -> str:
    """Convert Unix timestamp to human-readable local time."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _write_output(text: str, output_file: Optional[str]) -> None:
    """Print text to stdout and optionally write to file."""
    if output_file:
        try:
            path = Path(output_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        except OSError as e:
            print(f"写入文件失败: {e}", file=sys.stderr)
    print(text)


def _trunc(text: str, limit: int) -> str:
    """截断过长文本，超出 limit 加 "…"。"""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _format_search_full(result: dict) -> str:
    """搜索结果：结构化输出（默认模式），含完整元信息和评论。"""
    if not result.get("success"):
        return f"搜索失败: {result.get('message')}"

    data = result.get("data", {})
    rows = data.get("data", [])
    page = data.get("page", 1)

    lines = [f"# 搜索结果", f"关键词: {result.get('_keyword', 'N/A')}"]
    if isinstance(page, str):
        lines.append(f"跨页 {page}，共 {len(rows)} 条")
    else:
        lines.append(f"第 {page} 页，共 {len(rows)} 条")
    lines.append("")

    for i, post in enumerate(rows, start=1):
        pid = post.get("pid", "?")
        text = _trunc((post.get("text") or "").strip(), TRUNC_POST)
        ts = post.get("timestamp", 0)
        likes = post.get("likenum", 0)
        replies = post.get("reply", 0)
        lines.append(f"## [{i}] #{pid}")
        lines.append(f"时间: {format_ts(ts) if ts else 'N/A'}")
        lines.append(f"点赞: {likes}  回复: {replies}")
        lines.append(f"内容: {text}")
        comments = post.get("comment_list") or []
        if comments:
            lines.append("评论:")
            for c in comments:
                name = c.get("name_tag") or "匿名"
                c_text = _trunc((c.get("text") or "").strip().replace("\n", " "), TRUNC_COMMENT)
                lines.append(f"  - [{name}] {c_text}")
        lines.append("")
    return "\n".join(lines)


def _format_search_compact(result: dict) -> str:
    """搜索结果：紧凑输出（-c 模式），一行一帖，无评论。"""
    if not result.get("success"):
        return f"搜索失败: {result.get('message')}"
    rows = result.get("data", {}).get("data", [])
    lines = [f"关键词: {result.get('_keyword', 'N/A')}", f"返回: {len(rows)} 条"]
    for idx, post in enumerate(rows, start=1):
        ts = format_ts(post.get("timestamp", 0)) if post.get("timestamp") else "?"
        text = (post.get("text") or "").replace("\n", " ").strip()
        lines.append(f"{idx:02d}. #{post.get('pid')}  {ts}  {text[:140]}")
    return "\n".join(lines)


def _format_post_detail(data: dict) -> str:
    """帖子详情输出。"""
    post = data.get("data") or {}
    pid = post.get("pid", "?")
    text = (post.get("text") or "").strip()
    ts = post.get("timestamp", 0)
    likes = post.get("likenum", 0)
    replies = post.get("reply", 0)

    lines = [
        f"# 帖子 #{pid}",
        f"时间: {format_ts(ts) if ts else 'N/A'}",
        f"点赞: {likes}  回复: {replies}",
        "---",
        text,
    ]
    return "\n".join(lines)


def _format_comments_list(comments: list, pid: int) -> str:
    """评论列表输出（含截断）。"""
    lines = [f"# 帖子 #{pid} 的评论", f"共 {len(comments)} 条", ""]
    for i, c in enumerate(comments, start=1):
        name = c.get("name_tag") or c.get("name") or "匿名"
        text = _trunc((c.get("text") or "").strip(), TRUNC_COMMENT)
        ts = c.get("timestamp", 0)
        ref = c.get("comment_id")
        lines.append(f"## [{i}] {name}")
        lines.append(f"时间: {format_ts(ts) if ts else 'N/A'}")
        if ref:
            lines.append(f"回复: 评论#{ref}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def is_logged_in(client: TreeholeClient) -> bool:
    try:
        resp = client.un_read()
        if resp.status_code != 200:
            return False
        body = resp.json()
        if body.get("success"):
            return True
        # token-only sessions may still work for search
        if body.get("message") == "请进行令牌验证":
            probe = client.search_posts("测试", limit=1, comment_limit=0)
            return bool(probe.get("success"))
        return False
    except Exception:
        return False


def ensure_authenticated(client: TreeholeClient) -> bool:
    if is_logged_in(client):
        return True
    print("当前未登录，请先运行: thcli init")
    return False


def cmd_init(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)

    username = args.username
    if not username:
        username = input("学号: ").strip()
        if not username:
            print("学号不能为空")
            return 1

    password = getpass.getpass("密码: ").strip()
    if not password:
        print("密码不能为空")
        return 1

    client = TreeholeClient(cookies_file=cookies_file)
    ok = client.ensure_login(username=username, password=password, interactive=True)
    if not ok:
        print("登录失败")
        return 1

    profile.update(
        {
            "username": username,
            "cookies_file": cookies_file,
        }
    )
    save_profile(args.profile_file, profile)
    print(f"初始化完成，cookie 已保存: {cookies_file}")
    print(f"配置文件已保存: {args.profile_file}")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)
    username = args.username or profile.get("username") or input("学号: ").strip()
    if not username:
        print("学号不能为空")
        return 1

    password = getpass.getpass("密码: ").strip()
    if not password:
        print("密码不能为空")
        return 1

    client = TreeholeClient(cookies_file=cookies_file)
    ok = client.ensure_login(username=username, password=password, interactive=True)
    if not ok:
        print("登录失败")
        return 1

    profile.update({"username": username, "cookies_file": cookies_file})
    save_profile(args.profile_file, profile)
    print("登录成功")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    client, ok, profile = _setup_client(args)
    if not ok:
        return 1
    username = profile.get("username", "(unknown)")
    print("登录状态: 已登录")
    print(f"用户: {username}")
    print(f"cookie: {resolve_cookies_file(args, profile)}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    _resolve_defaults(args, args.profile_file)
    client, ok, _profile = _setup_client(args)
    if not ok:
        return 1

    multi_page = False
    max_all = args.all_limit
    all_rows: list[dict] = []
    page = args.page
    while True:
        result = client.search_posts(
            keyword=args.keyword,
            page=page,
            limit=args.limit,
            comment_limit=args.comment_limit,
        )
        if not result.get("success"):
            print(f"搜索失败: {result.get('message')}")
            return 1

        rows = result.get("data", {}).get("data", [])
        all_rows.extend(rows)

        if not args.all:
            break

        if len(all_rows) >= max_all:
            print(f"已达到上限 {max_all} 条，停止翻页", file=sys.stderr)
            break

        total = result.get("data", {}).get("total", 0)
        last_page = (total + args.limit - 1) // args.limit if args.limit > 0 else 1
        if page >= last_page or not rows:
            break
        page += 1
        multi_page = True

    result["data"]["data"] = all_rows[:max_all]
    result["_keyword"] = args.keyword
    if multi_page:
        result["data"]["page"] = f"{args.page}-{page}"

    if args.compact:
        out = _format_search_compact(result)
    else:
        out = _format_search_full(result)
    _write_output(out, args.output)
    return 0 if result.get("success") else 1


def cmd_post(args: argparse.Namespace) -> int:
    _resolve_defaults(args, args.profile_file)
    client, ok, _profile = _setup_client(args)
    if not ok:
        return 1

    try:
        data = client.get_post(args.pid)
    except Exception as e:
        print(f"获取帖子失败: {e}")
        return 1
    if not data.get("success"):
        print(f"获取帖子失败: {data.get('message', '未知错误')}")
        return 1

    if args.with_comments:
        max_comments = args.comment_limit
        all_comments = []
        page = 1
        while True:
            try:
                fetch = min(max_comments - len(all_comments), FETCH_COMMENTS)
                cdata = client.get_comment(args.pid, page=page, limit=fetch, sort="asc")
            except Exception as e:
                print(f"获取评论失败: {e}", file=sys.stderr)
                break
            if not cdata.get("success"):
                print(f"获取评论失败: {cdata.get('message', '未知错误')}", file=sys.stderr)
                break
            crows = (cdata.get("data") or {}).get("data") or []
            all_comments.extend(crows)

            if len(all_comments) >= max_comments:
                all_comments = all_comments[:max_comments]
                break

            last_page = (cdata.get("data") or {}).get("last_page") or page
            if page >= last_page or not crows:
                break
            page += 1
        data["_comments"] = all_comments

    text = _format_post_detail(data)
    if args.with_comments:
        text += "\n\n" + _format_comments_list(data.get("_comments", []), args.pid)
    _write_output(text, args.output)
    return 0


def cmd_comments(args: argparse.Namespace) -> int:
    _resolve_defaults(args, args.profile_file)
    client, ok, _profile = _setup_client(args)
    if not ok:
        return 1

    max_all = args.all_limit
    all_comments = []
    page = args.page
    while True:
        try:
            data = client.get_comment(args.pid, page=page, limit=args.limit, sort=args.sort)
        except Exception as e:
            print(f"获取评论失败: {e}")
            return 1
        if not data.get("success"):
            print(f"获取评论失败: {data.get('message', '未知错误')}")
            return 1

        rows = (data.get("data") or {}).get("data") or []
        all_comments.extend(rows)

        if not args.all:
            break

        if len(all_comments) >= max_all:
            print(f"已达到上限 {max_all} 条，停止翻页", file=sys.stderr)
            all_comments = all_comments[:max_all]
            break

        last_page = (data.get("data") or {}).get("last_page") or page
        if page >= last_page or not rows:
            break
        page += 1

    out_lines = [f"评论数: {len(all_comments)}"]
    if len(all_comments) >= max_all:
        out_lines[0] += f" (已达上限 {max_all})"
    for idx, c in enumerate(all_comments, start=1):
        ts = format_ts(c.get("timestamp", 0)) if c.get("timestamp") else "?"
        text = (c.get("text") or "").replace("\n", " ").strip()
        tag = c.get("name_tag") or c.get("name") or "Anonymous"
        out_lines.append(f"{idx:03d}. [{tag}] {ts}  {text}")
    _write_output("\n".join(out_lines), args.output)
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    key = args.key.replace("-", "_")
    if key not in HARD_DEFAULTS:
        print(f"不支持的配置项: {args.key}，可用: {', '.join(HARD_DEFAULTS)}")
        return 1
    if args.value < 1:
        print(f"{key} 必须为正整数")
        return 1
    defaults = profile.get("defaults", {})
    defaults[key] = args.value
    profile["defaults"] = defaults
    save_profile(args.profile_file, profile)
    help_text = HARD_DEFAULTS_HELP.get(key, "")
    print(f"已设置 {key} ({help_text}) = {args.value}")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    defaults = profile.get("defaults", {})
    if args.key:
        key = args.key.replace("-", "_")
        if key in HARD_DEFAULTS:
            val = defaults.get(key, HARD_DEFAULTS[key])
            help_text = HARD_DEFAULTS_HELP.get(key, "")
            print(f"{key} ({help_text}) = {val}")
        else:
            print(f"未知配置项: {args.key}，可用: {', '.join(HARD_DEFAULTS)}")
            return 1
    else:
        print("当前配置:")
        print(f"  profile: {args.profile_file}")
        for k, v in HARD_DEFAULTS.items():
            help_text = HARD_DEFAULTS_HELP.get(k, "")
            print(f"  {k} ({help_text}) = {defaults.get(k, v)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="treehole-cli",
        description="CLI for PKU Treehole authentication and search",
        add_help=False,
    )
    parser.add_argument("--profile-file", default=DEFAULT_PROFILE, help="profile json path")
    parser.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")

    subparsers = parser.add_subparsers(dest="command")

    p_init = subparsers.add_parser("init", help="初始化配置并登录", add_help=False)
    p_init.add_argument("--username", help="学号，不填则交互输入")
    p_init.add_argument("--cookies-file", help="cookie 文件路径")
    p_init.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_init.set_defaults(func=cmd_init)

    p_login = subparsers.add_parser("login", help="使用账号密码重新登录", add_help=False)
    p_login.add_argument("--username", help="学号，不填则读取 profile 或交互输入")
    p_login.add_argument("--cookies-file", help="cookie 文件路径")
    p_login.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_login.set_defaults(func=cmd_login)

    p_whoami = subparsers.add_parser("whoami", help="查看当前登录状态", add_help=False)
    p_whoami.add_argument("--cookies-file", help="cookie 文件路径")
    p_whoami.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_whoami.set_defaults(func=cmd_whoami)

    p_search = subparsers.add_parser("search", help="按关键词搜索帖子", add_help=False)
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--page", type=int, default=1)
    p_search.add_argument("--limit", type=int, default=_UNSET, help="每页条数 (默认值见 thcli get)")
    p_search.add_argument("--comment-limit", type=int, default=_UNSET, help="每帖附带评论数 (默认值见 thcli get)")
    p_search.add_argument("--all", action="store_true", help="翻页拉取全部结果，上限见 thcli get all_limit")
    p_search.add_argument("-c", "--compact", action="store_true", help="紧凑输出（无评论，一行一帖）")
    p_search.add_argument("--cookies-file", help="cookie 文件路径")
    p_search.add_argument("-o", "--output", help="输出结果写入文件")
    p_search.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_search.set_defaults(func=cmd_search)

    p_post = subparsers.add_parser("post", help="获取帖子详情", add_help=False)
    p_post.add_argument("pid", type=int, help="帖子 ID")
    p_post.add_argument("--with-comments", action="store_true", help="同时拉取评论")
    p_post.add_argument("--comment-limit", type=int, default=_UNSET, help="评论总数上限 (默认值见 thcli get)")
    p_post.add_argument("--cookies-file", help="cookie 文件路径")
    p_post.add_argument("-o", "--output", help="输出结果写入文件")
    p_post.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_post.set_defaults(func=cmd_post)

    p_comments = subparsers.add_parser("comments", help="获取帖子评论", add_help=False)
    p_comments.add_argument("pid", type=int, help="帖子 ID")
    p_comments.add_argument("--page", type=int, default=1)
    p_comments.add_argument("--limit", type=int, default=_UNSET, help="每页条数 (默认值见 thcli get)")
    p_comments.add_argument("--sort", choices=["asc", "desc"], default="asc")
    p_comments.add_argument("--all", action="store_true", help="拉取全部页")
    p_comments.add_argument("--cookies-file", help="cookie 文件路径")
    p_comments.add_argument("-o", "--output", help="输出结果写入文件")
    p_comments.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_comments.set_defaults(func=cmd_comments)

    p_set = subparsers.add_parser("set", help="持久化修改默认参数", add_help=False)
    p_set.add_argument("key", help=f"配置项 ({'/'.join(HARD_DEFAULTS)})")
    p_set.add_argument("value", type=int, help="值")
    p_set.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_set.set_defaults(func=cmd_set)

    p_get = subparsers.add_parser("get", help="查看当前配置", add_help=False)
    p_get.add_argument("key", nargs="?", help="配置项，不填则显示全部")
    p_get.add_argument("--help", action="help", default=argparse.SUPPRESS, help="显示帮助信息")
    p_get.set_defaults(func=cmd_get)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
