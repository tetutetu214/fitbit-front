"""Fitbit・Tanita・Vaultの記録をBedrock向けMarkdownに束ねる。"""

import argparse
import json
import os
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
DEFAULT_VAULT_DIR = Path("/mnt/c/Users/lemon/Vault")
DEFAULT_PROFILE_FILE = PROJECT_ROOT / "profile" / "about_me.md"
MAX_CONTEXT_CHARS = 160_000

JsonObject = dict[str, Any]
MetricValue = int | float | None
WORKLOG_HEADING = re.compile(r"^## \d{2}:\d{2}(?:\s|$)")
FRONTMATTER_DATE = re.compile(r"^date:\s*(.+?)\s*$")
REPORT_FILENAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_analysis\.md$")

PROFILE_HEADING = "## 本人プロフィール"
PROFILE_MISSING_SECTION = (
    f"{PROFILE_HEADING}\n\n"
    "（未作成。profile/about_me.example.md をコピーして書く）"
)
PREVIOUS_HEADING = "## 前回の指示と予測"
PREVIOUS_NONE_SECTION = f"{PREVIOUS_HEADING}\n\n初回のため無し"
# 新プロンプトの見出しを先に探し、旧プロンプトで書かれたレポートも拾えるようにする。
INSTRUCTION_HEADINGS = ("## 今週の指示", "## 来週試す1つ")


@dataclass(frozen=True)
class WorklogEntry:
    heading: str
    body_lines: tuple[str, ...]


@dataclass(frozen=True)
class Reflection:
    filename: str
    reflection_date: date
    content: str


def iter_dates(start_date: date, end_date: date) -> Iterator[date]:
    """両端を含む日付を昇順で返す。"""
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _numeric(value: object) -> MetricValue:
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


def _objects(value: object) -> list[JsonObject]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _read_json(path: Path) -> JsonObject | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"警告: {path} を読み込めません: {error}", file=sys.stderr)
        return None
    if not isinstance(value, dict):
        print(f"警告: {path} のJSON直下がobjectではありません", file=sys.stderr)
        return None
    return value


def _first_record(container: object, key: str) -> JsonObject | None:
    if not isinstance(container, dict):
        return None
    records = _objects(container.get(key))
    return records[0] if records else None


