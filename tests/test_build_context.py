# 個人データを含む実data/Vaultに依存せず欠測も再現できるよう、tmp_pathで構成を模擬する。

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from scripts import build_context


@pytest.fixture(autouse=True)
def isolate_profile(tmp_path, monkeypatch) -> None:
    """本人の実プロフィールをテストへ混入させない。既定は未作成扱いにする。"""
    monkeypatch.setenv("PROFILE_FILE", str(tmp_path / "no-profile.md"))


def _write_profile(tmp_path: Path, body: str) -> Path:
    profile_file = tmp_path / "profile" / "about_me.md"
    profile_file.parent.mkdir(parents=True, exist_ok=True)
    profile_file.write_text(body, encoding="utf-8")
    return profile_file


def _write_report(data_dir: Path, name: str, body: str) -> Path:
    report_path = data_dir / "reports" / name
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(body, encoding="utf-8")
    return report_path


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fitbit_day() -> dict[str, Any]:
    return {
        "heartrate": {
            "activities-heart": [
                {"dateTime": "2026-04-01", "value": {"restingHeartRate": 61}}
            ]
        },
        "hrv": {
            "hrv": [
                {
                    "dateTime": "2026-04-01",
                    "value": {"dailyRmssd": 28.5},
                }
            ]
        },
        "sleep": {
            "sleep": [
                {
                    "isMainSleep": False,
                    "efficiency": 50,
                    "startTime": "2026-04-01T14:00:00.000",
                    "endTime": "2026-04-01T14:40:00.000",
                },
                {
                    "isMainSleep": True,
                    "efficiency": 90,
                    "startTime": "2026-03-31T23:45:00.000",
                    "endTime": "2026-04-01T05:47:00.000",
                },
            ],
            "summary": {
                "totalMinutesAsleep": 420,
                "stages": {"deep": 70, "rem": 80, "light": 240, "wake": 30},
            },
        },
        "spo2": {"dateTime": "2026-04-01", "value": {"avg": 96.2}},
        "activity": {
            "summary": {
                "steps": 8000,
                "sedentaryMinutes": 700,
                "lightlyActiveMinutes": 40,
                "fairlyActiveMinutes": 20,
                "veryActiveMinutes": 5,
            }
        },
    }


def test_context_keeps_missing_days_and_bundles_vault_records(tmp_path) -> None:
    data_dir = tmp_path / "data"
    vault_dir = tmp_path / "vault"
    _write_json(data_dir / "daily" / "2026-04-01.json", _fitbit_day())
    _write_json(
        data_dir / "daily" / "2026-04-03.json",
        {
            "heartrate": {"activities-heart": []},
            "hrv": {"hrv": []},
            "sleep": {"sleep": [], "summary": {}},
            "spo2": {},
            "activity": {"summary": {}},
        },
    )
    _write_json(
        data_dir / "daily_tanita" / "2026-04-02.json",
        {
            "measurements": {
                "2026-04-02 08:00": {"weight": 57.4, "body_fat": 16.5},
                "2026-04-02 20:00": {"weight": 57.5, "body_fat": 16.9},
            }
        },
    )

    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True)
    worklog_path.write_text(
        """---
author: hidden-frontmatter
---
# Worklog
## 09:00 Alpha — 実装
本文一行目
本文二行目
本文三行目

## 10:30 Beta — レビュー
Beta一行目
Beta二行目
Beta三行目
""",
        encoding="utf-8",
    )
    reflection_dir = vault_dir / "wiki" / "reflections"
    reflection_dir.mkdir(parents=True)
    (reflection_dir / "in-range.md").write_text(
        """---
date: 2026-04-02
---
## 事実
期間内のreflection全文
""",
        encoding="utf-8",
    )
    (reflection_dir / "without-date.md").write_text(
        """---
tags: reflection
---
dateなしは含めない
""",
        encoding="utf-8",
    )
    (reflection_dir / "out-of-range.md").write_text(
        """---
date: 2026-03-31
---
期間外は含めない
""",
        encoding="utf-8",
    )

    context = build_context.build_context(
        days=3,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        vault_dir=vault_dir,
    )

    assert "- 期間: 2026-04-01〜2026-04-03 (3日)" in context
    assert "- Fitbit 欠測日: 2026-04-02" in context
    first_day_row = next(
        line for line in context.splitlines() if line.startswith("| 2026-04-01 ")
    )
    assert "| 61 | 28.5 | 23:45 | 05:47 | 420 | 90 |" in first_day_row
    assert "| 65 | - | - |" in first_day_row
    second_day_row = next(
        line for line in context.splitlines() if line.startswith("| 2026-04-02 ")
    )
    assert second_day_row.endswith("| 57.5 | 16.9 |")
    assert "## 09:00 Alpha — 実装" in context
    assert "本文一行目" in context
    assert "本文二行目" in context
    assert "本文三行目" in context
    assert "hidden-frontmatter" not in context
    assert "### 2026-04-02\n\nなし" in context
    assert "期間内のreflection全文" in context
    assert "dateなしは含めない" not in context
    assert "期間外は含めない" not in context


