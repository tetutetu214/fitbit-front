"""
タニタ Health Planet API クライアント

取得データ：体重（tag:6021）・体脂肪率（tag:6022）
認証：OAuth 2.0 Authorization Code Grant
トークン：.env に永続化（30日有効、自動リフレッシュ）

参照: https://www.healthplanet.jp/apis/api.html
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv, set_key

# ── 定数 ────────────────────────────────────────────────
REDIRECT_URI = "https://www.healthplanet.jp/success.html"
AUTH_URL = "https://www.healthplanet.jp/oauth/auth"
TOKEN_URL = "https://www.healthplanet.jp/oauth/token"
INNERSCAN_URL = "https://www.healthplanet.jp/status/innerscan.json"
ENV_FILE = ".env"

TAG_WEIGHT = "6021"       # 体重 (kg)
TAG_BODY_FAT = "6022"     # 体脂肪率 (%)


# ── .env 読み込み ────────────────────────────────────────
load_dotenv()

CLIENT_ID = os.getenv("TANITA_CLIENT_ID")
CLIENT_SECRET = os.getenv("TANITA_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    print(
        "エラー: .env に TANITA_CLIENT_ID / TANITA_CLIENT_SECRET が設定されていません。",
        file=sys.stderr,
    )
    sys.exit(1)


# ── トークン管理 ─────────────────────────────────────────

def _save_tokens(access_token: str, refresh_token: str) -> None:
    """アクセストークンとリフレッシュトークンを .env に保存する。"""
    set_key(ENV_FILE, "TANITA_ACCESS_TOKEN", access_token)
    set_key(ENV_FILE, "TANITA_REFRESH_TOKEN", refresh_token)
    # 取得日時（UTC）も保存しておく（有効期限チェック用）
    now_iso = datetime.now(timezone.utc).isoformat()
    set_key(ENV_FILE, "TANITA_TOKEN_OBTAINED_AT", now_iso)
    # os.environ にも反映
    os.environ["TANITA_ACCESS_TOKEN"] = access_token
    os.environ["TANITA_REFRESH_TOKEN"] = refresh_token
    os.environ["TANITA_TOKEN_OBTAINED_AT"] = now_iso


def _is_token_expired() -> bool:
    """トークン取得から 28 日以上経過していれば期限切れとみなす。
    （公式有効期限 30 日に対して 2 日のバッファを持たせる）
    """
    obtained_at_str = os.getenv("TANITA_TOKEN_OBTAINED_AT")
    if not obtained_at_str:
        return True
    try:
        obtained_at = datetime.fromisoformat(obtained_at_str)
        return datetime.now(timezone.utc) - obtained_at > timedelta(days=28)
    except ValueError:
        return True


def _fetch_token_with_code(code: str) -> dict:
    """認可コードを使ってアクセストークンを取得する。"""
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def _refresh_access_token(refresh_token: str) -> dict:
    """リフレッシュトークンを使ってアクセストークンを更新する。

    参照: Health Planet API 仕様書 (grant_type=refresh_token)
    """
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_access_token() -> str:
    """有効なアクセストークンを返す。
    - .env に保存済みで期限内 → そのまま返す
    - 期限切れ           → refresh_token で自動更新
    - トークンなし       → ブラウザ認証フロー（初回のみ）
    """
    access_token = os.getenv("TANITA_ACCESS_TOKEN")
    refresh_token = os.getenv("TANITA_REFRESH_TOKEN")

    # ── 既存トークンが有効な場合 ──
    if access_token and not _is_token_expired():
        return access_token

    # ── リフレッシュトークンで更新 ──
    if refresh_token and _is_token_expired():
        print("アクセストークンの有効期限が近いため、自動更新します...")
        try:
            token_data = _refresh_access_token(refresh_token)
            new_access = token_data["access_token"]
            new_refresh = token_data.get("refresh_token", refresh_token)
            _save_tokens(new_access, new_refresh)
            print("トークンを更新しました。")
            return new_access
        except requests.HTTPError as e:
            print(f"トークン更新失敗: {e}。再認証を行います...")

    # ── 初回 or 更新失敗 → ブラウザ認証フロー ──
    auth_url = (
        f"{AUTH_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope=innerscan"
        f"&response_type=code"
    )
    print("\n以下のURLをブラウザ（Windows側）で開いて「許可」を押してください：")
    print(f"\n  {auth_url}\n")

    code = input(
        "ブラウザに表示された認可コードを入力してください（10分以内）: "
    ).strip()
    if not code:
        print("エラー: コードが入力されませんでした。", file=sys.stderr)
        sys.exit(1)

    token_data = _fetch_token_with_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    _save_tokens(access_token, refresh_token)
    print("認証完了。トークンを .env に保存しました。\n")
    return access_token


# ── データ取得 ────────────────────────────────────────────

def fetch_innerscan(
    access_token: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """体組成データを取得する。

    Args:
        access_token: 有効なアクセストークン
        from_date: 取得開始日時（デフォルト: 3ヶ月前）
        to_date: 取得終了日時（デフォルト: 現在）

    Returns:
        APIレスポンス JSON（birth_date, height, sex, data[]）

    参照: https://www.healthplanet.jp/apis/api.html
        取得期間は最大 3ヶ月。超えると自動補正される。
    """
    if to_date is None:
        to_date = datetime.now()
    if from_date is None:
        from_date = to_date - timedelta(days=90)

    params = {
        "access_token": access_token,
        "date": "1",            # 1=測定日時基準
        "from": from_date.strftime("%Y%m%d%H%M%S"),
        "to": to_date.strftime("%Y%m%d%H%M%S"),
        "tag": f"{TAG_WEIGHT},{TAG_BODY_FAT}",
    }
    resp = requests.get(INNERSCAN_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── 表示 ─────────────────────────────────────────────────

def _parse_and_display(data: dict) -> None:
    """APIレスポンスを日付ごとに整形して表示する。"""
    records = data.get("data", [])
    if not records:
        print("データがありません。")
        return

    # 日付ごとに体重・体脂肪率をまとめる
    by_date: dict[str, dict] = {}
    for item in records:
        date_str = item["date"]          # "yyyyMMddHHmm"
        tag = item["tag"]
        value = float(item["keydata"])
        dt = datetime.strptime(date_str, "%Y%m%d%H%M")
        key = dt.strftime("%Y-%m-%d %H:%M")
        by_date.setdefault(key, {})
        if tag == TAG_WEIGHT:
            by_date[key]["weight"] = value
        elif tag == TAG_BODY_FAT:
            by_date[key]["body_fat"] = value

    # プロファイル情報
    sex = data.get("sex", "")
    height = data.get("height", "")
    birth = data.get("birth_date", "")
    print(f"【プロファイル】身長: {height}cm  性別: {sex}  生年月日: {birth}\n")

    # ヘッダー
    print(f"{'日時':<20} {'体重 (kg)':>10} {'体脂肪率 (%)':>13}")
    print("-" * 46)

    # 日付昇順で表示
    for key in sorted(by_date.keys()):
        entry = by_date[key]
        weight = f"{entry['weight']:.1f}" if "weight" in entry else "  -"
        body_fat = f"{entry['body_fat']:.1f}" if "body_fat" in entry else "  -"
        print(f"{key:<20} {weight:>10} {body_fat:>13}")

    print(f"\n合計 {len(by_date)} 件")


# ── エントリポイント ──────────────────────────────────────

def main() -> None:
    token = get_access_token()

    print("タニタ Health Planet からデータを取得中...\n")
    try:
        data = fetch_innerscan(token)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            # トークン無効 → .env をクリアして再認証を促す
            set_key(ENV_FILE, "TANITA_ACCESS_TOKEN", "")
            set_key(ENV_FILE, "TANITA_REFRESH_TOKEN", "")
            print(
                "エラー: アクセストークンが無効です。"
                "再度スクリプトを実行してください。",
                file=sys.stderr,
            )
        else:
            print(f"エラー: API リクエスト失敗 - {e}", file=sys.stderr)
        sys.exit(1)

    _parse_and_display(data)


if __name__ == "__main__":
    main()
