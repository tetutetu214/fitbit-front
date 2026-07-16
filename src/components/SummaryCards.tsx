import { useState } from 'react';
import type { HealthData } from '../types/health';
import { Card } from './ui/Card';
import { MetricDetailSheet, type MetricKey } from './MetricDetailSheet';

interface SummaryCardsProps {
  data: HealthData;
  index: number;
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
 * 選択日の値をベースライン（選択日を除く系列平均）と比較し、
 * トレンド矢印・差分テキスト・ゾーンを算出する。
 * goodWhen='none' はゾーン判定なし（体重など良し悪しが一概に言えない指標）。
 */
function contextOf(
  arr: (number | null)[] | undefined,
  goodWhen: 'up' | 'down' | 'none',
  index: number,
): Context | null {
  if (!arr) return null;
  const current = arr[index];
  if (current === null || current === undefined || current === 0) return null;

  const others = arr
    .filter((_, i) => i !== index)
    .filter((v): v is number => v !== null && v !== 0);
  if (others.length < 1) return null;

  const baseline = others.reduce((a, b) => a + b, 0) / others.length;
  if (baseline === 0) return null;

  const diffPct = ((current - baseline) / baseline) * 100;
  const arrow = diffPct > 3 ? '↗' : diffPct < -3 ? '↘' : '→';
  const text = `平均比 ${diffPct >= 0 ? '+' : ''}${Math.round(diffPct)}%`;

  let zone: Zone = 'neutral';
  if (goodWhen !== 'none') {
    const signedDiff = goodWhen === 'up' ? diffPct : -diffPct;
    zone = signedDiff >= -3 ? 'good' : signedDiff >= -10 ? 'warning' : 'attention';
  }
  return { arrow, text, zone };
}

export function SummaryCards({ data, index }: SummaryCardsProps) {
  const [openMetric, setOpenMetric] = useState<MetricKey | null>(null);

  if (index < 0 || index >= data.dates.length) return null;

  const sleepMin = data.sleep_minutes?.[index] ?? 0;
  const sedentary = data.sedentary_minutes?.[index] ?? null;
  const weight = data.weight?.[index] ?? null;
  const bodyFat = data.body_fat?.[index] ?? null;

  const cards: Array<{
    metric: MetricKey;
    label: string;
    val: string;
    unit?: string;
    color: string;
    sub: string;
    context: Context | null;
  }> = [
    {
      metric: 'resting_hr',
      label: '安静時心拍数',
      val: data.resting_hr[index] !== null ? String(data.resting_hr[index]) : '—',
      unit: 'bpm',
      color: '#ff6b6b',
      sub: '正常: 60〜100',
      context: contextOf(data.resting_hr, 'down', index),
    },
    {
      metric: 'steps',
      label: '歩数',
      val: data.steps[index] > 0 ? data.steps[index].toLocaleString() : '—',
      color: data.steps[index] >= 10000 ? '#00d68f' : '#4ecdc4',
      sub: data.steps[index] >= 10000 ? '目標達成!' : '目標: 10,000',
      context: contextOf(data.steps, 'up', index),
    },
    {
      metric: 'sleep',
      label: '睡眠',
      val:
        sleepMin > 0
          ? `${Math.floor(sleepMin / 60)}h ${sleepMin % 60}m`
          : '—',
      color: '#a78bfa',
      sub: data.sleep_efficiency[index] ? `効率: ${data.sleep_efficiency[index]}%` : '',
      context: contextOf(data.sleep_minutes, 'up', index),
    },
    {
      metric: 'hrv',
      label: 'HRV',
      val: data.hrv_rmssd[index] !== null ? data.hrv_rmssd[index]!.toFixed(1) : '—',
      unit: 'ms',
      color: '#00d68f',
      sub: '高いほど良好',
      context: contextOf(data.hrv_rmssd, 'up', index),
    },
    {
      metric: 'spo2',
      label: '血中酸素',
      val: data.spo2_avg[index] !== null ? data.spo2_avg[index]!.toFixed(1) : '—',
      unit: '%',
      color: '#00bcd4',
      sub: '正常: 95〜100%',
      context: contextOf(data.spo2_avg, 'up', index),
    },
    {
      metric: 'sedentary',
      label: '座位時間',
      val: sedentary !== null ? `${Math.floor(sedentary / 60)}h ${sedentary % 60}m` : '—',
      color: '#7d8590',
      sub: '長時間の座位に注意',
      context: contextOf(data.sedentary_minutes, 'down', index),
    },
    {
      metric: 'weight',
      label: '体重',
      val: weight !== null ? weight.toFixed(1) : '—',
      unit: 'kg',
      color: '#f6c177',
      sub: 'TANITA 計測',
      context: contextOf(data.weight, 'none', index),
    },
    {
      metric: 'body_fat',
      label: '体脂肪率',
      val: bodyFat !== null ? bodyFat.toFixed(1) : '—',
      unit: '%',
      color: '#eb6f92',
      sub: 'TANITA 計測',
      context: contextOf(data.body_fat, 'none', index),
    },
  ];

  return (
    <>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3 px-8 py-5 max-md:grid-cols-2 max-md:px-4">
        {cards.map((c) => (
          <Card
            key={c.label}
            className="relative cursor-pointer text-center transition-colors hover:border-accent"
            role="button"
            tabIndex={0}
            onClick={() => setOpenMetric(c.metric)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setOpenMetric(c.metric);
              }
            }}
            aria-label={`${c.label}の詳細を表示`}
          >
            <span className="absolute top-2 right-2.5 text-xs text-text3" aria-hidden="true">›</span>
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
      {openMetric && (
        <MetricDetailSheet
          metric={openMetric}
          data={data}
          index={index}
          onClose={() => setOpenMetric(null)}
        />
      )}
    </>
  );
}
