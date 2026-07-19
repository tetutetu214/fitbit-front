/**
 * AIトレーナー Lambda
 *
 * フロントエンドから受け取った日次ヘルスサマリー(JSON)を
 * Amazon Bedrock の Nova 2 に渡し、その日の状態解説とアドバイスを返す。
 *
 * 呼び出し: Lambda Function URL (POST, CORSはFunction URL側で設定)
 * 環境変数:
 *   MODEL_ID   - BedrockモデルID (default: us.amazon.nova-2-lite-v1:0)
 *   MAX_TOKENS - 応答の最大トークン数 (default: 1024)
 */
import { BedrockRuntimeClient, ConverseCommand } from '@aws-sdk/client-bedrock-runtime';

const MODEL_ID = process.env.MODEL_ID ?? 'us.amazon.nova-2-lite-v1:0';
const MAX_TOKENS = Number(process.env.MAX_TOKENS ?? 1024);
const MAX_BODY_BYTES = 20_000;

const client = new BedrockRuntimeClient({});

const SYSTEM_PROMPT = `あなたは経験豊富なパーソナルトレーナー兼健康コーチです。
ユーザーのFitbitで計測した生体データ(Readinessスコア、睡眠、心拍、HRV、SpO2、活動量、体組成など)をもとに、
その日の体の状態を分かりやすく解説し、今日実行できる具体的なアドバイスを届けます。

回答のルール:
- 日本語で、親しみやすく前向きなトーンで話す
- 次の3部構成で、全体で400字程度にまとめる
  【今日の状態】データから読み取れるコンディションの要約(2〜3文)
  【注目ポイント】特に良い点・気になる点を1〜2個、実際の数値やベースライン比を引用して説明
  【今日のアドバイス】運動強度・休養・睡眠・水分補給など、今日できる具体的な提案
- baseline7d(直近7日平均)との比較を積極的に使う
- 医学的な診断はしない。深刻な体調不良が疑われるデータの場合は医療機関の受診を勧める
- データにない事実を作らない。null や欠損は「データなし」として扱う`;

function response(statusCode, body) {
  return {
    statusCode,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify(body),
  };
}

export const handler = async (event) => {
  const rawBody = event.isBase64Encoded
    ? Buffer.from(event.body ?? '', 'base64').toString('utf-8')
    : (event.body ?? '');

  if (Buffer.byteLength(rawBody, 'utf-8') > MAX_BODY_BYTES) {
    return response(413, { error: 'request body too large' });
  }

  let summary;
  try {
    summary = JSON.parse(rawBody || '{}');
  } catch {
    return response(400, { error: 'invalid JSON body' });
  }
  if (typeof summary !== 'object' || summary === null || typeof summary.date !== 'string') {
    return response(400, { error: 'summary object with "date" is required' });
  }

  const userText =
    `以下は ${summary.date} のヘルスデータサマリーです。この日の状態を解説してください。\n\n` +
    JSON.stringify(summary, null, 2);

  try {
    const result = await client.send(
      new ConverseCommand({
        modelId: MODEL_ID,
        system: [{ text: SYSTEM_PROMPT }],
        messages: [{ role: 'user', content: [{ text: userText }] }],
        inferenceConfig: { maxTokens: MAX_TOKENS, temperature: 0.6, topP: 0.9 },
      }),
    );

    const advice = (result.output?.message?.content ?? [])
      .map((block) => block.text ?? '')
      .join('')
      .trim();

    if (!advice) {
      return response(502, { error: 'empty response from model' });
    }
    return response(200, { advice, model: MODEL_ID, usage: result.usage });
  } catch (err) {
    console.error('Bedrock invocation failed', err);
    return response(502, { error: 'model invocation failed' });
  }
};
