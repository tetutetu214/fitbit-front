# Fitbit連携 個人向け生体BIツール

Fitbit Web APIの豊富なヘルスデータをAWSサーバレス基盤で収集・蓄積し、Cloudflare Pagesでダッシュボードを配信する構成で、**月額~$0.40〜$0.60**の運用が実現可能である（既存AWSアカウント前提、12ヶ月限定無料枠は含まない）。50ユーザー規模までスケールしても$5/月の予算を大幅に下回る。本レポートでは競合分析・API仕様・アーキテクチャ設計・セキュリティ・ロードマップを網羅的に設計する。

---

## 1. 競合サービスが提供する機能と、差別化の着眼点

### 主要9サービスの機能マッピング

有料ヘルスBIツール市場は「スコアリング型」と「分析プラットフォーム型」の2軸に分かれる。WHOOPとOura Ringは**Recovery/Readiness/Strainの3スコア体系**でユーザーの状態を直感的に色分け表示（緑/黄/赤）し、月額$6〜$40で提供している。一方、GyroscopeとExist.ioは**クロスドメイン統合ダッシュボード**として、ヘルスデータに加え生産性（RescueTime）、気分、天気、音楽などの非健康データも統合して相関分析を行う。

各サービスの特徴的な機能を整理すると：

- **WHOOP**（$199〜$359/年）：Recovery Score（0-100%）、Strain Score（0-21 Borg scale）、Journal Trendsによるライフスタイル行動と回復の相関分析、AIコーチ
- **Oura Ring**（$5.99/月）：Readiness Score、HRV全夜グラフ、体温偏差による体調変化検知、月経周期対応のスコア補正
- **Exist.io**（$6.99/月）：**自動統計相関エンジン**が最大の差別化要素。全データソース間の相関関係を自動発見し、信頼度5段階で表示
- **Gyroscope**（$29/月）：「人体のOS」を標榜する最も包括的な統合ダッシュボード、Food XRAY（AI写真食事記録）、美しいデータビジュアライゼーション
- **Cronometer**（$4.99/月）：**84種類の栄養素**を追跡可能な最も詳細な栄養分析ツール。USDA/NCCDB検証済みデータベース
- **Welltory**：**21種のHRV指標**（RMSSD、SDNN、周波数ドメイン解析）を提供する最も粒度の高いHRV分析

### 個人BIツールで優先実装すべき機能

Fitbitユーザーが現在利用できないプレミアム分析機能の中で、最も価値が高いのは以下の3つである：

1. **自動相関分析**（Exist.ioモデル）：睡眠品質→活動パフォーマンス→HRV→体重の相関を統計的に可視化。Fitbitユーザーにとって最大のギャップ
2. **コンポジットスコア**（WHOOP/Ouraモデル）：HRV・RHR・睡眠データからRecovery Scoreを算出し、一目で体調を把握
3. **長期トレンド分析**（週次/月次/6ヶ月）：トレーニング適応度の可視化、季節変動の把握

---

## 2. Fitbit Web APIで取得可能なデータ全体像

### 14カテゴリ・数十エンドポイントの全容

Fitbit Web APIは`https://api.fitbit.com`をベースURLとし、OAuth 2.0認証（PKCE推奨）で**150リクエスト/時間/ユーザー**のレート制限下で動作する。「Personal」アプリタイプであれば開発者自身のIntraday（日中詳細）データに自動アクセス可能である。

| データカテゴリ | 主要エンドポイント | Intraday粒度 | OAuthスコープ |
|---|---|---|---|
| **心拍数** | `/1/user/-/activities/heart/date/{date}/{period}.json` | 1秒/1分/5分/15分 | `heartrate` |
| **HRV** | `/1/user/-/hrv/date/{date}.json` | 5分間隔（睡眠中） | `heartrate` |
| **睡眠** | `/1.2/user/-/sleep/date/{date}.json` | 30秒（ステージ）/ 60秒 | `sleep` |
| **活動量** | `/1/user/-/activities/{resource}/date/{date}/{period}.json` | 1分/5分/15分 | `activity` |
| **SpO2** | `/1/user/-/spo2/date/{date}.json` | 5分移動平均 | `oxygen_saturation` |
| **呼吸数** | `/1/user/-/br/date/{date}.json` | 睡眠ステージ別 | `respiratory_rate` |
| **体温** | `/1/user/-/temp/skin/date/{date}.json` | 日次のみ | `temperature` |
| **体重/BMI** | `/1/user/-/body/{resource}/date/{date}/{period}.json` | 日次のみ | `weight` |
| **栄養** | `/1/user/-/foods/log/date/{date}.json` | 日次のみ | `nutrition` |
| **ECG** | `/1/user/-/ecg/list.json` | 250Hz波形（30秒） | `electrocardiogram` |
| **VO2 Max** | `/1/user/-/cardioscore/date/{date}.json` | 日次 | `cardio_fitness` |
| **AZM** | `/1/user/-/activities/active-zone-minutes/date/{date}/{period}.json` | 1分/5分/15分 | `activity` |
| **デバイス** | `/1/user/-/devices.json` | — | `settings` |
| **プロフィール** | `/1/user/-/profile.json` | — | `profile` |

