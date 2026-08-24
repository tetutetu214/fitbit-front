"""日次コーチカード生成を排他実行する薄いオーケストレータ。"""

import argparse
import errno
import fcntl
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
COACH_HEADINGS = (
    "## 今日の一手",
    "## 昨日の答え合わせ",
    "## 根拠データ",
    "## 注意",
)
MAX_BODY_CHARS = 1_200
WEEKLY_REPORT_FILENAME = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_analysis\.md$"
)
YAML_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
INTEGER = re.compile(r"^-?(?:0|[1-9]\d*)$")
FLOAT = re.compile(
    r"^-?(?:0|[1-9]\d*)\.\d+(?:[eE][+-]?\d+)?$"
)

YamlValue = str | int | float | bool | None
CommandRunner = Callable[[Sequence[str], Path], int]


class CoachReportError(ValueError):
    """コーチカードの形式が契約を満たさない。"""


@dataclass(frozen=True)
class CoachReport:
    """検証済みコーチカードの frontmatter と4セクション。"""

    frontmatter: Mapping[str, YamlValue]
    sections: tuple[tuple[str, str], ...]


def _parse_yaml_scalar(raw_value: str) -> YamlValue:
    value = raw_value.strip()
    if not value:
        raise CoachReportError("frontmatterの値が空です")
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as error:
            raise CoachReportError(
                "frontmatterの引用文字列が不正です"
            ) from error
        if not isinstance(parsed, str):
            raise CoachReportError("frontmatterの複合値は使用できません")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise CoachReportError("frontmatterの引用文字列が不正です")
        return value[1:-1].replace("''", "'")
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if INTEGER.fullmatch(value):
        return int(value)
    if FLOAT.fullmatch(value):
        return float(value)
    if value[0] in "[{&*!|>@`" or value.endswith(('"', "'")):
        raise CoachReportError("frontmatterの値が不正です")
    return value


def _split_frontmatter(content: str) -> tuple[dict[str, YamlValue], str]:
    # Node側と同じくLFだけで分割し、frontmatterのキーと値はstrip後に比較する。
    lines = content.split("\n")
    if not lines or lines[0] != "---":
        raise CoachReportError("YAML frontmatterがありません")
    try:
        boundary = lines.index("---", 1)
    except ValueError as error:
        raise CoachReportError(
            "YAML frontmatterの終端がありません"
        ) from error

    frontmatter: dict[str, YamlValue] = {}
    for line in lines[1:boundary]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, raw_value = line.partition(":")
        key = key.strip()
        raw_value = raw_value.strip()
        if not separator or not YAML_KEY.fullmatch(key):
            raise CoachReportError("frontmatterがYAML mappingではありません")
        if key in frontmatter:
            raise CoachReportError(f"frontmatterのキーが重複しています: {key}")
        frontmatter[key] = _parse_yaml_scalar(raw_value)

    body = "\n".join(lines[boundary + 1 :]).strip()
    return frontmatter, body


def _validate_api_metadata(frontmatter: Mapping[str, YamlValue]) -> None:
    model_id = frontmatter.get("model_id")
    generated_at = frontmatter.get("generated_at")
    days = frontmatter.get("days")
    if not isinstance(model_id, str) or not model_id:
        raise CoachReportError("frontmatterのmodel_idが不正です")
    if not isinstance(generated_at, str):
        raise CoachReportError("frontmatterのgenerated_atが不正です")
    try:
        timestamp = datetime.fromisoformat(generated_at)
    except ValueError as error:
        raise CoachReportError(
            "frontmatterのgenerated_atが不正です"
        ) from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise CoachReportError("generated_atにタイムゾーンがありません")
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise CoachReportError("frontmatterのdaysが不正です")


