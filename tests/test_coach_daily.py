# 実 Fitbit API と Bedrock は認証・課金・待ち時間を伴うため、子コマンドをモックする。

import fcntl
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import pytest

from scripts import coach_daily

TARGET_DATE = date(2026, 8, 24)
VALID_REPORT = """---
model_id: "us.test-model"
generated_at: "2026-08-24T06:00:00+09:00"
end: "2026-08-23"
days: 7
prompt: "prompts/coach_daily.md"
---

## 今日の一手
23時30分に就寝する。

## 昨日の答え合わせ
睡眠時間で確認した。

## 根拠データ
- 2026-08-23: 睡眠 360 分

## 注意
個人差がある。
"""


class FakePipelineRunner:
    def __init__(
        self,
        data_dir: Path,
        report: str = VALID_REPORT,
        stage_codes: Mapping[str, int] | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.report = report
        self.stage_codes = dict(stage_codes or {})
        self.commands: list[list[str]] = []
        self.context_at_analyze: str | None = None

    def __call__(self, command: Sequence[str], _cwd: Path) -> int:
        copied_command = list(command)
        self.commands.append(copied_command)
        stage = Path(copied_command[1]).name
        exit_code = self.stage_codes.get(stage, 0)
        if stage == "build_context.py" and exit_code == 0:
            output_index = copied_command.index("--output") + 1
            context_path = Path(copied_command[output_index])
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text("# context\n", encoding="utf-8")
        if stage == "analyze_bedrock.py" and exit_code == 0:
            context_index = copied_command.index("--context") + 1
            context_path = Path(copied_command[context_index])
            self.context_at_analyze = context_path.read_text(encoding="utf-8")
            output_index = copied_command.index("--output") + 1
            output_path = Path(copied_command[output_index])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(self.report, encoding="utf-8")
        return exit_code


def test_analyze_auth_expiry_is_normalized_to_three(tmp_path) -> None:
    data_dir = tmp_path / "data"
    runner = FakePipelineRunner(
        data_dir,
        stage_codes={"analyze_bedrock.py": 2},
    )

    exit_code = coach_daily.run_daily(
        TARGET_DATE,
        "us.test-model",
        data_dir=data_dir,
        project_root=tmp_path,
        runner=runner,
    )

    assert exit_code == 3


def test_argparse_error_is_normalized_to_one(capsys) -> None:
    exit_code = coach_daily.main(
        ["--date", "not-a-date", "--model-id", "us.test-model"]
    )

    capsys.readouterr()
    assert exit_code == 1


def test_lock_contention_returns_four_without_starting_children(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    coach_dir = data_dir / "reports" / "coach"
    coach_dir.mkdir(parents=True)
    lock_path = coach_dir / ".lock"
    runner = FakePipelineRunner(data_dir)

    with lock_path.open("a+", encoding="utf-8") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        exit_code = coach_daily.run_daily(
            TARGET_DATE,
            "us.test-model",
            data_dir=data_dir,
            project_root=tmp_path,
            runner=runner,
        )

    assert exit_code == 4
    assert runner.commands == []


def test_invalid_output_is_moved_to_rejected_without_final_report(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    runner = FakePipelineRunner(
        data_dir,
        report="---\nmodel_id: test\n---\n\n## 今日の一手\n実行する。\n",
    )

    exit_code = coach_daily.run_daily(
        TARGET_DATE,
        "us.test-model",
        data_dir=data_dir,
        project_root=tmp_path,
        runner=runner,
    )

    coach_dir = data_dir / "reports" / "coach"
    assert exit_code == 1
    assert (coach_dir / ".2026-08-24_coach.md.rejected").is_file()
    assert not (coach_dir / "2026-08-24_coach.md").exists()


def test_daily_pipeline_uses_a_dedicated_context_output(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    runner = FakePipelineRunner(data_dir)

    exit_code = coach_daily.run_daily(
        TARGET_DATE,
        "us.test-model",
        data_dir=data_dir,
        project_root=tmp_path,
        runner=runner,
    )

    context_command = next(
        command
        for command in runner.commands
        if Path(command[1]).name == "build_context.py"
    )
    output_index = context_command.index("--output") + 1
    coach_context = data_dir / "context" / "2026-08-24_coach_context.md"
    weekly_default = data_dir / "context" / "2026-08-23_context.md"
    assert exit_code == 0
    assert Path(context_command[output_index]) == coach_context
    assert str(weekly_default) not in context_command

    analyze_command = next(
        command
        for command in runner.commands
        if Path(command[1]).name == "analyze_bedrock.py"
    )
    context_index = analyze_command.index("--context") + 1
    days_index = analyze_command.index("--days") + 1
    assert Path(analyze_command[context_index]) == coach_context
    assert analyze_command[days_index] == "7"


def test_previous_card_is_appended_to_the_end_of_context(tmp_path) -> None:
    data_dir = tmp_path / "data"
    coach_dir = data_dir / "reports" / "coach"
    coach_dir.mkdir(parents=True)
    previous_card = coach_dir / "2026-08-23_coach.md"
    previous_card.write_text(VALID_REPORT, encoding="utf-8")
    runner = FakePipelineRunner(data_dir)

    exit_code = coach_daily.run_daily(
        TARGET_DATE,
        "us.test-model",
        data_dir=data_dir,
        project_root=tmp_path,
        runner=runner,
    )

    assert exit_code == 0
    assert runner.context_at_analyze is not None
    assert runner.context_at_analyze.endswith(
        f"## 前日のコーチカード\n\n{VALID_REPORT.rstrip()}\n"
    )


def test_previous_option_is_omitted_when_weekly_report_does_not_exist(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    runner = FakePipelineRunner(data_dir)

    exit_code = coach_daily.run_daily(
        TARGET_DATE,
        "us.test-model",
        data_dir=data_dir,
        project_root=tmp_path,
        runner=runner,
    )

    context_command = next(
        command
        for command in runner.commands
        if Path(command[1]).name == "build_context.py"
    )
    assert exit_code == 0
    assert "--previous" not in context_command


def test_latest_weekly_report_not_after_target_date_is_passed_to_context(
    tmp_path,
) -> None:
    data_dir = tmp_path / "data"
    reports_dir = data_dir / "reports"
    reports_dir.mkdir(parents=True)
    older = reports_dir / "2026-08-20_analysis.md"
    latest = reports_dir / "2026-08-24_analysis.md"
    future = reports_dir / "2026-08-25_analysis.md"
    for report in (older, latest, future):
        report.write_text("weekly", encoding="utf-8")
    runner = FakePipelineRunner(data_dir)

    exit_code = coach_daily.run_daily(
        TARGET_DATE,
        "us.test-model",
        data_dir=data_dir,
        project_root=tmp_path,
        runner=runner,
    )

    context_command = next(
        command
        for command in runner.commands
        if Path(command[1]).name == "build_context.py"
    )
    previous_index = context_command.index("--previous") + 1
    assert exit_code == 0
    assert Path(context_command[previous_index]) == latest


def test_duplicate_heading_is_rejected() -> None:
    duplicate = VALID_REPORT.replace(
        "## 昨日の答え合わせ",
        "## 今日の一手\n追加\n\n## 昨日の答え合わせ",
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(duplicate)


def test_heading_in_wrong_order_is_rejected() -> None:
    wrong_order = VALID_REPORT.replace(
        "## 今日の一手", "## 一時見出し"
    ).replace("## 昨日の答え合わせ", "## 今日の一手").replace(
        "## 一時見出し", "## 昨日の答え合わせ"
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(wrong_order)


def test_empty_section_is_rejected() -> None:
    empty = VALID_REPORT.replace(
        "## 今日の一手\n23時30分に就寝する。\n\n## 昨日の答え合わせ",
        "## 今日の一手\n\n## 昨日の答え合わせ",
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(empty)


def test_body_over_2400_characters_is_rejected() -> None:
    oversized = VALID_REPORT.replace(
        "23時30分に就寝する。", "あ" * 2_400
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(oversized)


def test_extra_h2_heading_is_rejected() -> None:
    extra = VALID_REPORT.replace(
        "## 注意", "## 追加\n説明。\n\n## 注意"
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(extra)


def test_malformed_frontmatter_is_rejected() -> None:
    malformed = VALID_REPORT.replace(
        'model_id: "us.test-model"', 'model_id: "unterminated'
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(malformed)


def test_duplicate_frontmatter_key_is_rejected() -> None:
    duplicate = VALID_REPORT.replace(
        'model_id: "us.test-model"',
        'model_id: "us.test-model"\nmodel_id: "other"',
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(duplicate)


def test_api_metadata_without_timezone_is_rejected() -> None:
    invalid = VALID_REPORT.replace(
        'generated_at: "2026-08-24T06:00:00+09:00"',
        'generated_at: "2026-08-24T06:00:00"',
    )

    with pytest.raises(coach_daily.CoachReportError):
        coach_daily.parse_coach_report(invalid)


def _parity_report(case_name: str) -> str:
    if case_name == "normal":
        return VALID_REPORT
    if case_name == "u2028_heading_separator":
        return VALID_REPORT.replace(
            "## 今日の一手\n", "## 今日の一手\u2028"
        )
    if case_name == "leading_whitespace_key":
        return VALID_REPORT.replace("model_id:", "  model_id :")
    if case_name == "colon_in_plain_value":
        return VALID_REPORT.replace(
            'prompt: "prompts/coach_daily.md"',
            "prompt: prompts/coach:daily.md",
        )
    if case_name == "japanese_plain_value":
        return VALID_REPORT.replace("---\n\n##", "memo: 日本語の値\n---\n\n##")
    if case_name == "crlf":
        return VALID_REPORT.replace("\n", "\r\n")
    if case_name == "duplicate_trimmed_key":
        return VALID_REPORT.replace(
            'model_id: "us.test-model"',
            'model_id: "us.test-model"\n model_id : "other"',
        )
    if case_name == "blank_trimmed_value":
        return VALID_REPORT.replace(
            'prompt: "prompts/coach_daily.md"', "prompt:   "
        )
    if case_name == "surrounding_value_whitespace":
        return VALID_REPORT.replace("days: 7", "days:   7   ")
    raise AssertionError(f"未知のパリティケースです: {case_name}")


@pytest.mark.parametrize(
    ("case_name", "is_valid"),
    [
        ("normal", True),
        ("u2028_heading_separator", False),
        ("leading_whitespace_key", True),
        ("colon_in_plain_value", True),
        ("japanese_plain_value", True),
        ("crlf", False),
        ("duplicate_trimmed_key", False),
        ("blank_trimmed_value", False),
        ("surrounding_value_whitespace", True),
    ],
)
def test_report_parser_follows_the_shared_lf_and_strip_rules(
    case_name: str, is_valid: bool
) -> None:
    content = _parity_report(case_name)

    if is_valid:
        report = coach_daily.parse_coach_report(content)
        assert len(report.sections) == 4
    else:
        with pytest.raises(coach_daily.CoachReportError):
            coach_daily.parse_coach_report(content)
