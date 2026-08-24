"""Fitbit APIからヘルスデータを範囲取得して日次JSONに保存する。"""

import argparse
import json
import os
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
TOKENS_FILE = DATA_DIR / "tokens.json"
BASE_URL = "https://api.fitbit.com"

JsonObject = dict[str, Any]
JsonResponse = JsonObject | list[Any]

# Fitbit API の日付範囲上限。仕様変更時はここだけを更新する。
HEARTRATE_MAX_DAYS = 365
SLEEP_MAX_DAYS = 100
HRV_MAX_DAYS = 30
SPO2_MAX_DAYS = 30
ACTIVITY_MAX_DAYS = 365

RANGE_ENDPOINTS = {
    "heartrate": (
        "/1/user/-/activities/heart/date/{start}/{end}.json",
        HEARTRATE_MAX_DAYS,
    ),
    "sleep": ("/1.2/user/-/sleep/date/{start}/{end}.json", SLEEP_MAX_DAYS),
    "hrv": ("/1/user/-/hrv/date/{start}/{end}.json", HRV_MAX_DAYS),
    "spo2": ("/1/user/-/spo2/date/{start}/{end}.json", SPO2_MAX_DAYS),
}

ACTIVITY_RESOURCES = {
    "steps": "steps",
    "activityCalories": "activityCalories",
    "minutesSedentary": "sedentaryMinutes",
    "minutesLightlyActive": "lightlyActiveMinutes",
    "minutesFairlyActive": "fairlyActiveMinutes",
    "minutesVeryActive": "veryActiveMinutes",
}
ACTIVITY_ENDPOINT = "/1/user/-/activities/{resource}/date/{start}/{end}.json"
MAX_RATE_LIMIT_RETRIES = 3
DEFAULT_RETRY_AFTER_SECONDS = 60


@dataclass
class FetchStats:
    attempted_chunks: int = 0
    successful_chunks: int = 0


def load_tokens() -> JsonObject:
    if not TOKENS_FILE.exists():
        print("エラー: トークンが見つかりません。先に auth.py を実行してください")
        sys.exit(1)
    with TOKENS_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_tokens(token_data: JsonObject) -> None:
    with TOKENS_FILE.open("w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def refresh_token(token_data: JsonObject) -> JsonObject:
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


def api_get(
    endpoint: str, token_data: JsonObject
) -> tuple[JsonResponse, JsonObject]:
    """Fitbit APIを呼び出し、401と429を規定回数だけ再試行する。"""
    refreshed = False
    rate_limit_retries = 0
    while True:
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=headers)

        if resp.status_code == 401 and not refreshed:
            token_data = refresh_token(token_data)
            refreshed = True
            continue

        if (
            resp.status_code == 429
            and rate_limit_retries < MAX_RATE_LIMIT_RETRIES
        ):
            wait_seconds = _retry_after_seconds(resp)
            rate_limit_retries += 1
            print(
                f"  429: {wait_seconds}秒後に再試行 "
                f"({rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES})"
            )
            time.sleep(wait_seconds)
            continue

        resp.raise_for_status()
        return resp.json(), token_data


def _retry_after_seconds(response: requests.Response) -> int:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return DEFAULT_RETRY_AFTER_SECONDS
    try:
        return max(0, int(retry_after))
    except ValueError:
        return DEFAULT_RETRY_AFTER_SECONDS


def split_date_range(
    start_date: date, end_date: date, max_days: int
) -> Iterator[tuple[date, date]]:
    """両端を含む期間をAPI上限以内の範囲に分割する。"""
    if start_date > end_date:
        raise ValueError("開始日は終了日以前である必要があります")
    if max_days < 1:
        raise ValueError("max_days は1以上である必要があります")

    chunk_start = start_date
    while chunk_start <= end_date:
        chunk_end = min(end_date, chunk_start + timedelta(days=max_days - 1))
        yield chunk_start, chunk_end
        chunk_start = chunk_end + timedelta(days=1)


def iter_dates(start_date: date, end_date: date) -> Iterator[date]:
    """両端を含む日付を昇順で返す。"""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def empty_daily_data() -> JsonObject:
    """Fitbitが空配列を返した日にも保存する日次データの形を返す。"""
    return {
        "heartrate": {"activities-heart": []},
        "sleep": {
            "sleep": [],
            "summary": {
                "totalMinutesAsleep": 0,
                "totalSleepRecords": 0,
                "totalTimeInBed": 0,
                "stages": {"deep": 0, "light": 0, "rem": 0, "wake": 0},
            },
        },
        "activity": {"summary": {}},
        "hrv": {"hrv": []},
        "spo2": {},
    }


def _records(payload: JsonResponse, key: str) -> list[JsonObject]:
    if not isinstance(payload, dict):
        return []
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [record for record in value if isinstance(record, dict)]


