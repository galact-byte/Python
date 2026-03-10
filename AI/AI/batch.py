import json
import os
import re
import random
import time
import secrets
import hashlib
import base64
import urllib
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass
from typing import Any, Dict

from curl_cffi import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env2"))

# ===== 配置区（从 .env2 读取）=====
PROXY = os.getenv("PROXY", "127.0.0.1:7890")
CPA_BASE_URL = os.getenv("CPA_BASE_URL", "http://127.0.0.1:8317")
CPA_MANAGEMENT_KEY = os.getenv("CPA_MANAGEMENT_KEY", "")
MAIL_API_KEY = os.getenv("MAIL_API_KEY")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "accounts.json")
if not MAIL_API_KEY:
    raise RuntimeError("请在 .env2 中设置 MAIL_API_KEY")
# ==================================


# ===== 邮箱 API =====
def get(url: str, headers: dict | None = None) -> tuple[str, dict]:
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req) as response:
            resp_text = response.read().decode("utf-8")
            resp_headers = dict(response.getheaders())
            return resp_text, resp_headers
    except Exception as e:
        print(f"[get] 请求失败: {e}")
        return "", {}


def get_email() -> str:
    for attempt in range(5):
        body, _ = get("https://mail.chatgpt.org.uk/api/generate-email",
                      {"X-API-Key": MAIL_API_KEY, "User-Agent": "Mozilla/5.0"})
        if not body or body.strip().startswith("<"):
            print(f"[get_email] 第{attempt+1}次尝试失败，等待3s...")
            time.sleep(3)
            continue
        try:
            data = json.loads(body)
            return data["data"]["email"]
        except Exception as e:
            print(f"[get_email] 解析失败: {e}, body={body[:100]}")
            time.sleep(3)
    raise RuntimeError("获取邮箱失败，请检查邮箱API")


def get_oai_code(email: str) -> str:
    regex = r"(?<!\d)(\d{6})(?!\d)"
    for i in range(20):
        body, _ = get(f"https://mail.chatgpt.org.uk/api/emails?email={email}",
                      {"referer": "https://mail.chatgpt.org.uk/", "User-Agent": "Mozilla/5.0"})
        if not body or body.strip().startswith("<"):
            time.sleep(3)
            continue
        try:
            data = json.loads(body)
            emails = data["data"]["emails"]
            for mail in emails:
                if "openai" in mail.get("from_address", ""):
                    m = re.search(regex, mail.get("subject", ""))
                    if m:
                        return m.group(1)
                    m = re.search(regex, mail.get("html_content", ""))
                    if m:
                        return m.group(1)
        except Exception as e:
            print(f"[get_oai_code] 解析失败: {e}")
        print(f"[get_oai_code] 等待验证码... ({i+1}/20)")
        time.sleep(3)
    raise RuntimeError("获取验证码超时")


# ===== OAuth =====
AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_REDIRECT_URI = "http://localhost:1455/auth/callback"
DEFAULT_SCOPE = "openid email profile offline_access"


def _b64url_no_pad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _sha256_b64url_no_pad(s: str) -> str:
    return _b64url_no_pad(hashlib.sha256(s.encode("ascii")).digest())


def _pkce_verifier() -> str:
    return secrets.token_urlsafe(64)


def _random_state(nbytes: int = 16) -> str:
    return secrets.token_urlsafe(nbytes)


def _parse_callback_url(callback_url: str) -> Dict[str, str]:
    candidate = callback_url.strip()
    if not candidate:
        return {"code": "", "state": "", "error": "", "error_description": ""}
    if "://" not in candidate:
        if "=" in candidate:
            candidate = f"http://localhost/?{candidate}"
        else:
            candidate = f"http://{candidate}"
    parsed = urllib.parse.urlparse(candidate)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fragment = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)
    for key, values in fragment.items():
        if key not in query or not query[key]:
            query[key] = values

    def get1(k):
        v = query.get(k, [""])
        return (v[0] or "").strip()

    return {
        "code": get1("code"),
        "state": get1("state"),
        "error": get1("error"),
        "error_description": get1("error_description"),
    }


def _jwt_claims_no_verify(id_token: str) -> Dict[str, Any]:
    if not id_token or id_token.count(".") < 2:
        return {}
    payload_b64 = id_token.split(".")[1]
    pad = "=" * ((4 - (len(payload_b64) % 4)) % 4)
    try:
        payload = base64.urlsafe_b64decode((payload_b64 + pad).encode("ascii"))
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {}


