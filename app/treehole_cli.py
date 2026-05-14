#!/usr/bin/env python3
"""Interactive CLI for treehole-search-skill."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from src import TreeholeClient

DEFAULT_PROFILE = os.path.expanduser("~/.treehole_search_skill.json")
DEFAULT_COOKIES = os.path.expanduser("~/.treehole_cookies.json")


def load_profile(profile_file: str) -> Dict[str, Any]:
    path = Path(profile_file)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile_file: str, profile: Dict[str, Any]) -> None:
    path = Path(profile_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)


def resolve_cookies_file(args: argparse.Namespace, profile: Dict[str, Any]) -> str:
    if getattr(args, "cookies_file", None):
        return os.path.expanduser(args.cookies_file)
    if profile.get("cookies_file"):
        return os.path.expanduser(profile["cookies_file"])
    return DEFAULT_COOKIES


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
    print("当前未登录，请先运行: python treehole_cli.py init")
    return False


def cmd_init(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)

    username = args.username or input("学号: ").strip()
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
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)
    client = TreeholeClient(cookies_file=cookies_file)

    if not is_logged_in(client):
        print("未登录")
        return 1

    username = profile.get("username", "(unknown)")
    print("登录状态: 已登录")
    print(f"用户: {username}")
    print(f"cookie: {cookies_file}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)
    client = TreeholeClient(cookies_file=cookies_file)

    if not ensure_authenticated(client):
        return 1

    result = client.search_posts(
        keyword=args.keyword,
        page=args.page,
        limit=args.limit,
        comment_limit=args.comment_limit,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("success") else 1

    if not result.get("success"):
        print(f"搜索失败: {result.get('message')}")
        return 1

    rows = result.get("data", {}).get("data", [])
    total = result.get("data", {}).get("total", 0)
    print(f"关键词: {args.keyword}")
    print(f"返回: {len(rows)} 条，总计: {total}")
    for idx, post in enumerate(rows, start=1):
        text = (post.get("text") or "").replace("\n", " ").strip()
        print(f"{idx:02d}. #{post.get('pid')} {text[:90]}")
    return 0


def cmd_post(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)
    client = TreeholeClient(cookies_file=cookies_file)

    if not ensure_authenticated(client):
        return 1

    try:
        data = client.get_post(args.pid)
    except Exception as e:
        print(f"获取帖子失败: {e}")
        return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    post = data.get("data") or {}
    print(f"PID: {post.get('pid', args.pid)}")
    print(f"回复数: {post.get('reply')}  点赞数: {post.get('likenum')}")
    print("-" * 40)
    print(post.get("text", ""))
    return 0


def cmd_comments(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile_file)
    cookies_file = resolve_cookies_file(args, profile)
    client = TreeholeClient(cookies_file=cookies_file)

    if not ensure_authenticated(client):
        return 1

    all_comments = []
    page = args.page
    while True:
        try:
            data = client.get_comment(args.pid, page=page, limit=args.limit, sort=args.sort)
        except Exception as e:
            print(f"获取评论失败: {e}")
            return 1

        rows = (data.get("data") or {}).get("data") or []
        all_comments.extend(rows)

        if not args.all:
            break

        last_page = (data.get("data") or {}).get("last_page") or page
        if page >= last_page:
            break
        page += 1

    if args.json:
        print(json.dumps(all_comments, ensure_ascii=False, indent=2))
        return 0

    print(f"评论数: {len(all_comments)}")
    for idx, c in enumerate(all_comments, start=1):
        text = (c.get("text") or "").replace("\n", " ").strip()
        tag = c.get("name_tag", "Anonymous")
        print(f"{idx:03d}. [{tag}] {text[:100]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="treehole-cli",
        description="CLI for PKU Treehole authentication and search",
    )
    parser.add_argument("--profile-file", default=DEFAULT_PROFILE, help="profile json path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser("init", help="初始化配置并登录")
    p_init.add_argument("--username", help="学号，不填则交互输入")
    p_init.add_argument("--cookies-file", help="cookie 文件路径")
    p_init.set_defaults(func=cmd_init)

    p_login = subparsers.add_parser("login", help="使用账号密码重新登录")
    p_login.add_argument("--username", help="学号，不填则读取 profile 或交互输入")
    p_login.add_argument("--cookies-file", help="cookie 文件路径")
    p_login.set_defaults(func=cmd_login)

    p_whoami = subparsers.add_parser("whoami", help="查看当前登录状态")
    p_whoami.add_argument("--cookies-file", help="cookie 文件路径")
    p_whoami.set_defaults(func=cmd_whoami)

    p_search = subparsers.add_parser("search", help="按关键词搜索帖子")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("--page", type=int, default=1)
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--comment-limit", type=int, default=3)
    p_search.add_argument("--cookies-file", help="cookie 文件路径")
    p_search.add_argument("--json", action="store_true", help="输出完整 JSON")
    p_search.set_defaults(func=cmd_search)

    p_post = subparsers.add_parser("post", help="获取帖子详情")
    p_post.add_argument("pid", type=int, help="帖子 ID")
    p_post.add_argument("--cookies-file", help="cookie 文件路径")
    p_post.add_argument("--json", action="store_true", help="输出完整 JSON")
    p_post.set_defaults(func=cmd_post)

    p_comments = subparsers.add_parser("comments", help="获取帖子评论")
    p_comments.add_argument("pid", type=int, help="帖子 ID")
    p_comments.add_argument("--page", type=int, default=1)
    p_comments.add_argument("--limit", type=int, default=20)
    p_comments.add_argument("--sort", choices=["asc", "desc"], default="asc")
    p_comments.add_argument("--all", action="store_true", help="拉取全部页")
    p_comments.add_argument("--cookies-file", help="cookie 文件路径")
    p_comments.add_argument("--json", action="store_true", help="输出完整 JSON")
    p_comments.set_defaults(func=cmd_comments)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
