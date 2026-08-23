# todo.md

## 次の一手 <!-- next-move: 2026-08-23 -->
- ⏳てつてつ: Fitbit 再認証（`.venv/bin/python scripts/auth.py` → ブラウザ認可 → `.venv/bin/python scripts/auth.py <code>`）→ `.venv/bin/python scripts/fetch_data.py --days 60`
- ⏳てつてつ: `aws login` → Claude がモデル ID 確認 → `build_context.py` → `analyze_bedrock.py` を実行し、出力の質を Google Health Coach と比較して判定
- 判定後: PR 作成（feature/bedrock-analysis、5138f84 まで push 済み）→ サイクル 1 の go/no-go

## サイクル 0（2026-08-23 着手）
- [x] 方向転換の整理と docs/plan.md 起草
- [x] `scripts/fetch_data.py` を日付範囲エンドポイント対応に改修（60 日バックフィル）
- [x] `scripts/build_context.py` 新規（Fitbit + Tanita + Vault worklog/reflections → Markdown）
- [x] `scripts/analyze_bedrock.py` 新規（Converse API → `data/reports/`）
- [x] テスト（pytest 30 件、ruff 0 件、reviewer 指摘 10 件修正済み）
- [ ] てつてつ: Fitbit 再認証 → バックフィル実行
- [ ] てつてつ: `aws login` → モデル ID 確認 → 分析実行
- [ ] 出力の質を判定（純正コーチ比）→ サイクル 1 の go/no-go

## 保留（Won't リストは docs/plan.md §3）
- Issue #70 intraday 心拍（サイクル 0 の判定後に再検討）
- ダッシュボード UI 改善 Issue 群（約 20 件 OPEN）
