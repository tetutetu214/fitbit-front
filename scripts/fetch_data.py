"""Fitbit APIからヘルスデータを取得してJSONに保存する"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
TOKENS_FILE = DATA_DIR / "tokens.json"
BASE_URL = "https://api.fitbit.com"


def load_tokens() -> dict:
    if not TOKENS_FILE.exists():
        print("エラー: トークンが見つかりません。先に auth.py を実行してください")
        sys.exit(1)
    with open(TOKENS_FILE) as f:
        return json.load(f)


def save_tokens(token_data: dict):
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f, indent=2)


def refresh_token(token_data: dict) -> dict:
    client_id = os.environ.get("FITBIT_CLIENT_ID")
    client_secret = os.environ.get("FITBIT_CLIENT_SECRET")

    resp = requests.post(
        f"{BASE_URL}/oauth2/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": token_data["refresh_token"],
            "client_id": client_id,
        },
        auth=(client_id, client_secret),
    )

    if resp.status_code == 401:
        print("エラー: リフレッシュトークンが無効です。auth.py を再実行してください")
        sys.exit(1)

    resp.raise_for_status()
    new_tokens = resp.json()
    save_tokens(new_tokens)
    print("トークンをリフレッシュしました")
    return new_tokens


def api_get(endpoint: str, token_data: dict) -> dict:
    """Fitbit APIを呼び出す。401なら自動リフレッシュして再試行"""
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers)

    if resp.status_code == 401:
        token_data = refresh_token(token_data)
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers)

    resp.raise_for_status()
    return resp.json(), token_data


ENDPOINTS = {
    "heartrate": "/1/user/-/activities/heart/date/{date}/1d.json",
    "sleep": "/1.2/user/-/sleep/date/{date}.json",
    "activity": "/1/user/-/activities/date/{date}.json",
    "hrv": "/1/user/-/hrv/date/{date}.json",
    "spo2": "/1/user/-/spo2/date/{date}.json",
}


def fetch_date(date_str: str, token_data: dict) -> dict:
    """指定日の全データを取得"""
    results = {}

    for name, endpoint_template in ENDPOINTS.items():
        endpoint = endpoint_template.format(date=date_str)
        try:
            data, token_data = api_get(endpoint, token_data)
            results[name] = data
            print(f"  {name}: OK")
        except requests.HTTPError as e:
            print(f"  {name}: エラー ({e.response.status_code})")
            results[name] = {"error": e.response.status_code}

    return results, token_data


def save_daily_data(date_str: str, data: dict):
    daily_dir = DATA_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    filepath = daily_dir / f"{date_str}.json"
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  保存: {filepath}")


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    token_data = load_tokens()

    print(f"過去{days}日分のデータを取得します\n")

    for i in range(days):
        date = datetime.now() - timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        print(f"[{date_str}]")

        daily_data, token_data = fetch_date(date_str, token_data)
        save_daily_data(date_str, daily_data)
        print()

    print("完了")


if __name__ == "__main__":
    main()
