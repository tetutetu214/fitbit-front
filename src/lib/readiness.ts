import type { HealthData } from '../types/health';

export interface Contributor {
  label: string;
  score: number;
  weight: number;
  detail: string;
  baseline: string;
}

export function avg(values: (number | null)[]): number | null {
  const nums = values.filter((v): v is number => v !== null && !Number.isNaN(v));
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function clamp(n: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, n));
}

function signed(n: number): string {
  return n > 0 ? `+${n}` : `${n}`;
}

/** 指定日のデータが実質空（スコア計算不能）かどうか */
export function hasDataAt(data: HealthData, index: number): boolean {
  if (index < 0 || index >= data.dates.length) return false;
  return Boolean(
    (data.sleep_minutes[index] ?? 0) > 0 ||
    (data.steps[index] ?? 0) > 0 ||
    data.resting_hr[index] !== null ||
    data.hrv_rmssd[index] !== null,
  );
}

export function computeContributors(data: HealthData, index: number): Contributor[] {
  if (index < 0 || index >= data.dates.length) return [];

  // Sleep duration: 480 min (8h) target
  const sleepMin = data.sleep_minutes[index] ?? 0;
  const sleepDurTarget = 480;
  const sleepDurScore = clamp((sleepMin / sleepDurTarget) * 100);
  const sleepHours = Math.floor(sleepMin / 60);
  const sleepRemMin = sleepMin % 60;
  const sleepDiffMin = sleepMin - sleepDurTarget;

  // Sleep efficiency: target 90%
  const sleepEff = data.sleep_efficiency[index] ?? null;
  const sleepEffTarget = 90;
  const sleepEffScore = sleepEff !== null
    ? clamp(50 + (sleepEff - sleepEffTarget) * 5)
    : 50;

  // Deep sleep: target 90 min
  const deepMin = data.deep[index] ?? 0;
  const deepTarget = 90;
  const deepScore = clamp((deepMin / deepTarget) * 100);

  // HRV: compare vs personal baseline (mean of series)
  const hrvBaseline = avg(data.hrv_rmssd);
  const hrvLast = data.hrv_rmssd[index];
  const hrvScore = hrvLast !== null && hrvBaseline !== null && hrvBaseline > 0
    ? clamp(50 + ((hrvLast - hrvBaseline) / hrvBaseline) * 100)
    : 50;
  const hrvDiffPct = hrvLast !== null && hrvBaseline !== null && hrvBaseline > 0
    ? Math.round(((hrvLast - hrvBaseline) / hrvBaseline) * 100)
    : null;

  // Resting HR: lower vs baseline is better
  const rhrBaseline = avg(data.resting_hr);
  const rhrLast = data.resting_hr[index];
  const rhrScore = rhrLast !== null && rhrBaseline !== null && rhrBaseline > 0
    ? clamp(50 - ((rhrLast - rhrBaseline) / rhrBaseline) * 100)
    : 50;
  const rhrDiff = rhrLast !== null && rhrBaseline !== null
    ? rhrLast - Math.round(rhrBaseline)
    : null;

  // Activity: steps vs daily goal (default 10k)
  const stepsGoal = data.goals[index]?.steps ?? 10000;
  const steps = data.steps[index] ?? 0;
  const activityScore = clamp((steps / stepsGoal) * 100);

  return [
    {
      label: '睡眠時間',
      score: Math.round(sleepDurScore),
      weight: 0.25,
      detail: `${sleepHours}時間${sleepRemMin}分`,
      baseline: `目標 ${sleepDurTarget / 60}時間に対し ${signed(sleepDiffMin)}分`,
    },
    {
      label: '睡眠効率',
      score: Math.round(sleepEffScore),
      weight: 0.1,
      detail: sleepEff !== null ? `${sleepEff}%` : '—',
      baseline: sleepEff !== null
        ? `目標 ${sleepEffTarget}% に対し ${signed(sleepEff - sleepEffTarget)}pt`
        : 'データなし',
    },
    {
      label: '深い睡眠',
      score: Math.round(deepScore),
      weight: 0.1,
      detail: `${deepMin}分`,
      baseline: `目標 ${deepTarget}分に対し ${signed(deepMin - deepTarget)}分`,
    },
    {
      label: 'HRV',
      score: Math.round(hrvScore),
      weight: 0.2,
      detail: hrvLast !== null ? `${hrvLast.toFixed(1)} ms` : '—',
      baseline: hrvBaseline !== null && hrvDiffPct !== null
        ? `平均 ${hrvBaseline.toFixed(1)} ms に対し ${signed(hrvDiffPct)}%`
        : 'データなし',
    },
    {
      label: '安静時心拍',
      score: Math.round(rhrScore),
      weight: 0.15,
      detail: rhrLast !== null ? `${rhrLast} bpm` : '—',
      baseline: rhrBaseline !== null && rhrDiff !== null
        ? `平均 ${Math.round(rhrBaseline)} bpm に対し ${signed(rhrDiff)} bpm`
        : 'データなし',
    },
    {
      label: 'アクティビティ',
      score: Math.round(activityScore),
      weight: 0.2,
      detail: `${steps.toLocaleString()} 歩`,
      baseline: `目標 ${stepsGoal.toLocaleString()} 歩に対し ${Math.round((steps / stepsGoal) * 100)}%`,
    },
  ];
}

/** 指定日のReadinessスコア。データがない日は null */
export function readinessScore(data: HealthData, index: number): number | null {
  if (!hasDataAt(data, index)) return null;
  const cs = computeContributors(data, index);
  if (cs.length === 0) return null;
  const totalWeight = cs.reduce((a, c) => a + c.weight, 0);
  return Math.round(cs.reduce((a, c) => a + c.score * c.weight, 0) / totalWeight);
}

export function zoneFor(score: number): { color: string; ring: string; label: string } {
  if (score >= 85) return { color: '#10b981', ring: '#10b981', label: '最適' };
  if (score >= 70) return { color: '#f59e0b', ring: '#f59e0b', label: '良好' };
  return { color: '#f43f5e', ring: '#f43f5e', label: '要注意' };
}