### BIツール設計上の重要制約

**Access Tokenの有効期限は8時間**（28,800秒）で、Refresh Tokenは使い切り型（使用するたびに新しいRefresh Tokenが発行される）。API deprecation予定が**2026年9月**に設定されており、Google Health APIへの移行が必要になる点は設計時に考慮すべきである。Webhook（Subscriptions API）を使えばデバイス同期時にプッシュ通知を受け取れるが、定期バッチ方式の方がアーキテクチャがシンプルになる。

---

## 3. AWSアーキテクチャ：月額$0で動く構成

### 全体アーキテクチャ図

```
ユーザー → Cloudflare Pages (無料) → React SPA
                    ↓ API呼び出し
           API Gateway (HTTP API)
                    ↓ JWT検証
           Cognito Authorizer (Lite)
                    ↓
           Lambda (ARM/Graviton2, 256MB)
              ├── DynamoDB (Provisioned 25/25)
              ├── SSM Parameter Store (SecureString)
              └── Secrets Manager (アプリ認証情報のみ)

EventBridge Scheduler (6時間ごと)
              ↓
           Lambda (データ取得バッチ)
              ├── SSM → Fitbitトークン取得
              ├── Fitbit API → ヘルスデータ取得
              └── DynamoDB → データ保存
```

### サービス別の無料枠と月額コスト

各AWSサービスの「Always Free」（永続無料枠）を最大活用した構成を設計した。**太字**の項目は永続無料枠を持つサービスである。※12ヶ月限定の無料枠は既存AWSアカウントでは適用されないため、従量課金で試算している。

| サービス | 無料枠 | 1ユーザー推定使用量 | 月額コスト |
|---|---|---|---|
| **Lambda** | 100万リクエスト + 40万GB秒/月（永続） | ~3,900回 + 487GB秒 | **$0.00** |
| **DynamoDB** | On-Demandモード（$1.25/100万WRU, $0.25/100万RRU） | ~600W + ~3,000R/月 | **~$0.003** |
| **CloudFront** | 1TB転送 + 1,000万リクエスト（永続） | ~100MB | **$0.00** |
| **EventBridge** | 1,400万スケジューラ呼び出し（永続） | ~30回 | **$0.00** |
| **Cognito** | 10,000MAU Liteティア（永続） | 1MAU | **$0.00** |
| **SSM Parameter Store** | Standard無制限（永続） | 1パラメータ | **$0.00** |
| Secrets Manager | なし | 1シークレット | **$0.40** |
| API Gateway (HTTP) | なし（$1.00/100万リクエスト） | ~3,000回 | **~$0.003** |
| S3 | なし（$0.023/GB/月） | ~50MB | **~$0.001** |

**シングルユーザー合計：~$0.40/月**（大半はSecrets Manager。アプリ認証情報をParameter Storeに移せば~$0.004も可能）

### スケール時のコスト推移

| シナリオ | Lambda | DynamoDB | API GW | S3 | Secrets Manager | 合計 |
|---|---|---|---|---|---|---|
| 1ユーザー | $0.00 | $0.00 | ~$0.003 | ~$0.001 | $0.40 | **~$0.40** |
| 10ユーザー | $0.00 | $0.00 | ~$0.03 | ~$0.01 | $0.40 | **~$0.44** |
| 50ユーザー | $0.00 | $0.00 | ~$0.15 | ~$0.05 | $0.40 | **~$0.60** |

50ユーザーでも$5/月予算の**12%未満**で運用可能。

### コスト最適化の8つの設計判断

1. **HTTP API**を使用（REST APIより71%安価、JWTオーソライザー対応）
2. **SSM Parameter Store**でトークン保存（Secrets Managerは$0.40/secret/月）
3. **DynamoDB On-Demand**モード（Provisioned永続無料枠はアカウント全テーブルで共有のため、既存アカウントではOn-Demandが運用上適切。月額~$0.003）
4. **Lambda ARM/Graviton2**アーキテクチャ（x86比20%安価）
5. **EventBridge Scheduler**（1,400万回/月が永続無料）
6. **Cognito Lite**ティア（10,000MAUまで永続無料）
7. Lambdaメモリ内トークンキャッシュ（ウォームスタート時のAPI呼び出し削減）
8. CloudFront Free Flat-Rateプラン（CDN + WAF + DDoS保護込み$0）

---

## 4. フロントエンド配信：Cloudflare Pagesを選ぶべき理由

