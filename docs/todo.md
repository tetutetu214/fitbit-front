# todo.md

## 次の一手 <!-- next-move: 2026-08-30 -->
- PR #72（コーチカード）マージ済み（08-30、merge commit afdf526、ブランチ削除済み）。サイクル 1 完了
- 週次解析（日曜朝、aws login → fetch → build_context → analyze）＋ Cost Explorer で 08-23 の Opus 4.5 分にクレジットが当たっているか確認（RECORD_TYPE=Credit/Usage）。当たっていれば COACH_MODEL_ID を Opus 4.5 に切替。08-30 は未実施（コーチカードの実物確認を優先）
- マージ後のサイクル 2 は product-sparring から: 「既存ダッシュボードの見にくさ・心拍/HRV」を plan.md Won't のまま置くか、カード側に寄せるかを決めてから着手
- reviewer の non-blocking 指摘 4 件（見出しの正規表現化・ValueError 前の警告順序・auth 断片入力・+デコード）は次の実装ついでに拾う

## サイクル 1 コーチカード（2026-08-24 設計、spec.md v2.1）
- [x] arch-sparring で実行経路を決定（ADR-001: Vite ミドルウェア）
- [x] docs/spec.md 起草 → Codex 敵対的検証で v2 → reviewer 指摘で v2.1
- [x] 実装一式（Codex 2 ラウンド。pytest 86 / ruff 0 / Vitest 28 / tsc 0 / ESLint 0）
- [x] reviewer 2 巡（1 巡目 11 件修正 → 2 巡目 pass）、理解度テスト 3/3 正解
- [x] 実物 1 件（08-30）: running → ready、検算（一致 14 / 不一致 3 は集計・選択の判断誤り）、実測 $0.070/回を knowledge.md と spec §6 に記録
- [ ] PR 作成（判定 JSON 配置 → gh pr create）
- [ ] サイクル 2 候補（本人フィードバック 08-30）: 既存ダッシュボードが「数値だらけで見にくい」「心拍・HRV を見たい」→ plan.md §3 Won't「ダッシュボード改修」の再検討が必要。product-sparring で「カードに寄せるか・ダッシュボードを直すか」を判断してから着手
- [ ] サイクル 2 候補（品質）: 答え合わせの件数はプロンプトで「該当日を列挙 → 件数」の順序に固定 / worklog の最終エントリ時刻は build_context で機械抽出して渡す
- [ ] reviewer non-blocking 3 件は次の実装ついでに拾う: パリティテストを差分 7 ケースへ拡張（days float / generated_at のタイムゾーン 4 形態）/ spawn に cwd 明示 / いずれも現行パイプライン非到達

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
