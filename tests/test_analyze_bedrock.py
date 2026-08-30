# 実APIは本人のOAuthトークンとAWS認証が必要で、サンドボックスから到達できない。
# そのため、該当するHTTPまたはboto3をモックする。

import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from botocore.exceptions import (
    ClientError,
    CredentialRetrievalError,
    NoCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

from scripts import analyze_bedrock


class FakeBedrockClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "content": [
                        {"text": "## 数値の事実\n"},
                        {"text": "モデル本文"},
                    ]
                }
            },
            "usage": {"inputTokens": 123, "outputTokens": 45},
        }


def test_client_uses_bedrock_runtime_and_adaptive_retries(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    class FakeConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    boto3_module = ModuleType("boto3")

    def fake_client(service_name: str, **kwargs: Any) -> object:
        calls.append((service_name, kwargs))
        return object()

    boto3_module.client = fake_client  # type: ignore[attr-defined]
    botocore_module = ModuleType("botocore")
    config_module = ModuleType("botocore.config")
    config_module.Config = FakeConfig  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", boto3_module)
    monkeypatch.setitem(sys.modules, "botocore", botocore_module)
    monkeypatch.setitem(sys.modules, "botocore.config", config_module)

    analyze_bedrock.create_bedrock_client("us-east-1")

    assert calls[0][0] == "bedrock-runtime"
    assert calls[0][1]["region_name"] == "us-east-1"
    assert calls[0][1]["config"].kwargs == {
        "retries": {"max_attempts": 5, "mode": "adaptive"}
    }


def test_converse_is_called_once_and_report_keeps_model_text(
    tmp_path, monkeypatch
) -> None:
    prompt_path = tmp_path / "health_analysis.md"
    prompt_path.write_text("system prompt", encoding="utf-8")
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text("context body", encoding="utf-8")
    data_dir = tmp_path / "data"
    client = FakeBedrockClient()
    monkeypatch.setattr(analyze_bedrock, "SYSTEM_PROMPT_PATH", prompt_path)

    output_path = analyze_bedrock.analyze_context(
        model_id="us.test-profile",
        region="us-east-1",
        context_path=context_path,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        client=client,
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["modelId"] == "us.test-profile"
    assert call["system"] == [{"text": "system prompt"}]
    assert call["messages"] == [
        {"role": "user", "content": [{"text": "context body"}]}
    ]
    assert call["inferenceConfig"] == {"maxTokens": 4000, "temperature": 0.3}
    report = output_path.read_text(encoding="utf-8")
    assert 'model_id: "us.test-profile"' in report
    assert 'region: "us-east-1"' in report
    assert "input_tokens: 123" in report
    assert "output_tokens: 45" in report
    assert report.endswith("## 数値の事実\nモデル本文")


def test_latest_context_is_selected_when_path_and_end_are_omitted(tmp_path) -> None:
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    older = context_dir / "2026-04-01_context.md"
    latest = context_dir / "2026-04-03_context.md"
    older.write_text("older", encoding="utf-8")
    latest.write_text("latest", encoding="utf-8")

    resolved = analyze_bedrock.resolve_context_path(None, None, tmp_path)

    assert resolved == latest.resolve()
    assert analyze_bedrock.resolve_end_date(resolved, None) == date(2026, 4, 3)


def assert_auth_error_returns_two(
    error: BaseException, tmp_path, monkeypatch, capsys
) -> None:
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text("context", encoding="utf-8")

    def raise_auth_error(**kwargs: Any) -> Path:
        raise error

    monkeypatch.setattr(analyze_bedrock, "analyze_context", raise_auth_error)

    exit_code = analyze_bedrock.main(
        [
            "--model-id",
            "us.test-profile",
            "--context",
            str(context_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "aws login を実行してください" in captured.err


def test_access_denied_client_error_returns_two(
    tmp_path, monkeypatch, capsys
) -> None:
    error = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "access denied",
            }
        },
        "Converse",
    )

    assert_auth_error_returns_two(error, tmp_path, monkeypatch, capsys)


def test_unauthorized_sso_token_error_returns_two(
    tmp_path, monkeypatch, capsys
) -> None:
    assert_auth_error_returns_two(
        UnauthorizedSSOTokenError(), tmp_path, monkeypatch, capsys
    )


def test_token_retrieval_error_returns_two(
    tmp_path, monkeypatch, capsys
) -> None:
    error = TokenRetrievalError(provider="sso", error_msg="expired")

    assert_auth_error_returns_two(error, tmp_path, monkeypatch, capsys)


def test_sso_token_load_error_returns_two(
    tmp_path, monkeypatch, capsys
) -> None:
    error = SSOTokenLoadError(error_msg="expired")

    assert_auth_error_returns_two(error, tmp_path, monkeypatch, capsys)


def test_no_credentials_error_returns_two(tmp_path, monkeypatch, capsys) -> None:
    assert_auth_error_returns_two(
        NoCredentialsError(), tmp_path, monkeypatch, capsys
    )


def test_credential_retrieval_error_returns_two(
    tmp_path, monkeypatch, capsys
) -> None:
    error = CredentialRetrievalError(provider="sso", error_msg="expired")

    assert_auth_error_returns_two(error, tmp_path, monkeypatch, capsys)


def test_optional_cli_arguments_keep_weekly_defaults(
    tmp_path, monkeypatch
) -> None:
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text("context", encoding="utf-8")
    captured: dict[str, object] = {}

    def capture_analyze_context(**kwargs: object) -> Path:
        captured.update(kwargs)
        return tmp_path / "2026-04-03_analysis.md"

    monkeypatch.setattr(
        analyze_bedrock, "analyze_context", capture_analyze_context
    )

    exit_code = analyze_bedrock.main(
        [
            "--model-id",
            "us.test-profile",
            "--context",
            str(context_path),
        ]
    )

    assert exit_code == 0
    assert captured["model_id"] == "us.test-profile"
    assert captured["prompt_path"] is None
    assert captured["output_path"] is None
    assert captured["max_tokens"] == 4000
    assert captured["days"] is None


def test_weekly_defaults_write_to_the_dated_analysis_path(
    tmp_path, monkeypatch
) -> None:
    prompt_path = tmp_path / "health_analysis.md"
    prompt_path.write_text("system prompt", encoding="utf-8")
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text("context body", encoding="utf-8")
    data_dir = tmp_path / "data"
    monkeypatch.setattr(analyze_bedrock, "SYSTEM_PROMPT_PATH", prompt_path)

    output_path = analyze_bedrock.analyze_context(
        model_id="us.test-profile",
        region="us-east-1",
        context_path=context_path,
        end_date=date(2026, 4, 3),
        data_dir=data_dir,
        client=FakeBedrockClient(),
    )

    assert output_path == data_dir / "reports" / "2026-04-03_analysis.md"


def test_custom_prompt_output_and_token_limit_are_used(
    tmp_path,
) -> None:
    prompt_path = tmp_path / "coach_daily.md"
    prompt_path.write_text("daily system prompt", encoding="utf-8")
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text(
        "# context\n\n- 期間: 2026-03-28〜2026-04-03 (7日)\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "coach" / ".2026-04-04_coach.md.tmp"
    client = FakeBedrockClient()

    result = analyze_bedrock.analyze_context(
        model_id="us.daily-profile",
        region="us-east-1",
        context_path=context_path,
        end_date=date(2026, 4, 3),
        data_dir=tmp_path / "data",
        client=client,
        prompt_path=prompt_path,
        output_path=output_path,
        max_tokens=1500,
    )

    assert result == output_path
    assert client.calls[0]["system"] == [{"text": "daily system prompt"}]
    assert client.calls[0]["inferenceConfig"] == {
        "maxTokens": 1500,
        "temperature": 0.3,
    }
    report = output_path.read_text(encoding="utf-8")
    assert 'end: "2026-04-03"' in report
    assert "days: 7" in report
    assert f'prompt: "{prompt_path}"' in report


def test_explicit_days_override_the_context_period(tmp_path) -> None:
    prompt_path = tmp_path / "coach_daily.md"
    prompt_path.write_text("daily system prompt", encoding="utf-8")
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text(
        "# context\n\n- 期間: 2026-02-04〜2026-04-03 (60日)\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "coach.md"

    analyze_bedrock.analyze_context(
        model_id="us.daily-profile",
        region="us-east-1",
        context_path=context_path,
        end_date=date(2026, 4, 3),
        client=FakeBedrockClient(),
        prompt_path=prompt_path,
        output_path=output_path,
        days=7,
    )

    report = output_path.read_text(encoding="utf-8")
    assert "days: 7" in report
    assert "days: 60" not in report


def test_max_tokens_stop_reason_rejects_truncated_output() -> None:
    class MaxTokensClient(FakeBedrockClient):
        def converse(self, **kwargs: Any) -> dict[str, Any]:
            response = super().converse(**kwargs)
            response["stopReason"] = "max_tokens"
            return response

    with pytest.raises(ValueError, match="maxTokens 上限で切れた"):
        analyze_bedrock.invoke_converse(
            MaxTokensClient(),
            "us.daily-profile",
            "system prompt",
            "context body",
            1500,
        )


def test_max_tokens_error_is_written_to_stderr(
    tmp_path, monkeypatch, capsys
) -> None:
    context_path = tmp_path / "2026-04-03_context.md"
    context_path.write_text("context body", encoding="utf-8")

    def raise_max_tokens(**kwargs: object) -> Path:
        raise ValueError("maxTokens 上限で切れた")

    monkeypatch.setattr(
        analyze_bedrock, "analyze_context", raise_max_tokens
    )

    exit_code = analyze_bedrock.main(
        [
            "--model-id",
            "us.daily-profile",
            "--context",
            str(context_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "maxTokens 上限で切れた" in captured.err
