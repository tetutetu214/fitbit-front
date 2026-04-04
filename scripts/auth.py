"""Fitbit OAuth 2.0 PKCE認可フロー"""
import base64
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlencode

import requests

DATA_DIR = Path("/app/data")
TOKENS_FILE = DATA_DIR / "tokens.json"

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
        "redirect_uri": "http://localhost:8080/callback",
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
            "redirect_uri": "http://localhost:8080/callback",
        },
        auth=(client_id, client_secret),
    )
    resp.raise_for_status()
    return resp.json()


def save_tokens(token_data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"トークンを {TOKENS_FILE} に保存しました")


def main():
    client_id = os.environ.get("FITBIT_CLIENT_ID")
    client_secret = os.environ.get("FITBIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("エラー: .env に FITBIT_CLIENT_ID と FITBIT_CLIENT_SECRET を設定してください")
        return

    code_verifier, code_challenge = generate_pkce()

    auth_url = build_auth_url(client_id, code_challenge)
    print("\n以下のURLをブラウザで開いて認可してください：")
    print(f"\n{auth_url}\n")
    print("認可後、リダイレクトURLから 'code=' の値をコピーしてください。")
    print("（例: http://localhost:8080/callback?code=XXXXXX の XXXXXX 部分）\n")

    auth_code = input("認可コードを入力: ").strip()

    if not auth_code:
        print("エラー: 認可コードが空です")
        return

    print("\nトークンを取得中...")
    token_data = exchange_code(client_id, client_secret, auth_code, code_verifier)
    save_tokens(token_data)
    print("認可が完了しました")


if __name__ == "__main__":
    main()
