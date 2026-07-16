import { useState } from 'react';
import type { HealthData } from '../types/health';
import { Card } from './ui/Card';
import { CountUp } from './ui/CountUp';
import { Sparkline } from './ui/Sparkline';
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

const SPARK_DAYS = 7;

/** 選択日までの直近7日間のスパークラインデータ */
function sparkPoints(
  data: HealthData,
  arr: (number | null)[] | undefined,
  index: number,
): { date: string; value: number | null }[] {
  if (!arr) return [];
  const from = Math.max(0, index - SPARK_DAYS + 1);
  return data.dates.slice(from, index + 1).map((d, i) => {
    const v = arr[from + i];
    return { date: d, value: v === 0 ? null : v };
  });
}

/** 「7日間HRVトレンド: 12%上昇」形式のアクセシビリティラベル */
function sparkLabel(label: string, points: { value: number | null }[]): string {
  const valid = points.map((p) => p.value).filter((v): v is number => v !== null);
  if (valid.length < 2) return `${SPARK_DAYS}日間${label}トレンド`;
  const first = valid[0];
  const lastV = valid[valid.length - 1];
  if (first === 0) return `${SPARK_DAYS}日間${label}トレンド`;
  const pct = Math.round(((lastV - first) / first) * 100);
  const dir = pct > 3 ? '上昇' : pct < -3 ? '下降' : '横ばい';
  return `${SPARK_DAYS}日間${label}トレンド: ${Math.abs(pct)}%${dir}`;
}

const fmtMinutes = (v: number) => `${Math.floor(v / 60)}h ${Math.round(v % 60)}m`;

export function SummaryCards({ data, index }: SummaryCardsProps) {
  const [openMetric, setOpenMetric] = useState<MetricKey | null>(null);

  if (index < 0 || index >= data.dates.length) return null;

  const nz = (v: number | null | undefined) => (v === null || v === undefined || v === 0 ? null : v);

  const cards: Array<{
    metric: MetricKey;
    label: string;
    value: number | null;
    format: (v: number) => string;
    unit?: string;
    color: string;
    sub: string;
    context: Context | null;
    series: (number | null)[] | undefined;
    band?: [number, number];
  }> = [
    {
      metric: 'resting_hr',
      label: '安静時心拍数',
      value: nz(data.resting_hr[index]),
      format: (v) => String(Math.round(v)),
      unit: 'bpm',
      color: '#ff6b6b',
      sub: '正常: 60〜100',
      context: contextOf(data.resting_hr, 'down', index),
      series: data.resting_hr,
      band: [60, 100],
    },
    {
      metric: 'steps',
      label: '歩数',
      value: nz(data.steps[index]),
      format: (v) => Math.round(v).toLocaleString(),
      color: data.steps[index] >= 10000 ? '#00d68f' : '#4ecdc4',
      sub: data.steps[index] >= 10000 ? '目標達成!' : '目標: 10,000',
      context: contextOf(data.steps, 'up', index),
      series: data.steps,
    },
    {
      metric: 'sleep',
      label: '睡眠',
      value: nz(data.sleep_minutes[index]),
      format: fmtMinutes,
      color: '#a78bfa',
      sub: data.sleep_efficiency[index] ? `効率: ${data.sleep_efficiency[index]}%` : '',
      context: contextOf(data.sleep_minutes, 'up', index),
      series: data.sleep_minutes,
      band: [420, 540],
    },
    {
      metric: 'hrv',
      label: 'HRV',
      value: nz(data.hrv_rmssd[index]),
      format: (v) => v.toFixed(1),
      unit: 'ms',
      color: '#00d68f',
      sub: '高いほど良好',
      context: contextOf(data.hrv_rmssd, 'up', index),
      series: data.hrv_rmssd,
    },
    {
      metric: 'spo2',
      label: '血中酸素',
      value: nz(data.spo2_avg[index]),
      format: (v) => v.toFixed(1),
      unit: '%',
      color: '#00bcd4',
      sub: '正常: 95〜100%',
      context: contextOf(data.spo2_avg, 'up', index),
      series: data.spo2_avg,
      band: [95, 100],
    },
    {
      metric: 'sedentary',
      label: '座位時間',
      value: nz(data.sedentary_minutes?.[index]),
      format: fmtMinutes,
      color: '#7d8590',
      sub: '長時間の座位に注意',
      context: contextOf(data.sedentary_minutes, 'down', index),
      series: data.sedentary_minutes,
    },
    {
      metric: 'weight',
      label: '体重',
      value: nz(data.weight?.[index]),
      format: (v) => v.toFixed(1),
      unit: 'kg',
      color: '#f6c177',
      sub: 'TANITA 計測',
      context: contextOf(data.weight, 'none', index),
      series: data.weight,
    },
    {
      metric: 'body_fat',
      label: '体脂肪率',
      value: nz(data.body_fat?.[index]),
      format: (v) => v.toFixed(1),
      unit: '%',
      color: '#eb6f92',
      sub: 'TANITA 計測',
      context: contextOf(data.body_fat, 'none', index),
      series: data.body_fat,
    },
  ];

  return (
    <>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3 px-8 py-5 max-md:grid-cols-2 max-md:px-4">
        {cards.map((c) => {
          const points = sparkPoints(data, c.series, index);
          return (
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
                {c.value !== null ? <CountUp value={c.value} format={c.format} /> : '—'}
                {c.unit && <span className="text-[13px] text-text2">{c.unit}</span>}
              </div>
              {c.context && c.value !== null && (
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
              <Sparkline
                points={points}
                color={c.color}
                band={c.band}
                ariaLabel={sparkLabel(c.label, points)}
              />
              <div className="mt-1 text-[11px] text-text2">{c.sub}</div>
            </Card>
          );
        })}
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