def parse_coach_report(content: str) -> CoachReport:
    """frontmatterと本文を検証し、4セクションに分割する。"""
    frontmatter, body = _split_frontmatter(content)
    _validate_api_metadata(frontmatter)
    if len(body) > MAX_BODY_CHARS:
        raise CoachReportError("本文が1,200文字を超えています")

    lines = body.split("\n")
    headings = [line for line in lines if line.startswith("## ")]
    if headings != list(COACH_HEADINGS):
        raise CoachReportError("4見出しの種類・順序・回数が不正です")

    heading_positions = [lines.index(heading) for heading in COACH_HEADINGS]
    sections: list[tuple[str, str]] = []
    for index, heading in enumerate(COACH_HEADINGS):
        start = heading_positions[index] + 1
        end = (
            heading_positions[index + 1]
            if index + 1 < len(heading_positions)
            else len(lines)
        )
        section_body = "\n".join(lines[start:end]).strip()
        if not section_body:
            raise CoachReportError(f"セクション本文が空です: {heading}")
        sections.append((heading.removeprefix("## "), section_body))
    return CoachReport(frontmatter, tuple(sections))


def validate_coach_file(path: Path) -> CoachReport:
    """ファイルを読み、コーチカード契約を検証する。"""
    return parse_coach_report(path.read_text(encoding="utf-8"))


def find_latest_weekly_report(
    reports_dir: Path, target_date: date
) -> Path | None:
    """対象日以前で最新の日付を持つ週次レポートを返す。"""
    candidates: list[tuple[date, Path]] = []
    for path in reports_dir.glob("*_analysis.md"):
        match = WEEKLY_REPORT_FILENAME.fullmatch(path.name)
        if match is None:
            continue
        try:
            report_date = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if report_date <= target_date:
            candidates.append((report_date, path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1].name))[1]


def _default_command_runner(command: Sequence[str], cwd: Path) -> int:
    completed = subprocess.run(list(command), cwd=cwd, check=False)
    return completed.returncode


def _run_step(
    label: str,
    command: Sequence[str],
    runner: CommandRunner,
    project_root: Path,
) -> int | None:
    try:
        return runner(command, project_root)
    except OSError as error:
        print(f"{label} の起動に失敗しました: {error}", file=sys.stderr)
        return None


def _append_previous_card(context_path: Path, card_path: Path) -> None:
    context = context_path.read_text(encoding="utf-8").rstrip()
    card = card_path.read_text(encoding="utf-8").rstrip()
    appended = f"{context}\n\n## 前日のコーチカード\n\n{card}\n"
    context_path.write_text(appended, encoding="utf-8")


def _reject_output(tmp_path: Path, rejected_path: Path, reason: str) -> int:
    if tmp_path.is_file():
        os.replace(tmp_path, rejected_path)
    print(f"出力検証に失敗しました: {reason}", file=sys.stderr)
    return 1


