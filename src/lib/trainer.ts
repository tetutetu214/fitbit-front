import type { HealthData } from '../types/health';
import { avg, computeContributors, hasDataAt, readinessScore, zoneFor } from './readiness';

/** AIトレーナーAPI (Lambda Function URL)。未設定なら機能を無効化する */
export const TRAINER_API_URL: string | undefined =
  import.meta.env.VITE_TRAINER_API_URL || undefined;

export interface TrainerSummary {
  date: string;
  readiness: { score: number; zone: string } | null;
  contributors: { label: string; score: number; detail: string; baseline: string }[];
  metrics: {
    steps: number;
    stepsGoal: number;
    activeCalories: number;
    sedentaryMinutes: number | null;
    sleepMinutes: number;
    sleepEfficiency: number | null;
    deepMinutes: number;
    lightMinutes: number;
    remMinutes: number;
    wakeMinutes: number;
    restingHr: number | null;
    hrvRmssd: number | null;
    spo2Avg: number | null;
    spo2Min: number | null;
    weightKg: number | null;
    bodyFatPct: number | null;
  };
  /** 直近7日間(当日含む)の平均。トレーナーがベースライン比較に使う */
  baseline7d: {
    steps: number | null;
    sleepMinutes: number | null;
    restingHr: number | null;
    hrvRmssd: number | null;
  };
}

function round1(n: number | null): number | null {
  return n === null ? null : Math.round(n * 10) / 10;
}

/** 指定日のヘルスデータをAIトレーナーに渡すサマリーへ変換する */
export function buildTrainerSummary(data: HealthData, index: number): TrainerSummary | null {
  if (!hasDataAt(data, index)) return null;

  const score = readinessScore(data, index);
  const from = Math.max(0, index - 6);
  const window = <T,>(arr: T[]): T[] => arr.slice(from, index + 1);

  return {
    date: data.dates[index],
    readiness: score === null ? null : { score, zone: zoneFor(score).label },
    contributors: computeContributors(data, index).map(({ label, score: s, detail, baseline }) => ({
      label,
      score: s,
      detail,
      baseline,
    })),
    metrics: {
      steps: data.steps[index] ?? 0,
      stepsGoal: data.goals[index]?.steps ?? 10000,
      activeCalories: data.active_calories[index] ?? 0,
      sedentaryMinutes: data.sedentary_minutes[index],
      sleepMinutes: data.sleep_minutes[index] ?? 0,
      sleepEfficiency: data.sleep_efficiency[index],
      deepMinutes: data.deep[index] ?? 0,
      lightMinutes: data.light[index] ?? 0,
      remMinutes: data.rem[index] ?? 0,
      wakeMinutes: data.wake[index] ?? 0,
      restingHr: data.resting_hr[index],
      hrvRmssd: round1(data.hrv_rmssd[index]),
      spo2Avg: round1(data.spo2_avg[index]),
      spo2Min: round1(data.spo2_min[index]),
      weightKg: round1(data.weight[index]),
      bodyFatPct: round1(data.body_fat[index]),
    },
    baseline7d: {
      steps: round1(avg(window(data.steps))),
      sleepMinutes: round1(avg(window(data.sleep_minutes))),
      restingHr: round1(avg(window(data.resting_hr))),
      hrvRmssd: round1(avg(window(data.hrv_rmssd))),
    },
  };
}

const REQUEST_TIMEOUT_MS = 60_000;

/** サマリーをLambdaへPOSTし、AIトレーナーの解説テキストを取得する */
export async function fetchTrainerAdvice(summary: TrainerSummary): Promise<string> {
  if (!TRAINER_API_URL) {
    throw new Error('VITE_TRAINER_API_URL が設定されていません。');
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(TRAINER_API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(summary),
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`トレーナーAPIがエラーを返しました (HTTP ${res.status})`);
    }
    const json = (await res.json()) as { advice?: string };
    if (!json.advice) {
      throw new Error('トレーナーAPIの応答が空でした');
    }
    return json.advice;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new Error('トレーナーAPIの応答がタイムアウトしました');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}