def _post_form(url: str, data: Dict[str, str], timeout: int = 30) -> Dict[str, Any]:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        raise RuntimeError(f"token exchange failed: {exc.code}: {raw.decode('utf-8', 'replace')}") from exc


@dataclass(frozen=True)
class OAuthStart:
    auth_url: str
    state: str
    code_verifier: str
    redirect_uri: str


def generate_oauth_url(*, redirect_uri: str = DEFAULT_REDIRECT_URI, scope: str = DEFAULT_SCOPE) -> OAuthStart:
    state = _random_state()
    code_verifier = _pkce_verifier()
    code_challenge = _sha256_b64url_no_pad(code_verifier)
    params = {
        "client_id": CLIENT_ID, "response_type": "code",
        "redirect_uri": redirect_uri, "scope": scope,
        "state": state, "code_challenge": code_challenge,
        "code_challenge_method": "S256", "prompt": "login",
        "id_token_add_organizations": "true", "codex_cli_simplified_flow": "true",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return OAuthStart(auth_url=auth_url, state=state, code_verifier=code_verifier, redirect_uri=redirect_uri)


def submit_callback_url(*, callback_url: str, expected_state: str, code_verifier: str,
                        redirect_uri: str = DEFAULT_REDIRECT_URI) -> dict:
    cb = _parse_callback_url(callback_url)
    if cb["error"]:
        raise RuntimeError(f"oauth error: {cb['error']}: {cb['error_description']}".strip())
    if not cb["code"]:
        raise ValueError("callback url missing ?code=")
    if cb["state"] != expected_state:
        raise ValueError("state mismatch")

    token_resp = _post_form(TOKEN_URL, {
        "grant_type": "authorization_code", "client_id": CLIENT_ID,
        "code": cb["code"], "redirect_uri": redirect_uri, "code_verifier": code_verifier,
    })

    access_token = (token_resp.get("access_token") or "").strip()
    refresh_token = (token_resp.get("refresh_token") or "").strip()
    id_token = (token_resp.get("id_token") or "").strip()
    expires_in = int(token_resp.get("expires_in") or 0)

    claims = _jwt_claims_no_verify(id_token)
    email = str(claims.get("email") or "").strip()
    auth_claims = claims.get("https://api.openai.com/auth") or {}
    account_id = str(auth_claims.get("chatgpt_account_id") or "").strip()

    now = int(time.time())
    expired_rfc3339 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now + max(expires_in, 0)))
    now_rfc3339 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

    return {
        "id_token": id_token,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "account_id": account_id,
        "last_refresh": now_rfc3339,
        "email": email,
        "type": "codex",
        "expired": expired_rfc3339,
    }


