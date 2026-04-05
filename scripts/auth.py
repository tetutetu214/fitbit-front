"""Fitbit OAuth 2.0 PKCE認可フロー（2ステップ方式）

使い方:
  Step 1: python scripts/auth.py
    → 認可URLを表示し、code_verifierをファイルに保存
  Step 2: python scripts/auth.py <認可コード>
    → トークン交換してtokens.jsonに保存
"""
import base64
import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
TOKENS_FILE = DATA_DIR / "tokens.json"
PKCE_FILE = DATA_DIR / "pkce_verifier.txt"
REDIRECT_URI = "https://localhost"

SCOPES = [
    "heartrate",
    "sleep",
    "activity",
    "oxygen_saturation",
    "respiratory_rate",
    "temperature",
    "weight",
    "profile",
]


def generate_pkce():
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def build_auth_url(client_id: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "scope": " ".join(SCOPES),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT_URI,
    }
    return f"https://www.fitbit.com/oauth2/authorize?{urlencode(params)}"


def exchange_code(client_id: str, client_secret: str, code: str, code_verifier: str) -> dict:
    resp = requests.post(
        "https://api.fitbit.com/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": code_verifier,
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
        },
        auth=(client_id, client_secret),
    )
    if resp.status_code != 200:
        print(f"エラー ({resp.status_code}): {resp.text}")
        sys.exit(1)
    return resp.json()


def save_tokens(token_data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"トークンを {TOKENS_FILE} に保存しました")


def step1_generate_url():
    """Step 1: 認可URLを生成し、code_verifierを保存"""
    client_id = os.environ.get("FITBIT_CLIENT_ID")
    if not client_id:
        print("エラー: .env に FITBIT_CLIENT_ID を設定してください")
        sys.exit(1)

    code_verifier, code_challenge = generate_pkce()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(PKCE_FILE, "w") as f:
        f.write(code_verifier)

    auth_url = build_auth_url(client_id, code_challenge)
    print("\n=== Step 1: 以下のURLをブラウザで開いて認可してください ===")
    print(f"\n{auth_url}\n")
    print("認可後、アドレスバーのURLから code= の値をコピーして、以下を実行：")
    print("  python scripts/auth.py <認可コード>\n")


def step2_exchange(auth_code: str):
    """Step 2: 認可コードでトークン交換"""
    client_id = os.environ.get("FITBIT_CLIENT_ID")
    client_secret = os.environ.get("FITBIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("エラー: .env に FITBIT_CLIENT_ID と FITBIT_CLIENT_SECRET を設定してください")
        sys.exit(1)

    if not PKCE_FILE.exists():
        print("エラー: 先に引数なしで auth.py を実行してください（Step 1）")
        sys.exit(1)

    code_verifier = PKCE_FILE.read_text().strip()

    print("トークンを取得中...")
    token_data = exchange_code(client_id, client_secret, auth_code, code_verifier)
    save_tokens(token_data)

    PKCE_FILE.unlink()
    print("認可が完了しました")


def main():
    if len(sys.argv) >= 2:
        auth_code = sys.argv[1].strip().rstrip("#_=_").strip()
        step2_exchange(auth_code)
    else:
        step1_generate_url()


if __name__ == "__main__":
    main()
