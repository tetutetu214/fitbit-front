# 実APIは本人のOAuthトークンとAWS認証が必要で、サンドボックスから到達できない。
# そのため、該当するHTTPまたはboto3をモックする。

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import requests

from scripts import fetch_data

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fitbit_range_responses.json"


def load_range_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def fetch_fixture_range(monkeypatch) -> tuple[dict[str, Any], dict[str, Any]]:
    fixture = load_range_fixture()

    def fake_api_get(
        endpoint: str, token_data: fetch_data.JsonObject
    ) -> tuple[fetch_data.JsonResponse, fetch_data.JsonObject]:
        if "/activities/heart/" in endpoint:
            return fixture["heartrate"], token_data
        if "/sleep/" in endpoint:
            return fixture["sleep"], token_data
        if "/hrv/" in endpoint:
            return fixture["hrv"], token_data
        if "/spo2/" in endpoint:
            return fixture["spo2"], token_data
        for resource, payload in fixture["activities"].items():
            if f"/activities/{resource}/" in endpoint:
                return payload, token_data
        raise AssertionError(f"想定外のendpoint: {endpoint}")

    monkeypatch.setattr(fetch_data, "api_get", fake_api_get)
    daily_data, _ = fetch_data.fetch_date_range(
        date(2026, 4, 1),
        date(2026, 4, 3),
        {"access_token": "test"},
    )
    return daily_data, fixture


def empty_payload_for_endpoint(endpoint: str) -> fetch_data.JsonResponse:
    if "/activities/heart/" in endpoint:
        return {"activities-heart": []}
    if "/sleep/" in endpoint:
        return {"sleep": []}
    if "/hrv/" in endpoint:
        return {"hrv": []}
    if "/spo2/" in endpoint:
        return []
    resource = endpoint.split("/activities/", 1)[1].split("/", 1)[0]
    return {f"activities-{resource}": []}


def http_error(status_code: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    return requests.HTTPError(response=response)


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: fetch_data.JsonResponse,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self) -> fetch_data.JsonResponse:
        return self.payload


def test_30_day_limit_splits_60_days_twice_and_61_days_three_times() -> None:
    start_date = date(2026, 1, 1)
    sixty_day_end = start_date + timedelta(days=59)
    sixty_one_day_end = start_date + timedelta(days=60)

    sixty_day_chunks = list(
        fetch_data.split_date_range(start_date, sixty_day_end, 30)
    )
    sixty_one_day_chunks = list(
        fetch_data.split_date_range(start_date, sixty_one_day_end, 30)
    )

    assert sixty_day_chunks == [
        (date(2026, 1, 1), date(2026, 1, 30)),
        (date(2026, 1, 31), date(2026, 3, 1)),
    ]
    assert sixty_one_day_chunks == [
        *sixty_day_chunks,
        (date(2026, 3, 2), date(2026, 3, 2)),
    ]


def test_heartrate_records_are_split_by_day_and_missing_days_remain_empty(
    monkeypatch,
) -> None:
    daily_data, fixture = fetch_fixture_range(monkeypatch)

    assert daily_data["2026-04-01"]["heartrate"] == {
        "activities-heart": fixture["heartrate"]["activities-heart"][:1]
    }
    assert daily_data["2026-04-02"]["heartrate"] == {
        "activities-heart": []
    }


def test_sleep_uses_date_of_sleep_and_builds_daily_summary(monkeypatch) -> None:
    daily_data, _ = fetch_fixture_range(monkeypatch)

    sleep = daily_data["2026-04-02"]["sleep"]
    assert sleep["sleep"][0]["startTime"].startswith("2026-04-01")
    assert sleep["sleep"][0]["dateOfSleep"] == "2026-04-02"
    assert sleep["summary"] == {
        "totalMinutesAsleep": 400,
        "totalSleepRecords": 1,
        "totalTimeInBed": 450,
        "stages": {"deep": 60, "light": 250, "rem": 70, "wake": 70},
    }


def test_activity_resources_are_merged_and_missing_days_remain_empty(
    monkeypatch,
) -> None:
    daily_data, _ = fetch_fixture_range(monkeypatch)

    assert daily_data["2026-04-01"]["activity"]["summary"] == {
        "steps": 1234,
        "activityCalories": 456,
        "sedentaryMinutes": 600,
        "lightlyActiveMinutes": 100,
        "fairlyActiveMinutes": 20,
        "veryActiveMinutes": 10,
    }
    assert daily_data["2026-04-03"]["activity"] == {"summary": {}}


def test_hrv_and_spo2_records_are_split_by_day(monkeypatch) -> None:
    daily_data, fixture = fetch_fixture_range(monkeypatch)

    assert daily_data["2026-04-03"]["hrv"] == {
        "hrv": fixture["hrv"]["hrv"][1:]
    }
    assert daily_data["2026-04-01"]["spo2"] == fixture["spo2"][0]
    assert daily_data["2026-04-02"]["spo2"] == {}