### 2つの選択肢の比較

| 評価軸 | S3 + CloudFront + Cloudflare DNS | Cloudflare Pages |
|---|---|---|
| **月額コスト** | ~$0.50〜$2 | **$0（完全無料）** |
| **セットアップ時間** | 1〜2時間（7-10ステップ） | **5分（3ステップ）** |
| **SSL/TLS** | ACM証明書手動設定（us-east-1必須） | **自動発行・自動更新** |
| **CI/CD** | 別途構築が必要 | **Git push で自動デプロイ** |
| **SPA対応** | カスタムエラーレスポンス設定必要 | **ネイティブ対応（設定不要）** |
| **帯域制限** | 1TB/月（無料枠） | **無制限** |
| **プレビューデプロイ** | なし（自前構築） | **ブランチごと自動生成** |
| **キャッシュ無効化** | 手動invalidation必要 | **自動（デプロイ即反映）** |
| **二重キャッシュリスク** | Cloudflare Proxy有効時に発生 | **なし** |

### 推奨：Cloudflare Pages（決定的優位）

**Cloudflare Pagesが圧倒的に優れている。** 無制限の帯域・リクエスト、自動SSL、Git連携CI/CD、ブランチプレビューが全て無料枠に含まれる。S3+CloudFront構成はACM証明書設定（us-east-1リージョン必須）、CloudFront Custom Error Response、キャッシュ無効化パイプラインなど設定項目が多く、Cloudflare Proxyを有効にすると二重キャッシュ問題が発生するリスクもある。

### Cloudflare Pages セットアップ手順

```bash
# 1. Reactアプリをビルド確認
npm run build

# 2. GitHubにプッシュ後、Cloudflareダッシュボードで：
#    Workers & Pages → Create → Pages → Connect to Git
#    Framework preset: Vite (React)
#    Build command: npm run build
#    Output directory: dist
#    環境変数: VITE_API_URL=https://{api-id}.execute-api.{region}.amazonaws.com/prod

# 3. Custom domains → health.yourdomain.com を追加
#    → DNS自動設定、SSL自動発行（完了まで数分）
```

以後は`git push`するだけで自動ビルド・自動デプロイが行われる。

---

## 5. セキュリティ設計：トークン保管とデータ分離

### Fitbitトークン保管のハイブリッド戦略

**ユーザー単位のOAuthトークン → SSM Parameter Store（Standard SecureString）**を使用する。1ユーザーあたりのAccess Token + Refresh Tokenは合計2KB以下で、Standard Parameterの4KB上限に収まる。KMSで暗号化され、階層パス（`/fitbit/users/{cognitoSub}/tokens`）で整理できる。**50ユーザーでも$0/月**である。

**アプリ共通のClient ID/Secret → Secrets Manager（$0.40/月）** を使用する。全ユーザー共通で1つのシークレットのみ必要。リソースベースポリシーによる追加防御とCloudTrail監査統合が利点。

Secrets Managerをユーザー単位で使うと50ユーザーで**$20/月**になるため、Parameter Storeとの使い分けが必須である。

### トークン自動リフレッシュフロー

```
EventBridge Scheduler（6時間ごと）
  → Lambda起動
    → DynamoDBから token_expires_at < now + 2時間 のユーザーを取得
    → 各ユーザーについて：
      1. SSMからトークン取得
      2. Secrets ManagerからClient ID/Secret取得
      3. POST https://api.fitbit.com/oauth2/token
         (grant_type=refresh_token)
      4. 成功時：新トークンをSSMに上書き保存
      5. 失敗時(401 invalid_grant)：ユーザーステータスを
         "reauth_required"に更新、再認証を促す
```

Fitbit Refresh Tokenは**使い切り型**（1回使用で新しいRefresh Tokenが発行される）のため、同一リフレッシュリクエストの2分間のべき等性保護を考慮し、DynamoDBの条件付き書き込み（`token_version`チェック）で同時実行を防止する。

### DynamoDBマルチテナントデータ分離

シングルテーブル設計でPartition Key（`USER#{cognitoSub}`）によるテナント分離を行う。

```
PK: USER#abc123    SK: HEARTRATE#2026-04-04   resting_hr: 62, zones: {...}
PK: USER#abc123    SK: SLEEP#2026-04-04       duration: 28800000, efficiency: 92
PK: USER#abc123    SK: ACTIVITY#2026-04-04    steps: 10234, calories: 2100
PK: USER#abc123    SK: PROFILE                email: user@example.com
```

GSI1（PK: `USER#{id}`, SK: `{DATE}#{TYPE}`）により「ユーザーXの3月1日〜4月1日の全データ」を効率的にクエリできる。IAMポリシーの`dynamodb:LeadingKeys`条件で、Lambda関数がCognito JWT の`sub`クレームに対応するパーティションキーのデータにのみアクセスできるよう制限する。