def extract_fitbit_metrics(day: JsonObject | None) -> dict[str, MetricValue]:
    """generate_health_json.mjsと同じ参照元から日次値を取り出す。"""
    if day is None:
        return {
            "resting_hr": None,
            "hrv_rmssd": None,
            "sleep_minutes": None,
            "sleep_efficiency": None,
            "deep": None,
            "rem": None,
            "light": None,
            "wake": None,
            "spo2_avg": None,
            "steps": None,
            "sedentary_minutes": None,
            "active_minutes": None,
        }

    heart_record = _first_record(day.get("heartrate"), "activities-heart")
    heart_value = heart_record.get("value", {}) if heart_record else {}
    resting_hr = (
        _numeric(heart_value.get("restingHeartRate"))
        if isinstance(heart_value, dict)
        else None
    )

    hrv_record = _first_record(day.get("hrv"), "hrv")
    hrv_value = hrv_record.get("value", {}) if hrv_record else {}
    hrv_rmssd = (
        _numeric(hrv_value.get("dailyRmssd"))
        if isinstance(hrv_value, dict)
        else None
    )

    sleep_data = day.get("sleep")
    sleep_records = (
        _objects(sleep_data.get("sleep")) if isinstance(sleep_data, dict) else []
    )
    main_sleep = next(
        (record for record in sleep_records if record.get("isMainSleep") is True),
        None,
    )
    sleep_summary = (
        sleep_data.get("summary", {}) if isinstance(sleep_data, dict) else {}
    )
    if not isinstance(sleep_summary, dict):
        sleep_summary = {}
    stages = sleep_summary.get("stages", {})
    if not isinstance(stages, dict):
        stages = {}
    has_sleep = bool(sleep_records)
    sleep_minutes = (
        _numeric(sleep_summary.get("totalMinutesAsleep")) if has_sleep else None
    )
    sleep_efficiency = (
        _numeric(main_sleep.get("efficiency")) if main_sleep else None
    )

    spo2_data = day.get("spo2")
    if isinstance(spo2_data, list):
        spo2_record = next(
            (item for item in spo2_data if isinstance(item, dict)), None
        )
    elif isinstance(spo2_data, dict) and isinstance(spo2_data.get("spo2"), list):
        spo2_record = _first_record(spo2_data, "spo2")
    else:
        spo2_record = spo2_data if isinstance(spo2_data, dict) else None
    spo2_value = spo2_record.get("value", {}) if spo2_record else {}
    spo2_avg = (
        _numeric(spo2_value.get("avg"))
        if isinstance(spo2_value, dict)
        else None
    )

    activity = day.get("activity")
    summary = activity.get("summary", {}) if isinstance(activity, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    active_parts = [
        _numeric(summary.get("lightlyActiveMinutes")),
        _numeric(summary.get("fairlyActiveMinutes")),
        _numeric(summary.get("veryActiveMinutes")),
    ]
    active_minutes = (
        sum(value for value in active_parts if value is not None)
        if all(value is not None for value in active_parts)
        else None
    )

    return {
        "resting_hr": resting_hr,
        "hrv_rmssd": hrv_rmssd,
        "sleep_minutes": sleep_minutes,
        "sleep_efficiency": sleep_efficiency,
        "deep": _numeric(stages.get("deep")) if has_sleep else None,
        "rem": _numeric(stages.get("rem")) if has_sleep else None,
        "light": _numeric(stages.get("light")) if has_sleep else None,
        "wake": _numeric(stages.get("wake")) if has_sleep else None,
        "spo2_avg": spo2_avg,
        "steps": _numeric(summary.get("steps")),
        "sedentary_minutes": _numeric(summary.get("sedentaryMinutes")),
        "active_minutes": active_minutes,
    }


def extract_tanita_metrics(day: JsonObject | None) -> dict[str, MetricValue]:
    """mjsと同様に時刻順で最後に得られた体重・体脂肪率を返す。"""
    weight: MetricValue = None
    body_fat: MetricValue = None
    measurements = day.get("measurements", {}) if day else {}
    if not isinstance(measurements, dict):
        return {"weight": None, "body_fat": None}

    for timestamp in sorted(measurements):
        measurement = measurements[timestamp]
        if not isinstance(measurement, dict):
            continue
        current_weight = _numeric(measurement.get("weight"))
        current_body_fat = _numeric(measurement.get("body_fat"))
        if current_weight is not None:
            weight = current_weight
        if current_body_fat is not None:
            body_fat = current_body_fat
    return {"weight": weight, "body_fat": body_fat}


def _format_metric(value: MetricValue) -> str:
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _strip_frontmatter(content: str) -> str:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return content
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[index + 1 :])
    return content


def extract_worklog_entries(content: str) -> list[WorklogEntry]:
    """時刻付きH2と各本文の空行を除く先頭行を抽出する。"""
    lines = _strip_frontmatter(content).splitlines()
    entries: list[WorklogEntry] = []
    for index, line in enumerate(lines):
        if not WORKLOG_HEADING.match(line):
            continue
        section_end = len(lines)
        for candidate in range(index + 1, len(lines)):
            if lines[candidate].startswith("## "):
                section_end = candidate
                break
        body_lines = tuple(
            body_line
            for body_line in lines[index + 1 : section_end]
            if body_line.strip()
        )
        entries.append(WorklogEntry(heading=line, body_lines=body_lines))
    return entries


def _frontmatter_date(content: str) -> date | None:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = FRONTMATTER_DATE.match(line)
        if not match:
            continue
        raw_value = match.group(1).split("#", 1)[0].strip().strip("\"'")
        try:
            return date.fromisoformat(raw_value[:10])
        except ValueError:
            return None
    return None