def random_name() -> str:
    first_names = [
        "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
        "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Susan",
        "Jessica", "Sarah", "Karen", "Lisa", "Emma", "Olivia", "Noah", "Liam", "Sophia",
        "Ava", "Isabella", "Mia", "Charlotte", "Amelia", "Lucas", "Mason", "Ethan", "Logan"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
        "Wilson", "Taylor", "Anderson", "Thomas", "Jackson", "White", "Harris", "Martin",
        "Thompson", "Young", "Robinson", "Walker", "Allen", "King", "Scott", "Green", "Baker"
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"


def random_birthdate() -> str:
    # 年龄范围 18~45 岁
    year = random.randint(1980, 2006)
    month = random.randint(1, 12)
    max_day = 28 if month == 2 else 30 if month in (4, 6, 9, 11) else 31
    day = random.randint(1, max_day)
    return f"{year}-{month:02d}-{day:02d}"



def register_one(proxy: str) -> dict:
    s = requests.Session(
        proxies={"http": proxy, "https": proxy},
        impersonate="chrome"
    )

    # 检查代理
    trace = s.get("https://cloudflare.com/cdn-cgi/trace", timeout=10).text
    loc = re.search(r"^loc=(.+)$", trace, re.MULTILINE)
    ip = re.search(r"^ip=(.+)$", trace, re.MULTILINE)
    loc = loc.group(1) if loc else None
    ip = ip.group(1) if ip else None
    print(f"  IP: {loc} {ip}")
    if loc in ("CN", "HK"):
        raise RuntimeError("代理IP为CN/HK，请检查代理")

    email = get_email()
    print(f"  邮箱: {email}")

    oauth = generate_oauth_url()
    s.get(oauth.auth_url)
    did = s.cookies.get("oai-did")
    print(f"  did: {did}")

    # Sentinel
    sen_req_body = f'{{"p":"","id":"{did}","flow":"authorize_continue"}}'
    sen_resp = s.post(
        "https://sentinel.openai.com/backend-api/sentinel/req",
        headers={
            "origin": "https://sentinel.openai.com",
            "referer": "https://sentinel.openai.com/backend-api/sentinel/frame.html?sv=20260219f9f6",
            "content-type": "text/plain;charset=UTF-8"
        },
        data=sen_req_body
    )
    print(f"  sentinel: {sen_resp.status_code}")
    sen_token = sen_resp.json()["token"]
    sentinel = f'{{"p": "", "t": "", "c": "{sen_token}", "id": "{did}", "flow": "authorize_continue"}}'

    # 注册
    signup_body = f'{{"username":{{"value":"{email}","kind":"email"}},"screen_hint":"signup"}}'
    signup_resp = s.post(
        "https://auth.openai.com/api/accounts/authorize/continue",
        headers={"referer": "https://auth.openai.com/create-account",
                 "accept": "application/json", "content-type": "application/json",
                 "openai-sentinel-token": sentinel},
        data=signup_body
    )
    print(f"  signup: {signup_resp.status_code}")

    otp_resp = s.post(
        "https://auth.openai.com/api/accounts/passwordless/send-otp",
        headers={"referer": "https://auth.openai.com/create-account/password",
                 "accept": "application/json", "content-type": "application/json"}
    )
    print(f"  send-otp: {otp_resp.status_code}")

    code = get_oai_code(email)
    print(f"  验证码: {code}")

    code_resp = s.post(
        "https://auth.openai.com/api/accounts/email-otp/validate",
        headers={"referer": "https://auth.openai.com/email-verification",
                 "accept": "application/json", "content-type": "application/json"},
        data=f'{{"code":"{code}"}}'
    )
    print(f"  validate-otp: {code_resp.status_code}")

    name = random_name()
    birthdate = random_birthdate()
    create_resp = s.post(
        "https://auth.openai.com/api/accounts/create_account",
        headers={"referer": "https://auth.openai.com/about-you",
                 "accept": "application/json", "content-type": "application/json"},
        data=json.dumps({"name": name, "birthdate": birthdate})
    )
    print(f"  create_account: {create_resp.status_code}")
    if create_resp.status_code != 200:
        raise RuntimeError(f"create_account 失败: {create_resp.text}")

    auth_cookie = s.cookies.get("oai-client-auth-session")
    auth_data = json.loads(base64.b64decode(auth_cookie.split(".")[0]))
    workspace_id = auth_data["workspaces"][0]["id"]
    print(f"  workspace_id: {workspace_id}")

    select_resp = s.post(
        "https://auth.openai.com/api/accounts/workspace/select",
        headers={"referer": "https://auth.openai.com/sign-in-with-chatgpt/codex/consent",
                 "content-type": "application/json"},
        data=f'{{"workspace_id":"{workspace_id}"}}'
    )
    print(f"  select_workspace: {select_resp.status_code}")
    continue_url = select_resp.json()["continue_url"]

    r1 = s.get(continue_url, allow_redirects=False)
    r2 = s.get(r1.headers.get("Location"), allow_redirects=False)
    r3 = s.get(r2.headers.get("Location"), allow_redirects=False)
    cbk = r3.headers.get("Location")

    return submit_callback_url(
        callback_url=cbk,
        code_verifier=oauth.code_verifier,
        redirect_uri=oauth.redirect_uri,
        expected_state=oauth.state
    )


# ===== 导入 CLIProxyAPI =====
def import_to_cpa(account: dict) -> bool:
    auth_dir = os.getenv("CPA_AUTH_DIR", os.path.join(os.path.expanduser("~"), ".cli-proxy-api"))
    try:
        auth_dir = os.path.expanduser(auth_dir)
        os.makedirs(auth_dir, exist_ok=True)
        email = account.get("email", "account")
        safe_name = re.sub(r'[^\w@.-]', '_', email)
        filename = os.path.join(auth_dir, f"{safe_name}.json")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(account, f, ensure_ascii=False, indent=2)
        print(f"  导入CPA: 已写入 {filename}")
        return True
    except Exception as e:
        print(f"  导入CPA失败: {e}")
        return False


# ===== 保存逻辑 =====
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_DIR = os.path.join(SCRIPT_DIR, "accounts")


def save_account(account: dict, split_mode: bool, index: int):
    """split_mode=True 每个账号单独一个 json 文件，False 全部追加到 OUTPUT_FILE"""
    if split_mode:
        os.makedirs(ACCOUNTS_DIR, exist_ok=True)
        email = account.get("email", f"account_{index}")
        safe_name = re.sub(r'[^\w@.-]', '_', email)
        filepath = os.path.join(ACCOUNTS_DIR, f"{safe_name}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(account, f, ensure_ascii=False, indent=2)
        print(f"  💾 已保存到 accounts/{safe_name}.json")
    else:
        output_path = os.path.join(SCRIPT_DIR, OUTPUT_FILE)
        results = []
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as f:
                results = json.load(f)
        results.append(account)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"  💾 已保存到 {OUTPUT_FILE}（共 {len(results)} 条）")


# ===== 拆分已有 JSON =====
def split_existing_json():
    while True:
        filepath = input("请输入要拆分的 JSON 文件路径（直接回车取消）：").strip()
        if not filepath:
            print("已取消")
            return
        if not os.path.exists(filepath):
            print(f"  ❌ 文件不存在：{filepath}")
            continue
        break

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 兼容单个账号（dict）和多个账号（list）
    if isinstance(data, dict):
        accounts = [data]
    elif isinstance(data, list):
        accounts = data
    else:
        print("❌ 无法识别的 JSON 格式，应为对象或数组")
        return

    print(f"共检测到 {len(accounts)} 个账号，开始拆分...")

    # 选择输出目录
    out_dir = input("请输入输出目录（直接回车则保存到当前目录）：").strip()
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
        print(f"  已创建目录：{out_dir}")

    success = 0
    for i, account in enumerate(accounts):
        email = account.get("email", f"account_{i+1}")
        safe_name = re.sub(r'[^\w@.-]', '_', email)
        filename = f"{safe_name}.json"
        if out_dir:
            filename = os.path.join(out_dir, filename)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(account, f, ensure_ascii=False, indent=2)
        print(f"  💾 {email} -> {filename}")
        success += 1

    print(f"\n✅ 拆分完成，共输出 {success} 个文件")


# ===== 主程序 =====
def main():
    print("========== ChatGPT 批量注册工具 ==========")
    print("请选择运行模式：")
    print("  1. 批量注册账号")
    print("  2. 拆分已有 JSON 文件")
    while True:
        mode = input("请输入 1 或 2：").strip()
        if mode in ("1", "2"):
            break
        print("  请输入 1 或 2")

    if mode == "2":
        split_existing_json()
        return

    # 模式1：批量注册
    print()
    print(f"代理: {PROXY}")
    print(f"CPA地址: {CPA_BASE_URL}")
    print(f"CPA Key: {'已设置' if CPA_MANAGEMENT_KEY else '⚠️ 未设置'}")
    print()

    # 询问注册数量
    while True:
        try:
            count = int(input("请输入要注册的账号数量：").strip())
            if count > 0:
                break
            print("  请输入大于0的整数")
        except ValueError:
            print("  请输入有效的整数")

    # 询问存储方式
    print("请选择保存方式：")
    print("  1. 所有账号保存到一个 JSON 文件（accounts.json）")
    print("  2. 每个账号单独保存为一个 JSON 文件（以邮箱命名）")
    while True:
        choice = input("请输入 1 或 2：").strip()
        if choice in ("1", "2"):
            break
        print("  请输入 1 或 2")
    split_mode = (choice == "2")
    print(f"已选择：{'每个账号单独文件' if split_mode else '所有账号合并到一个文件'}\n")

    success = 0
    fail = 0

    for i in range(count):
        print(f"========== 第 {i+1}/{count} 个 ==========")
        try:
            account = register_one(PROXY)
            print(f"  ✅ 注册成功: {account.get('email')}")

            imported = import_to_cpa(account)
            account["imported_to_cpa"] = imported

            save_account(account, split_mode, i + 1)
            success += 1

        except Exception as e:
            print(f"  ❌ 失败: {e}")
            fail += 1

        if i < count - 1:
            print(f"  等待5s后继续...")
            time.sleep(5)

    print(f"\n========== 完成 ==========")
    print(f"成功: {success}，失败: {fail}")


if __name__ == "__main__":
    main()