### セキュリティ多層防御

| 防御層 | メカニズム | 目的 |
|---|---|---|
| エッジ | Cloudflare DDoS保護 | 大規模攻撃遮断 |
| API Gateway | Cognito JWT Authorizer | 未認証リクエスト排除 |
| Lambda | JWTのsubクレーム抽出 | ユーザースコープの強制 |
| DynamoDB | IAM LeadingKeys条件 | パーティションレベル分離 |
| SSM/Secrets | IAMパスベースポリシー | シークレットアクセス制限 |

Fitbitトークンはサーバーサイドのみで扱い、**フロントエンドに一切露出させない**。フロントエンドはCognito JWTで認証し、Lambda関数が内部的にFitbit APIを呼び出す。

---

## 6. 全体ロードマップ：4フェーズ段階開発

### Phase 1：データ収集基盤（2〜3週間）

目標：Fitbit APIからヘルスデータを定期取得してDynamoDBに蓄積する最小構成の構築。

- **EventBridge Scheduler** → **Lambda**（6時間間隔バッチ）→ Fitbit API呼び出し → **DynamoDB**保存
- 取得対象データ（Phase 1）：心拍数（日次サマリー+ゾーン）、睡眠（ステージ+効率）、活動量（歩数・カロリー・アクティブ分）、HRV（dailyRmssd）、SpO2
- SSM Parameter Storeにトークン保存、自動リフレッシュLambda実装
- DynamoDBテーブル設計（シングルテーブル、`USER#id` + `TYPE#date`スキーマ）
- 推定コスト：**$0.00〜$0.40/月**

### Phase 2：ダッシュボードUI（3〜4週間）

目標：収集データをリアルタイムに可視化するSPAダッシュボードの構築。

- **Cloudflare Pages**にReact + Viteアプリをデプロイ（Chart.js or Recharts使用）
- **API Gateway（HTTP API）** → Lambda → DynamoDB（読み取り専用API）
- 基本ダッシュボード：今日のサマリーカード（心拍数・歩数・睡眠時間・HRV）、7日間トレンドグラフ
- Cognito不要（Phase 1-2はシングルユーザー、API Keyまたは簡易トークンで認証）
- 推定コスト：**$0.00〜$0.40/月**

### Phase 3：分析・可視化強化（4〜6週間）

目標：競合サービスに匹敵する分析機能の追加。

- **Recovery Score算出**：HRV + RHR + 睡眠効率から独自スコア（0-100）を算出するロジック実装
- **トレンド分析**：30日/90日/6ヶ月の長期トレンドビュー、移動平均、前週比・前月比
- **相関分析**（Exist.ioモデル）：睡眠品質↔翌日HRV、活動量↔睡眠効率など、ピアソン相関係数を計算して可視化
- 体重・体温・SpO2・呼吸数のデータ取得追加
- ダッシュボードの美観向上（ダークモード、カラーコーディングされたスコア表示）
- 推定コスト：**$0.00〜$0.40/月**（コンピュート量増加もLambda無料枠内）

### Phase 4：マルチユーザースケール対応（3〜4週間）

目標：他のFitbitユーザーが自分のデータで利用できるマルチテナント化。

- **Cognito User Pool**（Liteティア）を導入、メール+パスワード認証
- サインアップフロー：Cognito登録 → Fitbit OAuth認可 → トークン保存（SSM `/fitbit/users/{sub}/tokens`）
- API Gateway Cognito Authorizerの適用
- IAM LeadingKeys条件によるDynamoDB行レベルアクセス制御
- ユーザーダッシュボード：自分のデータのみ表示される分離設計
- 管理機能：トークン失効通知、再認証フロー
- 推定コスト：**~$0.60/月（50ユーザー時）**

---

## 結論：実現可能性と設計上の重要判断

本設計は**月額~$0.40〜$0.60**（既存AWSアカウント前提）でフル機能の個人向けヘルスBIツールを運用でき、50ユーザーまでスケールしても$5/月予算の12%未満に収まる。設計上の最重要判断は3点：フロントエンドに**Cloudflare Pages**を選択すること（S3+CloudFront比でコスト$0、セットアップ時間1/20）、トークン保管に**SSM Parameter Store + Secrets Managerのハイブリッド**を採用すること（全量Secrets Managerの1/50のコスト）、DynamoDBを**On-Demandモード**で運用すること（既存アカウントではProvisioned永続無料枠が他テーブルと共有されるため、キャパシティ管理不要のOn-Demandが適切）である。

2026年9月にFitbit Web APIのdeprecationが予定されているため、Phase 3完了後にGoogle Health APIへの移行パスを調査・設計しておくことを強く推奨する。データ収集Lambda関数にAPIアダプターパターンを採用し、エンドポイント切り替えを最小コストで行える設計が望ましい。
