"""生成済みcontextをBedrock Converse APIで分析する。"""

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    CredentialRetrievalError,
    NoCredentialsError,
    PartialCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "health_analysis.md"
CONTEXT_FILENAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_context\.md$")

AUTH_ERROR_CODES = {
    "AccessDenied",
    "AccessDeniedException",
    "ExpiredToken",
    "ExpiredTokenException",
    "InvalidClientTokenId",
    "InvalidSignatureException",
    "UnrecognizedClientException",
}
AUTH_EXCEPTION_TYPES = (
    UnauthorizedSSOTokenError,
    TokenRetrievalError,
    SSOTokenLoadError,
    NoCredentialsError,
    CredentialRetrievalError,
    PartialCredentialsError,
)


class BedrockRuntimeClient(Protocol):
    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


def create_bedrock_client(region: str) -> BedrockRuntimeClient:
    """adaptive retryを設定したBedrock Runtimeクライアントを返す。"""
    import boto3
    from botocore.config import Config

    config = Config(retries={"max_attempts": 5, "mode": "adaptive"})
    return boto3.client("bedrock-runtime", region_name=region, config=config)


def invoke_converse(
    client: BedrockRuntimeClient,
    model_id: str,
    system_prompt: str,
    context: str,
) -> tuple[str, int, int]:
    """Converse APIを1回呼び、本文とトークン数を返す。"""
    response = client.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[
            {"role": "user", "content": [{"text": context}]},
        ],
        inferenceConfig={"maxTokens": 4000, "temperature": 0.3},
    )

    output = response.get("output")
    message = output.get("message") if isinstance(output, dict) else None
    content_blocks = (
        message.get("content") if isinstance(message, dict) else None
    )
    if not isinstance(content_blocks, list):
        raise TypeError("Bedrockレスポンスにcontentがありません")
    text_blocks = [
        block["text"]
        for block in content_blocks
        if isinstance(block, dict) and isinstance(block.get("text"), str)
    ]
    if not text_blocks:
        raise ValueError("Bedrockレスポンスにtextブロックがありません")

    usage = response.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    if not isinstance(input_tokens, int):
        input_tokens = 0
    if not isinstance(output_tokens, int):
        output_tokens = 0
    return "".join(text_blocks), input_tokens, output_tokens


def resolve_context_path(
    context_path: Path | None,
    end_date: date | None,
    data_dir: Path = DATA_DIR,
) -> Path:
    """明示パス、終了日、最新ファイルの順でcontextを解決する。"""
    if context_path is not None:
        resolved = context_path.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"contextファイルがありません: {context_path}")
        return resolved

    context_dir = data_dir / "context"
    if end_date is not None:
        resolved = context_dir / f"{end_date.isoformat()}_context.md"
        if not resolved.is_file():
            raise FileNotFoundError(f"contextファイルがありません: {resolved}")
        return resolved.resolve()

    candidates = sorted(
        path
        for path in context_dir.glob("*_context.md")
        if CONTEXT_FILENAME.match(path.name)
    )
    if not candidates:
        raise FileNotFoundError("contextファイルがありません。先にbuild_context.pyを実行してください")
    return candidates[-1].resolve()


def resolve_end_date(context_path: Path, explicit_end: date | None) -> date:
    """出力日を明示値またはcontextファイル名から決める。"""
    if explicit_end is not None:
        return explicit_end
    match = CONTEXT_FILENAME.match(context_path.name)
    if not match:
        raise ValueError(
            "contextファイル名から終了日を判定できません。--endを指定してください"
        )
    return date.fromisoformat(match.group(1))


def _context_label(context_path: Path) -> str:
    try:
        return str(context_path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(context_path)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_report(
    model_text: str,
    model_id: str,
    region: str,
    input_tokens: int,
    output_tokens: int,
    context_path: Path,
    end_date: date,
    data_dir: Path = DATA_DIR,
    generated_at: datetime | None = None,
) -> Path:
    """YAML frontmatterを付け、モデル本文を変更せず保存する。"""
    timestamp = generated_at or datetime.now().astimezone()
    frontmatter = "\n".join(
        [
            "---",
            f"model_id: {_yaml_string(model_id)}",
            f"region: {_yaml_string(region)}",
            f"input_tokens: {input_tokens}",
            f"output_tokens: {output_tokens}",
            f"context_file: {_yaml_string(_context_label(context_path))}",
            f"generated_at: {_yaml_string(timestamp.isoformat(timespec='seconds'))}",
            "---",
            "",
        ]
    )
    output_dir = data_dir / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{end_date.isoformat()}_analysis.md"
    output_path.write_text(f"{frontmatter}{model_text}", encoding="utf-8")
    return output_path


def analyze_context(
    model_id: str,
    region: str,
    context_path: Path,
    end_date: date,
    data_dir: Path = DATA_DIR,
    client: BedrockRuntimeClient | None = None,
) -> Path:
    """system/contextを読み、Converseを1回呼んでレポートを保存する。"""
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    context = context_path.read_text(encoding="utf-8")
    runtime_client = client or create_bedrock_client(region)
    model_text, input_tokens, output_tokens = invoke_converse(
        runtime_client, model_id, system_prompt, context
    )
    return write_report(
        model_text=model_text,
        model_id=model_id,
        region=region,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        context_path=context_path,
        end_date=end_date,
        data_dir=data_dir,
    )


def _client_error_code(error: ClientError) -> str | None:
    response = error.response
    if isinstance(response, dict):
        error_data = response.get("Error")
        if isinstance(error_data, dict) and isinstance(error_data.get("Code"), str):
            return error_data["Code"]
    return None


def is_auth_error(error: BaseException) -> bool:
    """AccessDenied・期限切れ・認証情報不在を識別する。"""
    if isinstance(error, AUTH_EXCEPTION_TYPES):
        return True
    if isinstance(error, ClientError):
        return _client_error_code(error) in AUTH_ERROR_CODES
    return False


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("YYYY-MM-DD形式で指定してください") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bedrock Converse APIで体調contextを分析します"
    )
    parser.add_argument(
        "--model-id",
        required=True,
        help="cross-region inference profile ID",
    )
    parser.add_argument("--region", default="us-east-1", help="AWSリージョン")
    parser.add_argument(
        "--context",
        type=Path,
        help="contextファイル。省略時は--endの日付または最新ファイル",
    )
    parser.add_argument("--end", type=_iso_date, help="出力日 (YYYY-MM-DD)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        context_path = resolve_context_path(args.context, args.end)
        end_date = resolve_end_date(context_path, args.end)
        output_path = analyze_context(
            model_id=args.model_id,
            region=args.region,
            context_path=context_path,
            end_date=end_date,
        )
    except (FileNotFoundError, TypeError, ValueError) as error:
        print(f"エラー: {error}", file=sys.stderr)
        return 1
    except ModuleNotFoundError:
        print(
            "エラー: boto3がありません。requirements.txtをインストールしてください",
            file=sys.stderr,
        )
        return 1
    except (BotoCoreError, ClientError) as error:
        if is_auth_error(error):
            print(
                "AWS認証エラー: aws login を実行してください",
                file=sys.stderr,
            )
            return 2
        print(
            f"エラー: Bedrock呼び出しに失敗しました ({error.__class__.__name__})",
            file=sys.stderr,
        )
        return 1
    except OSError as error:
        print(f"エラー: ファイル操作に失敗しました ({error})", file=sys.stderr)
        return 1

    print(f"生成: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
