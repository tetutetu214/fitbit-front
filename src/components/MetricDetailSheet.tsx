import { useMemo, useState } from 'react';
import {
  ResponsiveContainer,
  LineChart, Line,
  XAxis, YAxis, CartesianGrid,
  Tooltip,
} from 'recharts';
import type { HealthData } from '../types/health';
import { BottomSheet } from './ui/BottomSheet';

export type MetricKey =
  | 'resting_hr' | 'steps' | 'sleep' | 'hrv'
  | 'spo2' | 'sedentary' | 'weight' | 'body_fat';

interface MetricConfig {
  label: string;
  color: string;
  unit: string;
  series: (data: HealthData) => (number | null)[];
  format: (v: number) => string;
  note: string;
}

function fmtMinutes(v: number): string {
  return `${Math.floor(v / 60)}h ${Math.round(v % 60)}m`;
}

const METRICS: Record<MetricKey, MetricConfig> = {
  resting_hr: {
    label: '安静時心拍数', color: '#ff6b6b', unit: 'bpm',
    series: (d) => d.resting_hr, format: (v) => String(Math.round(v)),
    note: '低いほど回復状態が良好とされます（正常: 60〜100 bpm）',
  },
  steps: {
    label: '歩数', color: '#00d68f', unit: '歩',
    series: (d) => d.steps, format: (v) => Math.round(v).toLocaleString(),
    note: '目標は 10,000 歩です',
  },
  sleep: {
    label: '睡眠時間', color: '#a78bfa', unit: '',
    series: (d) => d.sleep_minutes, format: fmtMinutes,
    note: '目標は 8 時間です',
  },
  hrv: {
    label: 'HRV（自律神経ゆらぎ）', color: '#00d68f', unit: 'ms',
    series: (d) => d.hrv_rmssd, format: (v) => v.toFixed(1),
    note: '個人差が大きいため自分自身の推移を参考にしてください',
  },
  spo2: {
    label: '血中酸素濃度', color: '#00bcd4', unit: '%',
    series: (d) => d.spo2_avg, format: (v) => v.toFixed(1),
    note: '正常範囲: 95〜100%（睡眠中に計測）',
  },
  sedentary: {
    label: '座位時間', color: '#7d8590', unit: '',
    series: (d) => d.sedentary_minutes, format: fmtMinutes,
    note: '長時間の座位は健康リスクを高めます',
  },
  weight: {
    label: '体重', color: '#f6c177', unit: 'kg',
    series: (d) => d.weight, format: (v) => v.toFixed(1),
    note: 'TANITA 体組成計で計測',
  },
  body_fat: {
    label: '体脂肪率', color: '#eb6f92', unit: '%',
    series: (d) => d.body_fat, format: (v) => v.toFixed(1),
    note: 'TANITA 体組成計で計測',
  },
};

const RANGES = [7, 14, 30] as const;

interface MetricDetailSheetProps {
  metric: MetricKey;
  data: HealthData;
  index: number;
  onClose: () => void;
}

function shortDate(d: string) {
  const m = d.match(/(\d+)-(\d+)$/);
  return m ? `${parseInt(m[1])}/${parseInt(m[2])}` : d;
}

export function MetricDetailSheet({ metric, data, index, onClose }: MetricDetailSheetProps) {
  const [range, setRange] = useState<(typeof RANGES)[number]>(7);
  const cfg = METRICS[metric];

  const { chartData, stats, current } = useMemo(() => {
    const series = cfg.series(data);
    const from = Math.max(0, index - range + 1);
    const window = data.dates
      .slice(from, index + 1)
      .map((d, i) => ({ date: d, value: series[from + i] }))
      .filter((r): r is { date: string; value: number } => r.value !== null && r.value !== 0);
    const values = window.map((r) => r.value);
    return {
      chartData: window,
      stats: values.length > 0
        ? {
            avg: values.reduce((a, b) => a + b, 0) / values.length,
            min: Math.min(...values),
            max: Math.max(...values),
          }
        : null,
      current: series[index],
    };
  }, [cfg, data, index, range]);

  return (
    <BottomSheet title={cfg.label} onClose={onClose}>
      <div className="mb-3 flex items-end justify-between">
        <div>
          <span className="text-3xl font-bold" style={{ color: cfg.color }}>
            {current !== null && current !== 0 ? cfg.format(current) : '—'}
          </span>
          {cfg.unit && <span className="ml-1 text-sm text-text2">{cfg.unit}</span>}
          <span className="ml-2 text-xs text-text3">{data.dates[index]}</span>
        </div>
        <div className="flex shrink-0 gap-1" role="group" aria-label="表示期間">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded-full px-2.5 py-1 text-[11px] whitespace-nowrap transition-colors ${
                range === r
                  ? 'bg-accent/20 font-semibold text-accent'
                  : 'text-text2 hover:bg-card2'
              }`}
            >
              {r}日
            </button>
          ))}
        </div>
      </div>

      {chartData.length >= 2 ? (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#21262d" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={shortDate}
              tick={{ fill: '#7d8590', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#7d8590', fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={44}
              domain={['auto', 'auto']}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0];
                return (
                  <div className="rounded-md border border-border bg-card2 px-2.5 py-1.5 text-xs text-text">
                    {cfg.format(Number(p.value))}{cfg.unit && ` ${cfg.unit}`}
                  </div>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={cfg.color}
              strokeWidth={2.5}
              dot={{ r: 3, fill: cfg.color }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[180px] items-center justify-center text-xs text-text2">
          この期間のデータが不足しています
        </div>
      )}

      {stats && (
        <div className="mt-3 grid grid-cols-3 gap-2 text-center">
          {[
            { label: `${range}日平均`, value: stats.avg },
            { label: '最小', value: stats.min },
            { label: '最大', value: stats.max },
          ].map((s) => (
            <div key={s.label} className="rounded-lg bg-card2 py-2">
              <div className="text-[10px] text-text3">{s.label}</div>
              <div className="text-sm font-semibold text-text">
                {cfg.format(s.value)}{cfg.unit && <span className="text-[10px] text-text2"> {cfg.unit}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="mt-3 text-[11px] text-text3">※{cfg.note}</p>
    </BottomSheet>
  );
}
