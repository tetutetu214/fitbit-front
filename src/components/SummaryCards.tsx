import type { HealthData } from '../types/health';
import { Card } from './ui/Card';

interface SummaryCardsProps {
  data: HealthData;
}

type Zone = 'good' | 'warning' | 'attention' | 'neutral';

const ZONE_STYLE: Record<Zone, { color: string; icon: string }> = {
  good: { color: '#00d68f', icon: '✓' },
  warning: { color: '#ffb347', icon: '⚠' },
  attention: { color: '#ff6b6b', icon: '!' },
  neutral: { color: '#7d8590', icon: '' },
};

interface Context {
  arrow: string;
  text: string;
  zone: Zone;
}

/**
 * 直近値をベースライン（直近値を除く系列平均）と比較し、
 * トレンド矢印・差分テキスト・ゾーンを算出する。
 * goodWhen='none' はゾーン判定なし（体重など良し悪しが一概に言えない指標）。
 */
function contextOf(
  arr: (number | null)[] | undefined,
  goodWhen: 'up' | 'down' | 'none',
): Context | null {
  if (!arr) return null;
  const values = arr
    .map((v, i) => ({ v, i }))
    .filter((x): x is { v: number; i: number } => x.v !== null && x.v !== 0);
  if (values.length < 2) return null;

  const last = values[values.length - 1].v;
  const prior = values.slice(0, -1).map((x) => x.v);
  const baseline = prior.reduce((a, b) => a + b, 0) / prior.length;
  if (baseline === 0) return null;

  const diffPct = ((last - baseline) / baseline) * 100;
  const arrow = diffPct > 3 ? '↗' : diffPct < -3 ? '↘' : '→';
  const text = `平均比 ${diffPct >= 0 ? '+' : ''}${Math.round(diffPct)}%`;

  let zone: Zone = 'neutral';
  if (goodWhen !== 'none') {
    const signedDiff = goodWhen === 'up' ? diffPct : -diffPct;
    zone = signedDiff >= -3 ? 'good' : signedDiff >= -10 ? 'warning' : 'attention';
  }
  return { arrow, text, zone };
}

export function SummaryCards({ data }: SummaryCardsProps) {
  const last = data.dates.length - 1;
  if (last < 0) return null;

  const sleepMin = data.sleep_minutes?.[last] ?? 0;
  const sedentary = data.sedentary_minutes?.[last] ?? null;

  const findLatest = (arr: (number | null)[] | undefined) => {
    if (!arr) return null;
    for (let i = arr.length - 1; i >= 0; i--) {
      if (arr[i] !== null && arr[i] !== undefined) return arr[i];
    }
    return null;
  };
  const weight = findLatest(data.weight);
  const bodyFat = findLatest(data.body_fat);

  const cards = [
    {
      label: '安静時心拍数',
      val: data.resting_hr[last] !== null ? String(data.resting_hr[last]) : '—',
      unit: 'bpm',
      color: '#ff6b6b',
      sub: '正常: 60〜100',
      context: contextOf(data.resting_hr, 'down'),
    },
    {
      label: '歩数',
      val: data.steps[last] > 0 ? data.steps[last].toLocaleString() : '—',
      color: data.steps[last] >= 10000 ? '#00d68f' : '#4ecdc4',
      sub: data.steps[last] >= 10000 ? '目標達成!' : '目標: 10,000',
      context: contextOf(data.steps, 'up'),
    },
    {
      label: '睡眠',
      val:
        sleepMin > 0
          ? `${Math.floor(sleepMin / 60)}h ${sleepMin % 60}m`
          : '—',
      color: '#a78bfa',
      sub: data.sleep_efficiency[last] ? `効率: ${data.sleep_efficiency[last]}%` : '',
      context: contextOf(data.sleep_minutes, 'up'),
    },
    {
      label: 'HRV',
      val: data.hrv_rmssd[last] !== null ? data.hrv_rmssd[last]!.toFixed(1) : '—',
      unit: 'ms',
      color: '#00d68f',
      sub: '高いほど良好',
      context: contextOf(data.hrv_rmssd, 'up'),
    },
    {
      label: '血中酸素',
      val: data.spo2_avg[last] !== null ? data.spo2_avg[last]!.toFixed(1) : '—',
      unit: '%',
      color: '#00bcd4',
      sub: '正常: 95〜100%',
      context: contextOf(data.spo2_avg, 'up'),
    },
    {
      label: '座位時間',
      val: sedentary !== null ? `${Math.floor(sedentary / 60)}h ${sedentary % 60}m` : '—',
      color: '#7d8590',
      sub: '長時間の座位に注意',
      context: contextOf(data.sedentary_minutes, 'down'),
    },
    {
      label: '体重',
      val: weight !== null ? weight.toFixed(1) : '—',
      unit: 'kg',
      color: '#f6c177',
      sub: 'TANITA 計測',
      context: contextOf(data.weight, 'none'),
    },
    {
      label: '体脂肪率',
      val: bodyFat !== null ? bodyFat.toFixed(1) : '—',
      unit: '%',
      color: '#eb6f92',
      sub: 'TANITA 計測',
      context: contextOf(data.body_fat, 'none'),
    },
  ];

  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3 px-8 py-5 max-md:grid-cols-2 max-md:px-4">
      {cards.map((c) => (
        <Card key={c.label} className="text-center">
          <div className="mb-1.5 text-[11px] tracking-wide text-text2">{c.label}</div>
          <div className="text-[32px] font-bold" style={{ color: c.color ?? undefined }}>
            {c.val}
            {c.unit && <span className="text-[13px] text-text2">{c.unit}</span>}
          </div>
          {c.context && c.val !== '—' && (
            <div
              className="mt-0.5 text-[11px] font-medium"
              style={{ color: ZONE_STYLE[c.context.zone].color }}
            >
              <span aria-hidden="true">{c.context.arrow} </span>
              {c.context.text}
              {ZONE_STYLE[c.context.zone].icon && (
                <span aria-hidden="true"> {ZONE_STYLE[c.context.zone].icon}</span>
              )}
            </div>
          )}
          <div className="mt-1 text-[11px] text-text2">{c.sub}</div>
        </Card>
      ))}
    </div>
  );
}