def test_missing_vault_outputs_none_without_failing(tmp_path) -> None:
    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=tmp_path / "missing-vault",
    )

    assert "- Worklog 欠測日: Vault ディレクトリなし" in context
    assert "## 日ごとの作業ログ\n\nなし" in context
    assert "## Reflections\n\nなし" in context


def _write_worklog(vault_dir: Path, body: str) -> None:
    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True, exist_ok=True)
    worklog_path.write_text(
        f"## 09:00 Large entry\n{body}\n", encoding="utf-8"
    )


def test_worklog_body_stays_full_when_context_fits_in_the_limit(tmp_path) -> None:
    vault_dir = tmp_path / "vault"
    body = "短い本文なので打ち切られない。"
    _write_worklog(vault_dir, body)

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
    )

    assert body in context
    assert "…" not in context


def test_oversized_worklog_body_is_first_truncated_to_600_characters(
    tmp_path,
) -> None:
    vault_dir = tmp_path / "vault"
    # 1エントリで上限を超え、最初の段階(600文字)に落ちる長さにする。
    body = "あ" * 200_000
    _write_worklog(vault_dir, body)

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
    )

    assert len(context) <= build_context.MAX_CONTEXT_CHARS
    assert "あ" * 600 + "…" in context
    assert "あ" * 601 not in context


def test_single_paragraph_worklog_bodies_shrink_stepwise(tmp_path) -> None:
    vault_dir = tmp_path / "vault"
    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True)
    # 実データと同じく1段落=1行。行数基準では縮まらないので400文字段階まで落ちる。
    entries = "\n".join(
        f"## 00:00 Entry {index}\n{'あ' * 1_000}" for index in range(300)
    )
    worklog_path.write_text(f"{entries}\n", encoding="utf-8")

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
    )

    assert len(context) <= build_context.MAX_CONTEXT_CHARS
    assert "あ" * 400 + "…" in context
    assert "あ" * 401 not in context
    # 全300エントリが本文つきで残る（見出しのみに落ちていない）。
    assert context.count("…") == 300


def test_worklog_falls_back_to_headings_only_when_truncation_is_not_enough(
    tmp_path,
) -> None:
    vault_dir = tmp_path / "vault"
    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True)
    # 200文字に打ち切っても収まらない件数にして、見出しのみの段階を踏ませる。
    entries = "\n".join(
        f"## 00:00 Entry {index}\n{'あ' * 1_000}" for index in range(2_000)
    )
    worklog_path.write_text(f"{entries}\n", encoding="utf-8")

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
        max_chars=100_000,
    )

    assert len(context) <= 100_000
    assert "## 00:00 Entry 0" in context
    assert "あ" not in context


