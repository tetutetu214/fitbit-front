# todo.md

## 次の一手 <!-- next-move: 2026-08-23 -->
- サイクル 0 の実装（バックフィル改修・文脈束ね・Bedrock 分析スクリプト）を Codex に委譲中
- ⏳てつてつ: Fitbit 再認証（`python scripts/auth.py` → ブラウザ認可 → `python scripts/auth.py <code>`）

## サイクル 0（2026-08-23 着手）
- [x] 方向転換の整理と docs/plan.md 起草
- [ ] `scripts/fetch_data.py` を日付範囲エンドポイント対応に改修（60 日バックフィル）
- [ ] `scripts/build_context.py` 新規（Fitbit + Tanita + Vault worklog/reflections → Markdown）
- [ ] `scripts/analyze_bedrock.py` 新規（Converse API → `data/reports/`）
- [ ] テスト（pytest）
- [ ] てつてつ: Fitbit 再認証 → バックフィル実行
- [ ] てつてつ: `aws login` → モデル ID 確認 → 分析実行
- [ ] 出力の質を判定（純正コーチ比）→ サイクル 1 の go/no-go

## 保留（Won't リストは docs/plan.md §3）
- Issue #70 intraday 心拍（サイクル 0 の判定後に再検討）
- ダッシュボード UI 改善 Issue 群（約 20 件 OPEN）
