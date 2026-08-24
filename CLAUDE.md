# 20260405_fitbit — Fitbit 体調分析

## 概要
Fitbit Web API（日次サマリ）と Tanita Health Planet の体データを取得し、Vault の行動文脈（worklog / reflections）と合わせて Bedrock の Claude に分析させる本人専用ツール。2026-08-23 に「ダッシュボード画面」から「LLM 体調分析」へ方向転換（経緯は docs/plan.md）。

## 技術スタック
- Python 3.12（`scripts/`）: requests / python-dotenv / boto3
- フロント（据え置き・改修しない）: React + Vite + Recharts + Tailwind v4
- AWS: Bedrock Converse API（cross-region inference profile）。認証は `aws login` 都度方式、長期キーなし
- データ: `data/daily/*.json`（Fitbit 生レスポンス）/ `data/daily_tanita/*.json` / `data/reports/*.md`。`/data/` は Git 管理外

## 実行
- 認証: `python scripts/auth.py` → ブラウザ認可 → `python scripts/auth.py <code>`（URL 手貼り方式）
- 取得: `python scripts/fetch_data.py --days 60`
- 文脈生成: `python scripts/build_context.py --days 60`
- 分析: `aws login` 後に `python scripts/analyze_bedrock.py --model-id <inference-profile-id>`
- テスト・静的解析 (`requirements-dev.txt`): `python -m pytest tests/ -q` / `ruff check scripts/fetch_data.py scripts/build_context.py scripts/analyze_bedrock.py tests`

## 秘密情報
- `.env`（FITBIT_CLIENT_ID / FITBIT_CLIENT_SECRET / TANITA_*）と `data/tokens.json` の中身を画面に出さない
- Vault のパス: `/mnt/c/Users/lemon/Vault`（worklog/ と wiki/reflections/ を読み取り専用で参照）

## docs/
- plan.md（方向転換・スコープ・Won't）/ todo.md / knowledge.md