def _run_pipeline(
    target_date: date,
    model_id: str,
    days: int,
    data_dir: Path,
    project_root: Path,
    runner: CommandRunner,
) -> int:
    coach_dir = data_dir / "reports" / "coach"
    final_path = coach_dir / f"{target_date.isoformat()}_coach.md"
    tmp_path = coach_dir / f".{target_date.isoformat()}_coach.md.tmp"
    rejected_path = coach_dir / f".{target_date.isoformat()}_coach.md.rejected"
    if final_path.is_file():
        try:
            validate_coach_file(final_path)
        except (OSError, CoachReportError) as error:
            print(f"既存レポートの検証に失敗しました: {error}", file=sys.stderr)
            return 1
        return 0

    python = sys.executable
    scripts_dir = project_root / "scripts"
    previous_date = target_date - timedelta(days=1)
    fetch_command = [
        python,
        str(scripts_dir / "fetch_data.py"),
        "--days",
        str(days),
    ]
    fetch_code = _run_step(
        "fetch_data.py", fetch_command, runner, project_root
    )
    if fetch_code is None:
        return 1
    if fetch_code != 0:
        print(
            f"fetch_data.py が終了コード {fetch_code} で失敗しました",
            file=sys.stderr,
        )
        return 1

    weekly_report = find_latest_weekly_report(
        data_dir / "reports", target_date
    )
    context_command = [
        python,
        str(scripts_dir / "build_context.py"),
        "--days",
        str(days),
        "--end",
        previous_date.isoformat(),
        "--output",
        str(
            data_dir
            / "context"
            / f"{target_date.isoformat()}_coach_context.md"
        ),
    ]
    if weekly_report is not None:
        context_command.extend(["--previous", str(weekly_report)])
    context_code = _run_step(
        "build_context.py", context_command, runner, project_root
    )
    if context_code is None:
        return 1
    if context_code != 0:
        print(
            f"build_context.py が終了コード {context_code} で失敗しました",
            file=sys.stderr,
        )
        return 1

    context_path = (
        data_dir
        / "context"
        / f"{target_date.isoformat()}_coach_context.md"
    )
    previous_card = (
        coach_dir / f"{previous_date.isoformat()}_coach.md"
    )
    try:
        if previous_card.is_file():
            _append_previous_card(context_path, previous_card)
    except OSError as error:
        print(f"前日のカード追記に失敗しました: {error}", file=sys.stderr)
        return 1

    analyze_command = [
        python,
        str(scripts_dir / "analyze_bedrock.py"),
        "--model-id",
        model_id,
        "--context",
        str(context_path),
        "--end",
        previous_date.isoformat(),
        "--prompt",
        str(project_root / "prompts" / "coach_daily.md"),
        "--output",
        str(tmp_path),
        "--max-tokens",
        "1500",
        "--days",
        str(days),
    ]
    analyze_code = _run_step(
        "analyze_bedrock.py", analyze_command, runner, project_root
    )
    if analyze_code is None:
        return 1
    if analyze_code == 2:
        print("analyze_bedrock.py のAWS認証が失効しています", file=sys.stderr)
        return 3
    if analyze_code != 0:
        print(
            f"analyze_bedrock.py が終了コード {analyze_code} で失敗しました",
            file=sys.stderr,
        )
        return 1

    try:
        validate_coach_file(tmp_path)
    except (OSError, CoachReportError) as error:
        try:
            return _reject_output(tmp_path, rejected_path, str(error))
        except OSError as rename_error:
            print(f"不合格出力の退避に失敗しました: {rename_error}", file=sys.stderr)
            return 1

    try:
        os.replace(tmp_path, final_path)
    except OSError as error:
        print(f"完成レポートの配置に失敗しました: {error}", file=sys.stderr)
        return 1
    return 0


def run_daily(
    target_date: date,
    model_id: str,
    days: int = 7,
    data_dir: Path = DATA_DIR,
    project_root: Path = PROJECT_ROOT,
    runner: CommandRunner = _default_command_runner,
) -> int:
    """ロックを保持し、対象日のコーチカードを最大1回生成する。"""
    if days < 1:
        print("days は1以上である必要があります", file=sys.stderr)
        return 1
    coach_dir = data_dir / "reports" / "coach"
    try:
        coach_dir.mkdir(parents=True, exist_ok=True)
        lock_file = (coach_dir / ".lock").open("a+", encoding="utf-8")
    except OSError as error:
        print(f"ロックファイルを開けません: {error}", file=sys.stderr)
        return 1

    with lock_file:
        try:
            fcntl.flock(
                lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
            )
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                print("already_running", file=sys.stderr)
                return 4
            print(f"ロック取得に失敗しました: {error}", file=sys.stderr)
            return 1
        return _run_pipeline(
            target_date,
            model_id,
            days,
            data_dir,
            project_root,
            runner,
        )


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "YYYY-MM-DD形式で指定してください"
        ) from error


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("整数を指定してください") from error
    if number < 1:
        raise argparse.ArgumentTypeError("1以上を指定してください")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="日次コーチカードを生成します")
    parser.add_argument(
        "--date", required=True, type=_iso_date, help="生成日 (YYYY-MM-DD)"
    )
    parser.add_argument("--model-id", required=True, help="BedrockモデルID")
    parser.add_argument("--days", type=_positive_int, default=7, help="対象日数")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as error:
        return 0 if error.code == 0 else 1
    return run_daily(args.date, args.model_id, args.days)


if __name__ == "__main__":
    raise SystemExit(main())
