# 個人データを含む実data/Vaultに依存せず欠測も再現できるよう、tmp_pathで構成を模擬する。

import json
from datetime import date
from pathlib import Path
from typing import Any

from scripts import build_context


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
                {"isMainSleep": False, "efficiency": 50},
                {"isMainSleep": True, "efficiency": 90},
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
    assert "| 61 | 28.5 | 420 | 90 |" in first_day_row
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


def test_worklog_body_lines_are_reduced_below_120000_characters(tmp_path) -> None:
    vault_dir = tmp_path / "vault"
    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True)
    first_line = "A" * 110_000
    second_line = "B" * 110_000
    worklog_path.write_text(
        f"## 09:00 Large entry\n{first_line}\n{second_line}\n",
        encoding="utf-8",
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
    )

    assert len(context) <= build_context.MAX_CONTEXT_CHARS
    assert first_line in context
    assert second_line not in context


def test_worklog_is_first_reduced_to_five_body_lines(tmp_path) -> None:
    vault_dir = tmp_path / "vault"
    worklog_path = vault_dir / "worklog" / "2026-04-01.md"
    worklog_path.parent.mkdir(parents=True)
    body_lines = [character * 20_000 for character in "ABCDEF"]
    worklog_path.write_text(
        "## 09:00 Large entry\n" + "\n".join(body_lines) + "\n",
        encoding="utf-8",
    )

    context = build_context.build_context(
        days=1,
        end_date=date(2026, 4, 1),
        data_dir=tmp_path / "data",
        vault_dir=vault_dir,
    )

    assert len(context) <= build_context.MAX_CONTEXT_CHARS
    assert body_lines[4] in context
    assert body_lines[5] not in context


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