def test_reflections_are_dropped_oldest_first_when_limit_is_tight(
    tmp_path, capsys
) -> None:
    vault_dir = tmp_path / "vault"
    reflection_dir = vault_dir / "wiki" / "reflections"
    reflection_dir.mkdir(parents=True)
    for date_string, filename, marker in (
        ("2026-04-01", "oldest.md", "最も古いReflection"),
        ("2026-04-02", "middle.md", "中間のReflection"),
        ("2026-04-03", "newest.md", "最も新しいReflection"),
    ):
        (reflection_dir / filename).write_text(
            f"---\ndate: {date_string}\n---\n{marker}\n{'あ' * 1_200}\n",
            encoding="utf-8",
        )

    context = build_context.build_context(
        days=3,
        end_date=date(2026, 4, 3),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
        max_chars=3_000,
    )

    captured = capsys.readouterr()
    assert "最も古いReflection" not in context
    assert "中間のReflection" not in context
    assert "最も新しいReflection" in context
    assert "Reflections を古い順に 2 本省略しました" in captured.err


def test_main_prints_generated_context_character_count(
    tmp_path, monkeypatch, capsys
) -> None:
    data_dir = tmp_path / "data"
    vault_dir = tmp_path / "missing-vault"
    monkeypatch.setattr(build_context, "DATA_DIR", data_dir)
    monkeypatch.setenv("VAULT_DIR", str(vault_dir))

    exit_code = build_context.main(
        [
            "--days",
            "1",
            "--end",
            "2026-04-01",
            "--max-chars",
            "10000",
        ]
    )

    output_path = data_dir / "context" / "2026-04-01_context.md"
    total_chars = len(output_path.read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"合計文字数: {total_chars}" in captured.out


def test_profile_is_bundled_in_full_at_the_top_of_the_context(tmp_path) -> None:
    profile_file = _write_profile(
        tmp_path,
        "## 生活\n朝のトレーニングを毎日する。\n\n## 目標\n体脂肪率を15%にする。\n",
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=tmp_path / "missing-vault",
        profile_file=profile_file,
    )

    assert context.startswith(
        "# 体調分析コンテキスト\n\n## 本人プロフィール\n\n"
        "## 生活\n朝のトレーニングを毎日する。\n\n## 目標\n体脂肪率を15%にする。\n\n"
        "## 期間と欠測日の一覧"
    )


def test_absent_profile_shows_the_setup_guidance(tmp_path) -> None:
    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=tmp_path / "missing-vault",
        profile_file=tmp_path / "profile" / "about_me.md",
    )

    assert (
        "## 本人プロフィール\n\n（未作成。profile/about_me.example.md をコピーして書く）"
        in context
    )


def test_profile_stays_full_even_when_worklog_shrinks_to_headings_only(
    tmp_path,
) -> None:
    profile_body = "## 生活\n" + "朝のトレーニングは固定。" * 100
    profile_file = _write_profile(tmp_path, f"{profile_body}\n")
    vault_dir = tmp_path / "vault"
    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True)
    entries = "\n".join(
        f"## 00:00 Entry {index}\n{'あ' * 1_000}" for index in range(2_000)
    )
    worklog_path.write_text(f"{entries}\n", encoding="utf-8")

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
        max_chars=100_000,
        profile_file=profile_file,
    )

    # worklogは見出しのみまで縮んでも、プロフィールは全文が残る。
    assert "あ" not in context
    assert profile_body in context


