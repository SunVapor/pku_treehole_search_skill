from src import TreeholeClient


def main() -> None:
    client = TreeholeClient(cookies_file="./user_cookies/demo.json")

    # 如果已有可用 cookie，可省略账号密码。
    if not client.ensure_login(username="你的学号", password="你的密码", interactive=True):
        print("登录失败")
        return

    result = client.search_posts(keyword="选课", limit=5, comment_limit=3)
    print("success:", result.get("success"))
    print("message:", result.get("message"))

    rows = result.get("data", {}).get("data", [])
    for i, post in enumerate(rows, start=1):
        print(f"{i}. #{post.get('pid')} {str(post.get('text', ''))[:50]}")


if __name__ == "__main__":
    main()