def test_61_day_fetch_calls_30_day_endpoints_three_times(monkeypatch) -> None:
    endpoints: list[str] = []

    def fake_api_get(
        endpoint: str, token_data: fetch_data.JsonObject
    ) -> tuple[fetch_data.JsonResponse, fetch_data.JsonObject]:
        endpoints.append(endpoint)
        if "/spo2/" in endpoint:
            return [], token_data
        if "/sleep/" in endpoint:
            return {"sleep": []}, token_data
        if "/hrv/" in endpoint:
            return {"hrv": []}, token_data
        key = endpoint.split("/activities/", 1)[1].split("/", 1)[0]
        return {f"activities-{key}": []}, token_data

    monkeypatch.setattr(fetch_data, "api_get", fake_api_get)
    fetch_data.fetch_date_range(
        date(2026, 1, 1),
        date(2026, 3, 2),
        {"access_token": "test"},
    )

    hrv_endpoints = [endpoint for endpoint in endpoints if "/hrv/" in endpoint]
    spo2_endpoints = [endpoint for endpoint in endpoints if "/spo2/" in endpoint]
    assert len(hrv_endpoints) == 3
    assert len(spo2_endpoints) == 3
    assert hrv_endpoints[-1].endswith("/2026-03-02/2026-03-02.json")


def test_nonconsecutive_missing_days_use_one_range_and_keep_complete_days(
    tmp_path, monkeypatch
) -> None:
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    existing_paths = [
        daily_dir / "2026-04-02.json",
        daily_dir / "2026-04-04.json",
    ]
    for existing_path in existing_paths:
        existing_path.write_text('{"kept": true}', encoding="utf-8")
    fetched_ranges: list[tuple[date, date]] = []

    def fake_fetch_date_range(
        start_date: date,
        end_date: date,
        token_data: fetch_data.JsonObject,
        *,
        stats: fetch_data.FetchStats | None = None,
    ) -> tuple[dict[str, fetch_data.JsonObject], fetch_data.JsonObject]:
        fetched_ranges.append((start_date, end_date))
        if stats is not None:
            stats.attempted_chunks += 1
            stats.successful_chunks += 1
        return {
            current.isoformat(): fetch_data.empty_daily_data()
            for current in fetch_data.iter_dates(start_date, end_date)
        }, token_data

    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_data, "load_dotenv", lambda path: None)
    monkeypatch.setattr(
        fetch_data, "load_tokens", lambda: {"access_token": "test"}
    )
    monkeypatch.setattr(fetch_data, "fetch_date_range", fake_fetch_date_range)

    exit_code = fetch_data.main(["--days", "4", "--end", "2026-04-04"])

    assert exit_code == 0
    assert fetched_ranges == [(date(2026, 4, 1), date(2026, 4, 3))]
    assert (daily_dir / "2026-04-01.json").is_file()
    assert (daily_dir / "2026-04-03.json").is_file()
    assert all(
        path.read_text(encoding="utf-8") == '{"kept": true}'
        for path in existing_paths
    )


def test_http_error_is_recorded_for_each_day_in_its_chunk(monkeypatch) -> None:
    def fake_api_get(
        endpoint: str, token_data: fetch_data.JsonObject
    ) -> tuple[fetch_data.JsonResponse, fetch_data.JsonObject]:
        if "/sleep/" in endpoint:
            raise http_error(503)
        return empty_payload_for_endpoint(endpoint), token_data

    monkeypatch.setattr(fetch_data, "api_get", fake_api_get)
    daily_data, _ = fetch_data.fetch_date_range(
        date(2026, 4, 1),
        date(2026, 4, 2),
        {"access_token": "test"},
    )

    assert daily_data["2026-04-01"]["sleep"] == {"error": 503}
    assert daily_data["2026-04-02"]["sleep"] == {"error": 503}


def test_existing_error_day_is_fetched_again(tmp_path, monkeypatch) -> None:
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    existing_path = daily_dir / "2026-04-01.json"
    existing_path.write_text('{"sleep": {"error": 503}}', encoding="utf-8")
    fetched_ranges: list[tuple[date, date]] = []

    def fake_fetch_date_range(
        start_date: date,
        end_date: date,
        token_data: fetch_data.JsonObject,
        *,
        stats: fetch_data.FetchStats | None = None,
    ) -> tuple[dict[str, fetch_data.JsonObject], fetch_data.JsonObject]:
        fetched_ranges.append((start_date, end_date))
        if stats is not None:
            stats.attempted_chunks += 1
            stats.successful_chunks += 1
        return {start_date.isoformat(): fetch_data.empty_daily_data()}, token_data

    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_data, "load_dotenv", lambda path: None)
    monkeypatch.setattr(
        fetch_data, "load_tokens", lambda: {"access_token": "test"}
    )
    monkeypatch.setattr(fetch_data, "fetch_date_range", fake_fetch_date_range)

    exit_code = fetch_data.main(["--days", "1", "--end", "2026-04-01"])

    assert exit_code == 0
    assert fetched_ranges == [(date(2026, 4, 1), date(2026, 4, 1))]
    saved = json.loads(existing_path.read_text(encoding="utf-8"))
    assert not fetch_data._contains_error(saved)