def _numeric(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number
    return None


def _sleep_summary(logs: list[JsonObject]) -> JsonObject:
    stages = {"deep": 0, "light": 0, "rem": 0, "wake": 0}
    total_minutes_asleep = 0
    total_time_in_bed = 0

    for log in logs:
        minutes_asleep = _numeric(log.get("minutesAsleep"))
        time_in_bed = _numeric(log.get("timeInBed"))
        if minutes_asleep is not None:
            total_minutes_asleep += minutes_asleep
        if time_in_bed is not None:
            total_time_in_bed += time_in_bed

        levels = log.get("levels")
        level_summary = levels.get("summary", {}) if isinstance(levels, dict) else {}
        if not isinstance(level_summary, dict):
            continue
        for stage in stages:
            stage_data = level_summary.get(stage)
            if not isinstance(stage_data, dict):
                continue
            minutes = _numeric(stage_data.get("minutes"))
            if minutes is not None:
                stages[stage] += minutes

    return {
        "totalMinutesAsleep": total_minutes_asleep,
        "totalSleepRecords": len(logs),
        "totalTimeInBed": total_time_in_bed,
        "stages": stages,
    }


def _apply_heartrate(payload: JsonResponse, daily_data: dict[str, JsonObject]) -> None:
    records_by_date: dict[str, list[JsonObject]] = {}
    for record in _records(payload, "activities-heart"):
        date_string = record.get("dateTime")
        if isinstance(date_string, str):
            records_by_date.setdefault(date_string, []).append(record)

    for date_string, records in records_by_date.items():
        if date_string in daily_data:
            daily_data[date_string]["heartrate"] = {
                "activities-heart": records[:1]
            }


def _apply_sleep(payload: JsonResponse, daily_data: dict[str, JsonObject]) -> None:
    logs_by_date: dict[str, list[JsonObject]] = {}
    for log in _records(payload, "sleep"):
        # 日付をまたぐログは開始時刻ではなくFitbitのdateOfSleepに従う。
        date_string = log.get("dateOfSleep")
        if isinstance(date_string, str):
            logs_by_date.setdefault(date_string, []).append(log)

    for date_string, logs in logs_by_date.items():
        if date_string in daily_data:
            daily_data[date_string]["sleep"] = {
                "sleep": logs,
                "summary": _sleep_summary(logs),
            }


def _apply_hrv(payload: JsonResponse, daily_data: dict[str, JsonObject]) -> None:
    records_by_date: dict[str, list[JsonObject]] = {}
    for record in _records(payload, "hrv"):
        date_string = record.get("dateTime")
        if isinstance(date_string, str):
            records_by_date.setdefault(date_string, []).append(record)

    for date_string, records in records_by_date.items():
        if date_string in daily_data:
            daily_data[date_string]["hrv"] = {"hrv": records}


def _spo2_records(payload: JsonResponse) -> list[JsonObject]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    wrapped_records = _records(payload, "spo2")
    if wrapped_records:
        return wrapped_records
    if isinstance(payload, dict) and isinstance(payload.get("dateTime"), str):
        return [payload]
    return []


def _apply_spo2(payload: JsonResponse, daily_data: dict[str, JsonObject]) -> None:
    for record in _spo2_records(payload):
        date_string = record.get("dateTime")
        if isinstance(date_string, str) and date_string in daily_data:
            daily_data[date_string]["spo2"] = record


def _apply_activity(
    resource: str,
    summary_key: str,
    payload: JsonResponse,
    daily_data: dict[str, JsonObject],
) -> None:
    response_key = f"activities-{resource}"
    for record in _records(payload, response_key):
        date_string = record.get("dateTime")
        value = _numeric(record.get("value"))
        if not isinstance(date_string, str) or value is None:
            continue
        if date_string not in daily_data:
            continue
        activity = daily_data[date_string]["activity"]
        if isinstance(activity, dict):
            summary = activity.get("summary")
            if isinstance(summary, dict):
                summary[summary_key] = value


def _http_status(error: requests.HTTPError) -> object:
    return getattr(error.response, "status_code", "不明")


def _mark_chunk_error(
    daily_data: dict[str, JsonObject],
    name: str,
    chunk_start: date,
    chunk_end: date,
    status: object,
) -> None:
    for current in iter_dates(chunk_start, chunk_end):
        daily_data[current.isoformat()][name] = {"error": status}


def fetch_date_range(
    start_date: date,
    end_date: date,
    token_data: JsonObject,
    *,
    stats: FetchStats | None = None,
) -> tuple[dict[str, JsonObject], JsonObject]:
    """指定期間をAPI別の上限で取得し、日次データへ分割する。"""
    fetch_stats = stats or FetchStats()
    daily_data = {
        current.isoformat(): empty_daily_data()
        for current in iter_dates(start_date, end_date)
    }

    apply_response = {
        "heartrate": _apply_heartrate,
        "sleep": _apply_sleep,
        "hrv": _apply_hrv,
        "spo2": _apply_spo2,
    }
    for name, (endpoint_template, max_days) in RANGE_ENDPOINTS.items():
        for chunk_start, chunk_end in split_date_range(
            start_date, end_date, max_days
        ):
            endpoint = endpoint_template.format(
                start=chunk_start.isoformat(), end=chunk_end.isoformat()
            )
            fetch_stats.attempted_chunks += 1
            try:
                payload, token_data = api_get(endpoint, token_data)
            except requests.HTTPError as error:
                status = _http_status(error)
                _mark_chunk_error(
                    daily_data, name, chunk_start, chunk_end, status
                )
                print(
                    f"  {name} {chunk_start}〜{chunk_end}: "
                    f"エラー ({status})"
                )
                continue
            fetch_stats.successful_chunks += 1
            apply_response[name](payload, daily_data)
            print(f"  {name} {chunk_start}〜{chunk_end}: OK")

    for resource, summary_key in ACTIVITY_RESOURCES.items():
        for chunk_start, chunk_end in split_date_range(
            start_date, end_date, ACTIVITY_MAX_DAYS
        ):
            endpoint = ACTIVITY_ENDPOINT.format(
                resource=resource,
                start=chunk_start.isoformat(),
                end=chunk_end.isoformat(),
            )
            fetch_stats.attempted_chunks += 1
            try:
                payload, token_data = api_get(endpoint, token_data)
            except requests.HTTPError as error:
                status = _http_status(error)
                _mark_chunk_error(
                    daily_data, "activity", chunk_start, chunk_end, status
                )
                print(
                    f"  activity/{resource} {chunk_start}〜{chunk_end}: "
                    f"エラー ({status})"
                )
                continue
            fetch_stats.successful_chunks += 1
            _apply_activity(resource, summary_key, payload, daily_data)
            print(f"  activity/{resource} {chunk_start}〜{chunk_end}: OK")

    return daily_data, token_data


def save_daily_data(date_str: str, data: JsonObject) -> None:
    daily_dir = DATA_DIR / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    filepath = daily_dir / f"{date_str}.json"
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  保存: {filepath}")


def _contains_error(value: object) -> bool:
    if isinstance(value, dict):
        return "error" in value or any(
            _contains_error(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_error(item) for item in value)
    return False


def _existing_daily_file_is_complete(filepath: Path) -> bool:
    try:
        value = json.loads(filepath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"警告: {filepath} を再取得します ({error})", file=sys.stderr)
        return False
    if not isinstance(value, dict):
        print(f"警告: {filepath} を再取得します (JSON直下がobjectではありません)")
        return False
    return not _contains_error(value)


def _today_in_japan() -> date:
    return datetime.now(tz=ZoneInfo("Asia/Tokyo")).date()


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("整数を指定してください") from error
    if number < 1:
        raise argparse.ArgumentTypeError("1以上を指定してください")
    return number


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("YYYY-MM-DD形式で指定してください") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fitbitの日付範囲データを日次JSONに分割して保存します"
    )
    parser.add_argument("--days", type=_positive_int, default=60, help="取得日数")
    parser.add_argument(
        "--end",
        type=_iso_date,
        default=_today_in_japan() - timedelta(days=1),
        help="終了日 (YYYY-MM-DD、既定: 昨日)",
    )
    parser.add_argument(
        "--force", action="store_true", help="既存の日次JSONも上書きする"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.end >= _today_in_japan():
        print(
            "警告: --end が今日以降です。当日以降のデータは未確定の可能性があります",
            file=sys.stderr,
        )
    start_date = args.end - timedelta(days=args.days - 1)
    requested_dates = list(iter_dates(start_date, args.end))
    daily_dir = DATA_DIR / "daily"

    target_dates: list[date] = []
    for current in requested_dates:
        filepath = daily_dir / f"{current.isoformat()}.json"
        if (
            filepath.is_file()
            and not args.force
            and _existing_daily_file_is_complete(filepath)
        ):
            print(f"[{current}] スキップ: 既存ファイル")
        else:
            if filepath.is_file() and not args.force:
                print(f"[{current}] 再取得: errorを含む既存ファイル")
            target_dates.append(current)

    if not target_dates:
        print("対象期間はすべて取得済みです")
        return 0

    load_dotenv(PROJECT_ROOT / ".env")
    token_data = load_tokens()
    range_start = target_dates[0]
    range_end = target_dates[-1]
    print(f"未取得日の範囲 {range_start}〜{range_end} を取得します")

    stats = FetchStats()
    all_daily_data, token_data = fetch_date_range(
        range_start, range_end, token_data, stats=stats
    )

    target_date_strings = {current.isoformat() for current in target_dates}
    for date_string in sorted(all_daily_data):
        if date_string in target_date_strings:
            save_daily_data(date_string, all_daily_data[date_string])

    if stats.attempted_chunks > 0 and stats.successful_chunks == 0:
        print("エラー: 全チャンクの取得に失敗しました", file=sys.stderr)
        return 1

    print("完了")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
