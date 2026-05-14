"""Minimal PKU Treehole API client focused on authentication and search."""

from __future__ import annotations

import json
import os
import random
import re
import uuid
from dataclasses import dataclass
from http.cookiejar import Cookie
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class TreeholeEndpoints:
    oauth_login: str = "https://iaaa.pku.edu.cn/iaaa/oauthlogin.do"
    redir_url: str = "https://treehole.pku.edu.cn/cas_iaaa_login?uuid=fc71db5799cf&plat=web"
    sso_login: str = "http://treehole.pku.edu.cn/cas_iaaa_login"
    unread: str = "https://treehole.pku.edu.cn/api/mail/un_read"
    login_by_token: str = "https://treehole.pku.edu.cn/api/login_iaaa_check_token"
    login_by_message: str = "https://treehole.pku.edu.cn/api/jwt_msg_verify"
    send_message: str = "https://treehole.pku.edu.cn/api/jwt_send_msg"
    get_post: str = "https://treehole.pku.edu.cn/api/pku/{post_id}"
    get_comment: str = "https://treehole.pku.edu.cn/api/pku_comment_v3/{post_id}"
    search_posts: str = "https://treehole.pku.edu.cn/chapi/api/v3/hole/list_comments"


class TreeholeClient:
    """Client for PKU Treehole interaction only (auth/search/post/comment)."""

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        user_agent: str = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
        ),
    ) -> None:
        self.session = requests.Session()
        self.endpoints = TreeholeEndpoints()
        self.cookies_file = cookies_file or os.path.expanduser("~/.treehole_cookies.json")
        self.authorization: Optional[str] = None

        self.session.headers.update({"user-agent": user_agent})
        self.load_cookies()
        self._sync_auth_header_from_cookie()

    def _sync_auth_header_from_cookie(self) -> None:
        token = self.session.cookies.get("pku_token")
        if token:
            self.authorization = token
            self.session.headers.update({"authorization": f"Bearer {token}"})

    def oauth_login(self, username: str, password: str) -> Dict[str, Any]:
        response = self.session.post(
            self.endpoints.oauth_login,
            data={
                "appid": "PKU Helper",
                "userName": username,
                "password": password,
                "randCode": "",
                "smsCode": "",
                "otpCode": "",
                "redirUrl": self.endpoints.redir_url,
            },
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def sso_login(self, token: str) -> requests.Response:
        response = self.session.get(
            self.endpoints.sso_login,
            params={
                "uuid": str(uuid.uuid4()).split("-")[-1],
                "plat": "web",
                "_rand": str(random.random()),
                "token": token,
            },
            timeout=20,
        )
        response.raise_for_status()

        m = re.search(r"token=(.*)", response.url)
        if not m:
            raise RuntimeError("Cannot parse token from SSO redirect URL")

        self.authorization = m.group(1)
        self.session.cookies.update({"pku_token": self.authorization})
        self.session.headers.update({"authorization": f"Bearer {self.authorization}"})
        return response

    def un_read(self) -> requests.Response:
        return self.session.get(self.endpoints.unread, timeout=20)

    def send_message(self) -> requests.Response:
        response = self.session.post(self.endpoints.send_message, timeout=20)
        response.raise_for_status()
        return response

    def login_by_message(self, code: str) -> requests.Response:
        response = self.session.post(
            self.endpoints.login_by_message,
            data={"valid_code": code},
            timeout=20,
        )
        response.raise_for_status()

        body = response.json()
        token = body.get("token")
        if body.get("success") and token:
            self.authorization = token
            self.session.cookies.update({"pku_token": token})
            self.session.headers.update({"authorization": f"Bearer {token}"})

        return response

    def login_by_token(self, token_or_code: str) -> requests.Response:
        response = self.session.post(
            self.endpoints.login_by_token,
            data={"code": token_or_code},
            timeout=20,
        )
        response.raise_for_status()

        body = response.json()
        token = None
        if body.get("success"):
            token = body.get("token")
            if not token and isinstance(body.get("data"), dict):
                token = body["data"].get("token")

        if token:
            self.authorization = token
            self.session.cookies.update({"pku_token": token})
            self.session.headers.update({"authorization": f"Bearer {token}"})

        return response

    def get_post(self, post_id: int) -> Dict[str, Any]:
        response = self.session.get(
            self.endpoints.get_post.format(post_id=post_id),
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def get_comment(self, post_id: int, page: int = 1, limit: int = 15, sort: str = "asc") -> Dict[str, Any]:
        response = self.session.get(
            self.endpoints.get_comment.format(post_id=post_id),
            params={"page": page, "limit": limit, "sort": sort},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def search_posts(
        self,
        keyword: str,
        page: int = 1,
        limit: int = 30,
        comment_limit: int = 10,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        params = {
            "page": page,
            "limit": limit,
            "comment_limit": comment_limit,
            "keyword": keyword,
        }
        params.update(kwargs)

        response = self.session.get(self.endpoints.search_posts, params=params, timeout=20)
        response.raise_for_status()
        raw = response.json()

        if raw.get("code") != 20000:
            return {
                "success": False,
                "message": raw.get("message", "Unknown error"),
                "code": raw.get("code"),
                "data": {"data": [], "total": 0, "page": page, "limit": limit, "last_page": 0},
            }

        rows = raw.get("data", {}).get("list", [])
        for row in rows:
            row["comments"] = row.get("comment_list") or []

        total = raw.get("data", {}).get("total", 0)
        return {
            "success": True,
            "message": raw.get("message", "success"),
            "data": {
                "data": rows,
                "total": total,
                "page": page,
                "limit": limit,
                "last_page": (total + limit - 1) // limit if limit > 0 else 1,
            },
        }

    def save_cookies(self) -> None:
        cookies: list[Dict[str, Any]] = []
        for c in self.session.cookies:
            cookies.append(
                {
                    "name": c.name,
                    "value": c.value,
                    "domain": c.domain,
                    "path": c.path,
                    "expires": c.expires if c.expires else None,
                    "secure": c.secure,
                    "rest": {"HttpOnly": c.has_nonstandard_attr("HttpOnly")},
                }
            )

        with open(self.cookies_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

    def load_cookies(self) -> None:
        try:
            with open(self.cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
        except FileNotFoundError:
            return

        self.session.cookies.clear()
        for c in cookies:
            cookie = Cookie(
                version=0,
                name=c["name"],
                value=c["value"],
                port=None,
                port_specified=False,
                domain=c["domain"],
                domain_specified=bool(c["domain"]),
                domain_initial_dot=c["domain"].startswith("."),
                path=c["path"],
                path_specified=bool(c["path"]),
                secure=c["secure"],
                expires=c["expires"],
                discard=False,
                comment=None,
                comment_url=None,
                rest=c.get("rest", {}),
            )
            self.session.cookies.set_cookie(cookie)

    def ensure_login(self, username: Optional[str] = None, password: Optional[str] = None, interactive: bool = True) -> bool:
        """Ensure login state, optionally completing SMS/token verification interactively."""
        status = self.un_read()
        if status.status_code == 200 and status.json().get("success"):
            return True

        if not (username and password):
            return False

        result = self.oauth_login(username, password)
        if result.get("success") not in (True, "true"):
            return False

        token = result.get("token")
        if not token:
            return False
        self.sso_login(token)

        for _ in range(5):
            probe = self.un_read().json()
            if probe.get("success"):
                self.save_cookies()
                return True

            msg = probe.get("message", "")
            if msg == "请手机短信验证":
                if not interactive:
                    return False
                want = input("Send verification code (Y/n): ").strip().lower()
                if want != "y":
                    return False
                self.send_message()
                code = input("SMS verification code: ").strip()
                self.login_by_message(code)
                continue

            if msg == "请进行令牌验证":
                if not interactive:
                    return False
                code = input("Mobile token code: ").strip()
                self.login_by_token(code)
                continue

            return False

        return False
