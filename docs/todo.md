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
- [ ] サイクル 2 候補（本人フィードバック 08-30、初回カードを見て）。plan.md §3 Won't「ダッシュボード改修」は本人の要望で再開の対象。product-sparring で優先順位を決めてから着手
  - 日次カード: 実行がダッシュボードを開いた時だけで「毎日・朝に届く」になっていない → PC 起動時の自動実行＋LINE 通知の要否（aws login 都度方式との両立が設計論点）
  - 日次カード: 初回は前日カードが無く週次指示に対して 7 日分を比較したため週報に見えた。日次は「昨日 1 日の答え合わせ 3 行／今日の一手 3 行」に絞り、根拠データは画面に出さない（モデルには読ませる）
  - トレーナー設定: context には安静時心拍・HRV・睡眠ステージ・SpO2・歩数・活動時間が載っているのに睡眠しか語らない → プロンプトで全指標を使わせる。「歩数と睡眠」「サウナと睡眠ステージ」のような指標間・イベントの関係は 60 日の週次で扱い、サウナ等の行動イベントは 1 行入力の口を作る（Fitbit では検出不能）
  - ダッシュボード: 全チャートが読み込んだ全日分を描き期間切替が無い → 日が増えるほど密になり数字が読めない。期間切替（7/30/60 日）が先決。intraday 心拍（Issue #70、分単位）は日単位表示で要望あり。HRV・SpO2 は数値だけでなく「何が分かるか」の意味づけ（基準帯・前週比）が要る
  - 未取得の Fitbit 指標: 距離・呼吸数・皮膚温・intraday（取得は日次サマリのみ）
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