def test_only_the_weekly_instruction_section_of_the_previous_report_is_bundled(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    _write_report(
        data_dir,
        "2026-03-25_analysis.md",
        """---
generated_at: "2026-03-25T20:00:00+09:00"
---
## 今の状態

安静時心拍数は61bpm。

## 今週の指示

**23時以降の作業を避ける**

- 根拠データ: 03-20の睡眠効率91%

## 指示の確認

就寝時刻は自分で決められるか。
""",
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    assert context.endswith(
        "## 前回の指示と予測（2026-03-25 作成）\n\n"
        "**23時以降の作業を避ける**\n\n"
        "- 根拠データ: 03-20の睡眠効率91%\n"
    )
    assert "安静時心拍数は61bpm。" not in context
    assert "就寝時刻は自分で決められるか。" not in context
    assert 'generated_at: "2026-03-25T20:00:00+09:00"' not in context


def test_prompt_heading_with_parentheses_is_extracted() -> None:
    section = build_context.extract_instruction_section(
        """## 今週の指示（優先順に 3 つまで）

**23時30分までに就寝する**

## 指示の確認

実行できたか確認する。
"""
    )

    assert section == "**23時30分までに就寝する**"


def test_existing_report_without_instruction_section_warns(
    tmp_path, capsys
) -> None:
    data_dir = tmp_path / "data"
    _write_report(
        data_dir,
        "2026-03-25_analysis.md",
        "## 今の状態\n\n指示節がないレポート\n",
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    captured = capsys.readouterr()
    assert context.endswith("## 前回の指示と予測\n\n初回のため無し\n")
    assert "前回の指示節を抜粋できません" in captured.err


def test_absent_previous_report_is_reported_as_the_first_run(tmp_path) -> None:
    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=tmp_path / "missing-vault",
    )

    assert context.endswith("## 前回の指示と予測\n\n初回のため無し\n")


def test_report_dated_on_or_after_end_date_is_not_chosen_as_previous(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    _write_report(
        data_dir,
        "2026-03-25_analysis.md",
        "## 今週の指示\n\n過去のレポートの指示\n",
    )
    _write_report(
        data_dir,
        "2026-04-01_analysis.md",
        "## 今週の指示\n\n同日のレポートの指示\n",
    )
    _write_report(
        data_dir,
        "2026-04-08_analysis.md",
        "## 今週の指示\n\n未来のレポートの指示\n",
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    assert "## 前回の指示と予測（2026-03-25 作成）" in context
    assert "過去のレポートの指示" in context
    assert "同日のレポートの指示" not in context
    assert "未来のレポートの指示" not in context


def _fitbit_day_with_sleep_times(start_time: str, end_time: str) -> dict[str, Any]:
    day = _fitbit_day()
    day["sleep"]["sleep"] = [
        {
            "isMainSleep": True,
            "efficiency": 90,
            "startTime": start_time,
            "endTime": end_time,
        }
    ]
    return day


def test_main_sleep_bedtime_and_wake_time_appear_as_hh_mm_in_the_table(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    _write_json(
        data_dir / "daily" / "2026-04-01.json",
        _fitbit_day_with_sleep_times(
            "2026-03-31T00:12:00.000", "2026-04-01T05:47:00.000"
        ),
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    header = next(
        line for line in context.splitlines() if line.startswith("| 日付 ")
    )
    row = next(
        line for line in context.splitlines() if line.startswith("| 2026-04-01 ")
    )
    assert "| 就寝 | 起床 | 睡眠時間(分) |" in header
    assert "| 00:12 | 05:47 | 420 |" in row


def test_day_without_sleep_records_shows_hyphens_for_bedtime_and_wake_time(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    day = _fitbit_day()
    day["sleep"] = {"sleep": [], "summary": {}}
    _write_json(data_dir / "daily" / "2026-04-01.json", day)

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    row = next(
        line for line in context.splitlines() if line.startswith("| 2026-04-01 ")
    )
    assert "| 61 | 28.5 | - | - | - |" in row


def test_bedtime_and_wake_time_medians_and_in_range_days_are_summarised(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    # 3日分: 起床は2日が5:30〜6:00に入り、就寝は2日が23:30〜00:30に入る。
    schedule = {
        "2026-04-01": ("2026-03-31T23:40:00.000", "2026-04-01T05:45:00.000"),
        "2026-04-02": ("2026-04-02T00:10:00.000", "2026-04-02T05:47:00.000"),
        "2026-04-03": ("2026-04-02T22:00:00.000", "2026-04-03T07:10:00.000"),
    }
    for date_string, (start_time, end_time) in schedule.items():
        _write_json(
            data_dir / "daily" / f"{date_string}.json",
            _fitbit_day_with_sleep_times(start_time, end_time),
        )

    context = build_context.build_context(
        days=3,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    assert "- 就寝時刻: 中央値 23:40、23:30〜00:30 の範囲が 2/3 日" in context
    assert "- 起床時刻: 中央値 05:47、05:30〜06:00 の範囲が 2/3 日" in context


def test_sleep_time_summary_reports_no_valid_days_when_records_are_absent(
    tmp_path,
) -> None:
    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=tmp_path / "missing-vault",
    )

    assert "- 起床時刻: 有効日なし（05:30〜06:00 の範囲が 0/0 日）" in context


def test_longest_sleep_is_used_when_no_record_is_flagged_as_main(tmp_path) -> None:
    data_dir = tmp_path / "data"
    day = _fitbit_day()
    day["sleep"]["sleep"] = [
        {
            "efficiency": 80,
            "duration": 3_600_000,
            "startTime": "2026-04-01T13:00:00.000",
            "endTime": "2026-04-01T14:00:00.000",
        },
        {
            "efficiency": 92,
            "duration": 21_600_000,
            "startTime": "2026-03-31T23:55:00.000",
            "endTime": "2026-04-01T05:55:00.000",
        },
    ]
    _write_json(data_dir / "daily" / "2026-04-01.json", day)

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    row = next(
        line for line in context.splitlines() if line.startswith("| 2026-04-01 ")
    )
    assert "| 23:55 | 05:55 | 420 | 92 |" in row


def _tanita_day(weight: float, body_fat: float) -> dict[str, Any]:
    return {"measurements": {"08:00": {"weight": weight, "body_fat": body_fat}}}


def test_only_measured_days_are_listed_in_date_order(tmp_path) -> None:
    data_dir = tmp_path / "data"
    # 3日中2日だけ計測。書き込み順は新しい日付が先でも一覧は古い順になる。
    _write_json(
        data_dir / "daily_tanita" / "2026-04-03.json", _tanita_day(55.0, 15.4)
    )
    _write_json(
        data_dir / "daily_tanita" / "2026-04-01.json", _tanita_day(57.4, 16.5)
    )

    context = build_context.build_context(
        days=3,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    assert (
        "- Tanita 計測日 (2 日): 2026-04-01 57.4kg/16.5%, "
        "2026-04-03 55.0kg/15.4%" in context
    )


def test_last_measurement_date_is_the_latest_measured_day(tmp_path) -> None:
    data_dir = tmp_path / "data"
    _write_json(
        data_dir / "daily_tanita" / "2026-04-01.json", _tanita_day(57.4, 16.5)
    )
    _write_json(
        data_dir / "daily_tanita" / "2026-04-03.json", _tanita_day(55.0, 15.4)
    )
    # 最終日は計測なし。表の最終行ではなく最後の計測日を指すことを確かめる。
    _write_json(data_dir / "daily_tanita" / "2026-04-05.json", {})

    context = build_context.build_context(
        days=5,
        end_date=date(2026, 4, 5),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    assert "- Tanita 最終計測日: 2026-04-03" in context


def test_measurement_list_says_none_when_no_day_was_measured(tmp_path) -> None:
    context = build_context.build_context(
        days=3,
        end_date=date(2026, 4, 3),
        data_dir=tmp_path / "data",
        vault_dir=tmp_path / "missing-vault",
    )

    assert "- Tanita 計測日: なし" in context
    assert "- Tanita 最終計測日:" not in context


def test_write_context_keeps_the_weekly_default_output_path(tmp_path) -> None:
    data_dir = tmp_path / "data"

    output_path = build_context.write_context(
        days=1,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
    )

    assert output_path == data_dir / "context" / "2026-04-03_context.md"


def test_write_context_uses_the_explicit_output_path(tmp_path) -> None:
    data_dir = tmp_path / "data"
    requested_path = data_dir / "context" / "2026-04-04_coach_context.md"

    output_path = build_context.write_context(
        days=1,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        vault_dir=tmp_path / "missing-vault",
        output_path=requested_path,
    )

    assert output_path == requested_path
    assert requested_path.is_file()
    assert not (data_dir / "context" / "2026-04-03_context.md").exists()