def _load_reflections(
    vault_dir: Path, start_date: date, end_date: date
) -> list[Reflection]:
    reflection_dir = vault_dir / "wiki" / "reflections"
    if not reflection_dir.is_dir():
        return []

    reflections: list[Reflection] = []
    for path in sorted(reflection_dir.glob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            print(f"警告: {path} を読み込めません: {error}", file=sys.stderr)
            continue
        reflection_date = _frontmatter_date(content)
        if reflection_date is None or not start_date <= reflection_date <= end_date:
            continue
        reflections.append(
            Reflection(
                filename=path.name,
                reflection_date=reflection_date,
                content=content,
            )
        )
    return sorted(
        reflections, key=lambda item: (item.reflection_date, item.filename)
    )


def _date_list(values: list[str]) -> str:
    return ", ".join(values) if values else "なし"


def _render_table(
    dates: list[date],
    fitbit_by_date: dict[str, JsonObject],
    tanita_by_date: dict[str, JsonObject],
) -> str:
    lines = [
        "## 日次メトリクス",
        "",
        (
            "| 日付 | 安静時心拍 | HRV RMSSD | 睡眠時間(分) | 睡眠効率 | "
            "深い(分) | REM(分) | 浅い(分) | 覚醒(分) | SpO2 平均 | 歩数 | "
            "座位(分) | 活動(分: lightly+fairly+very) | 体重 | 体脂肪率 |"
        ),
        (
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
            "---:|---:|---:|"
        ),
    ]
    for current in dates:
        date_string = current.isoformat()
        fitbit = extract_fitbit_metrics(fitbit_by_date.get(date_string))
        tanita = extract_tanita_metrics(tanita_by_date.get(date_string))
        values = [
            date_string,
            _format_metric(fitbit["resting_hr"]),
            _format_metric(fitbit["hrv_rmssd"]),
            _format_metric(fitbit["sleep_minutes"]),
            _format_metric(fitbit["sleep_efficiency"]),
            _format_metric(fitbit["deep"]),
            _format_metric(fitbit["rem"]),
            _format_metric(fitbit["light"]),
            _format_metric(fitbit["wake"]),
            _format_metric(fitbit["spo2_avg"]),
            _format_metric(fitbit["steps"]),
            _format_metric(fitbit["sedentary_minutes"]),
            _format_metric(fitbit["active_minutes"]),
            _format_metric(tanita["weight"]),
            _format_metric(tanita["body_fat"]),
        ]
        lines.append(f"| {' | '.join(values)} |")
    return "\n".join(lines)


def _render_worklogs(
    dates: list[date],
    worklogs: dict[str, list[WorklogEntry]],
    vault_available: bool,
    body_char_limit: int | None,
) -> str:
    lines = ["## 日ごとの作業ログ", ""]
    if not vault_available:
        lines.append("なし")
        return "\n".join(lines)

    for current in dates:
        date_string = current.isoformat()
        lines.extend([f"### {date_string}", ""])
        entries = worklogs.get(date_string, [])
        if not entries:
            lines.extend(["なし", ""])
            continue
        for entry in entries:
            lines.append(entry.heading)
            # worklog本文は1段落=1行のことが多く行数では縮まないため、文字数で打ち切る。
            body_text = "\n".join(entry.body_lines)
            if body_char_limit == 0:
                # 最終段階は見出しのみに落とす。
                body_text = ""
            elif body_char_limit is not None and len(body_text) > body_char_limit:
                body_text = f"{body_text[:body_char_limit]}…"
            if body_text:
                lines.append(body_text)
            lines.append("")
    return "\n".join(lines).rstrip()


def _render_reflections(reflections: list[Reflection]) -> str:
    lines = ["## Reflections", ""]
    if not reflections:
        lines.append("なし")
        return "\n".join(lines)
    for reflection in reflections:
        lines.extend(
            [
                f"### {reflection.reflection_date} — {reflection.filename}",
                "",
                reflection.content.rstrip(),
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def _render_profile(profile_file: Path) -> str:
    """本人プロフィールを全文で節にする。無ければ作成を促す文言を返す。"""
    if not profile_file.is_file():
        return PROFILE_MISSING_SECTION
    try:
        content = profile_file.read_text(encoding="utf-8")
    except OSError as error:
        print(f"警告: {profile_file} を読み込めません: {error}", file=sys.stderr)
        return PROFILE_MISSING_SECTION
    body = content.strip()
    if not body:
        return PROFILE_MISSING_SECTION
    return f"{PROFILE_HEADING}\n\n{body}"


def _report_date(filename: str) -> date | None:
    match = REPORT_FILENAME.match(filename)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def _latest_report(reports_dir: Path, end_date: date) -> tuple[date, Path] | None:
    """end_dateより後の日付を除いた中で最新の分析レポートを返す。"""
    if not reports_dir.is_dir():
        return None
    candidates: list[tuple[date, Path]] = []
    for path in sorted(reports_dir.glob("*_analysis.md")):
        report_date = _report_date(path.name)
        if report_date is None or report_date > end_date:
            continue
        candidates.append((report_date, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1].name))


def _resolve_previous_report(
    previous_report: Path | None, reports_dir: Path, end_date: date
) -> tuple[date | None, Path] | None:
    if previous_report is None:
        return _latest_report(reports_dir, end_date)
    if not previous_report.is_file():
        print(f"警告: {previous_report} が見つかりません", file=sys.stderr)
        return None
    return (_report_date(previous_report.name), previous_report)


def extract_instruction_section(content: str) -> str:
    """レポートから指示の節だけを、次のH2見出しの手前まで取り出す。"""
    lines = _strip_frontmatter(content).splitlines()
    for heading in INSTRUCTION_HEADINGS:
        for index, line in enumerate(lines):
            if line.strip() != heading:
                continue
            section_end = len(lines)
            for candidate in range(index + 1, len(lines)):
                if lines[candidate].startswith("## "):
                    section_end = candidate
                    break
            body_lines = list(lines[index + 1 : section_end])
            # 節の末尾に残る区切り線と空行は落とす。
            while body_lines and body_lines[-1].strip() in ("", "---"):
                body_lines.pop()
            body = "\n".join(body_lines).strip()
            if body:
                return body
    return ""


def _render_previous(report: tuple[date | None, Path] | None) -> str:
    if report is None:
        return PREVIOUS_NONE_SECTION
    report_date, path = report
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"警告: {path} を読み込めません: {error}", file=sys.stderr)
        return PREVIOUS_NONE_SECTION
    section = extract_instruction_section(content)
    if not section:
        return PREVIOUS_NONE_SECTION
    if report_date is None:
        return f"{PREVIOUS_HEADING}\n\n{section}"
    return f"{PREVIOUS_HEADING}（{report_date} 作成）\n\n{section}"


def build_context(
    days: int,
    end_date: date,
    data_dir: Path | None = None,
    vault_dir: Path | None = None,
    max_chars: int = MAX_CONTEXT_CHARS,
    profile_file: Path | None = None,
    previous_report: Path | None = None,
) -> str:
    """指定期間の入力を読み、上限内のMarkdownを返す。"""
    if days < 1:
        raise ValueError("days は1以上である必要があります")
    if max_chars < 1:
        raise ValueError("max_chars は1以上である必要があります")

    resolved_data_dir = data_dir or DATA_DIR
    resolved_vault_dir = vault_dir or Path(
        os.environ.get("VAULT_DIR") or DEFAULT_VAULT_DIR
    )
    resolved_profile_file = profile_file or Path(
        os.environ.get("PROFILE_FILE") or DEFAULT_PROFILE_FILE
    )
    start_date = end_date - timedelta(days=days - 1)
    dates = list(iter_dates(start_date, end_date))

    fitbit_by_date: dict[str, JsonObject] = {}
    tanita_by_date: dict[str, JsonObject] = {}
    fitbit_missing: list[str] = []
    tanita_missing: list[str] = []
    for current in dates:
        date_string = current.isoformat()
        fitbit = _read_json(resolved_data_dir / "daily" / f"{date_string}.json")
        tanita = _read_json(
            resolved_data_dir / "daily_tanita" / f"{date_string}.json"
        )
        if fitbit is None:
            fitbit_missing.append(date_string)
        else:
            fitbit_by_date[date_string] = fitbit
        if tanita is None:
            tanita_missing.append(date_string)
        else:
            tanita_by_date[date_string] = tanita

    vault_available = resolved_vault_dir.is_dir()
    worklogs: dict[str, list[WorklogEntry]] = {}
    worklog_missing: list[str] = []
    if vault_available:
        for current in dates:
            date_string = current.isoformat()
            path = resolved_vault_dir / "worklog" / f"{date_string}.md"
            try:
                content = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                worklog_missing.append(date_string)
                continue
            except OSError as error:
                print(f"警告: {path} を読み込めません: {error}", file=sys.stderr)
                worklog_missing.append(date_string)
                continue
            worklogs[date_string] = extract_worklog_entries(content)
        reflections = _load_reflections(
            resolved_vault_dir, start_date, end_date
        )
    else:
        reflections = []

    missing_lines = [
        "## 期間と欠測日の一覧",
        "",
        f"- 期間: {start_date}〜{end_date} ({days}日)",
        f"- Fitbit 欠測日: {_date_list(fitbit_missing)}",
        f"- Tanita 欠測日: {_date_list(tanita_missing)}",
    ]
    if vault_available:
        missing_lines.append(
            f"- Worklog 欠測日: {_date_list(worklog_missing)}"
        )
    else:
        missing_lines.append("- Worklog 欠測日: Vault ディレクトリなし")
    missing_section = "\n".join(missing_lines)
    table_section = _render_table(dates, fitbit_by_date, tanita_by_date)
    reflection_section = _render_reflections(reflections)
    profile_section = _render_profile(resolved_profile_file)
    previous_section = _render_previous(
        _resolve_previous_report(
            previous_report, resolved_data_dir / "reports", end_date
        )
    )

    for body_char_limit in (None, 600, 400, 300, 200, 0):
        context = "\n\n".join(
            [
                "# 体調分析コンテキスト",
                # プロフィールと前回の指示は縮約対象外。最終段階でも全文を残す。
                profile_section,
                missing_section,
                table_section,
                _render_worklogs(
                    dates, worklogs, vault_available, body_char_limit
                ),
                reflection_section,
                previous_section,
            ]
        )
        context = f"{context}\n"
        if len(context) <= max_chars:
            return context

    raise ValueError(
        "worklog本文を省略してもcontextが文字数上限を超えます"
    )


def write_context(
    days: int,
    end_date: date,
    data_dir: Path | None = None,
    vault_dir: Path | None = None,
    max_chars: int = MAX_CONTEXT_CHARS,
    profile_file: Path | None = None,
    previous_report: Path | None = None,
) -> Path:
    """contextを生成してdata/contextへ保存する。"""
    resolved_data_dir = data_dir or DATA_DIR
    context = build_context(
        days=days,
        end_date=end_date,
        data_dir=resolved_data_dir,
        vault_dir=vault_dir,
        max_chars=max_chars,
        profile_file=profile_file,
        previous_report=previous_report,
    )
    output_dir = resolved_data_dir / "context"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{end_date.isoformat()}_context.md"
    output_path.write_text(context, encoding="utf-8")
    return output_path


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


def _today_in_japan() -> date:
    return datetime.now(tz=ZoneInfo("Asia/Tokyo")).date()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fitbit・Tanita・VaultをBedrock向けMarkdownに束ねます"
    )
    parser.add_argument("--days", type=_positive_int, default=60, help="対象日数")
    parser.add_argument(
        "--end",
        type=_iso_date,
        default=_today_in_japan(),
        help="終了日 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--max-chars",
        type=_positive_int,
        default=MAX_CONTEXT_CHARS,
        help=f"contextの文字数上限 (既定: {MAX_CONTEXT_CHARS})",
    )
    parser.add_argument(
        "--previous",
        type=Path,
        default=None,
        help="前回レポートのパス (既定: data/reports から自動選択)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output_path = write_context(
            args.days,
            args.end,
            max_chars=args.max_chars,
            previous_report=args.previous,
        )
    except ValueError as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    print(f"生成: {output_path}")
    total_chars = len(output_path.read_text(encoding="utf-8"))
    print(f"合計文字数: {total_chars}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
