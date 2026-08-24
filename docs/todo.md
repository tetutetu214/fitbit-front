# todo.md

## 次の一手 <!-- next-move: 2026-08-24 -->
- ⏳てつてつ: docs/spec.md（コーチカード）の確認。OK なら Codex 委譲で実装開始（ブランチ feature/coach-card）
- 08-31 日曜朝: 週次解析（aws login → fetch → build_context → analyze）＋ Cost Explorer で 08-23 の Opus 4.5 分にクレジットが当たっているか確認（RECORD_TYPE=Credit/Usage）。当たっていれば日次モデルを Opus 4.5 に切替
- reviewer の non-blocking 指摘 4 件（見出しの正規表現化・ValueError 前の警告順序・auth 断片入力・+デコード）は次の実装ついでに拾う

## サイクル 1 コーチカード（2026-08-24 設計、spec.md）
- [x] arch-sparring で実行経路を決定（ADR-001: Vite ミドルウェア）
- [x] docs/spec.md 起草
- [ ] `scripts/coach_daily.py` / `analyze_bedrock.py --prompt --output` / `prompts/coach_daily.md`
- [ ] `vite/coach-plugin.ts` + Vitest 5 件
- [ ] `src/components/CoachCard.tsx` + `App.tsx` 1 行
- [ ] 実物 1 件で loading → ready を目視、数値検算、初回コストを knowledge.md に記録
- [ ] PR 作成（理解度テスト → reviewer）

## サイクル 0（2026-08-23 着手）
- [x] 方向転換の整理と docs/plan.md 起草
- [x] `scripts/fetch_data.py` を日付範囲エンドポイント対応に改修（60 日バックフィル）
- [x] `scripts/build_context.py` 新規（Fitbit + Tanita + Vault worklog/reflections → Markdown）
- [x] `scripts/analyze_bedrock.py` 新規（Converse API → `data/reports/`）
- [x] テスト（pytest 30 件、ruff 0 件、reviewer 指摘 10 件修正済み）
- [x] Fitbit 再認証 → 60 日バックフィル（API 12 回、エラー 0）
- [x] Bedrock 分析実行（Opus 4.5。Claude 5 系はアカウント未提供）
- [x] 出力の質を判定 → go（トレーナー役 + プロフィール同梱で再実行済み、出典 URL 実在確認済み）

## 保留（Won't リストは docs/plan.md §3）
- Issue #70 intraday 心拍（サイクル 0 の判定後に再検討）
- ダッシュボード UI 改善 Issue 群（約 20 件 OPEN）