def test_partially_failed_day_is_saved_and_returns_zero(
    tmp_path, monkeypatch
) -> None:
    def fake_api_get(
        endpoint: str, token_data: fetch_data.JsonObject
    ) -> tuple[fetch_data.JsonResponse, fetch_data.JsonObject]:
        if "/sleep/" in endpoint:
            raise http_error(503)
        return empty_payload_for_endpoint(endpoint), token_data

    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_data, "load_dotenv", lambda path: None)
    monkeypatch.setattr(
        fetch_data, "load_tokens", lambda: {"access_token": "test"}
    )
    monkeypatch.setattr(fetch_data, "api_get", fake_api_get)

    exit_code = fetch_data.main(["--days", "1", "--end", "2026-04-01"])

    saved_path = tmp_path / "daily" / "2026-04-01.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert saved["sleep"] == {"error": 503}


def test_all_failed_chunks_are_saved_and_return_one(
    tmp_path, monkeypatch
) -> None:
    def raise_http_error(
        endpoint: str, token_data: fetch_data.JsonObject
    ) -> tuple[fetch_data.JsonResponse, fetch_data.JsonObject]:
        raise http_error(503)

    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(fetch_data, "load_dotenv", lambda path: None)
    monkeypatch.setattr(
        fetch_data, "load_tokens", lambda: {"access_token": "test"}
    )
    monkeypatch.setattr(fetch_data, "api_get", raise_http_error)

    exit_code = fetch_data.main(["--days", "1", "--end", "2026-04-01"])

    assert exit_code == 1
    saved_path = tmp_path / "daily" / "2026-04-01.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    assert saved == {
        "heartrate": {"error": 503},
        "sleep": {"error": 503},
        "activity": {"error": 503},
        "hrv": {"error": 503},
        "spo2": {"error": 503},
    }


def test_429_uses_retry_after_and_falls_back_to_sixty_seconds(
    monkeypatch,
) -> None:
    responses = [
        FakeResponse(429, {}, {"Retry-After": "12"}),
        FakeResponse(429, {}),
        FakeResponse(200, {"ok": True}),
    ]
    waits: list[int] = []
    monkeypatch.setattr(
        fetch_data.requests, "get", lambda url, headers: responses.pop(0)
    )
    monkeypatch.setattr(fetch_data.time, "sleep", waits.append)

    payload, _ = fetch_data.api_get("/test", {"access_token": "test"})

    assert payload == {"ok": True}
    assert waits == [12, 60]


def test_429_is_retried_at_most_three_times(monkeypatch) -> None:
    responses = [
        FakeResponse(429, {}, {"Retry-After": "0"}) for _ in range(4)
    ]
    waits: list[int] = []
    monkeypatch.setattr(
        fetch_data.requests, "get", lambda url, headers: responses.pop(0)
    )
    monkeypatch.setattr(fetch_data.time, "sleep", waits.append)

    with pytest.raises(requests.HTTPError):
        fetch_data.api_get("/test", {"access_token": "test"})

    assert waits == [0, 0, 0]
    assert responses == []


def test_default_end_is_yesterday_in_japan(monkeypatch) -> None:
    monkeypatch.setattr(
        fetch_data, "_today_in_japan", lambda: date(2026, 8, 23)
    )

    args = fetch_data.build_parser().parse_args([])

    assert args.end == date(2026, 8, 22)


def test_end_today_prints_unsettled_data_warning(
    tmp_path, monkeypatch, capsys
) -> None:
    daily_dir = tmp_path / "daily"
    daily_dir.mkdir()
    (daily_dir / "2026-08-23.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(fetch_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        fetch_data, "_today_in_japan", lambda: date(2026, 8, 23)
    )

    exit_code = fetch_data.main(
        ["--days", "1", "--end", "2026-08-23"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "当日以降のデータは未確定" in captured.err


def test_api_get_refreshes_once_after_401(monkeypatch) -> None:
    responses = [FakeResponse(401, {}), FakeResponse(200, {"ok": True})]
    authorization_headers: list[str] = []

    def fake_get(url: str, headers: dict[str, str]) -> FakeResponse:
        authorization_headers.append(headers["Authorization"])
        return responses.pop(0)

    monkeypatch.setattr(fetch_data.requests, "get", fake_get)
    monkeypatch.setattr(
        fetch_data,
        "refresh_token",
        lambda token_data: {"access_token": "new-access"},
    )

    payload, token_data = fetch_data.api_get(
        "/test", {"access_token": "old-access"}
    )

    assert payload == {"ok": True}
    assert token_data == {"access_token": "new-access"}
    assert authorization_headers == ["Bearer old-access", "Bearer new-access"]
