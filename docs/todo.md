# todo.md

## 次の一手 <!-- next-move: 2026-08-23 -->
- ⏳てつてつ: `data/reports/2026-08-22_analysis.md`（Opus 4.5 の初回分析）を読んで Google Health Coach と比較し、サイクル 1 の go/no-go を判定
- 判定が go なら: プロンプト改善（計算ミス対策・平均睡眠 5h45m を見出しに）→ 理解度テスト → PR 作成（feature/bedrock-analysis、75d1a22 まで push 済み）→ arch-sparring（自動化と認証方式）

## サイクル 0（2026-08-23 着手）
- [x] 方向転換の整理と docs/plan.md 起草
- [x] `scripts/fetch_data.py` を日付範囲エンドポイント対応に改修（60 日バックフィル）
- [x] `scripts/build_context.py` 新規（Fitbit + Tanita + Vault worklog/reflections → Markdown）
- [x] `scripts/analyze_bedrock.py` 新規（Converse API → `data/reports/`）
- [x] テスト（pytest 30 件、ruff 0 件、reviewer 指摘 10 件修正済み）
- [x] Fitbit 再認証 → 60 日バックフィル（API 12 回、エラー 0）
- [x] Bedrock 分析実行（Opus 4.5。Claude 5 系はアカウント未提供）
- [ ] 出力の質を判定（純正コーチ比）→ サイクル 1 の go/no-go

## 保留（Won't リストは docs/plan.md §3）
- Issue #70 intraday 心拍（サイクル 0 の判定後に再検討）
- ダッシュボード UI 改善 Issue 群（約 20 件 OPEN）
