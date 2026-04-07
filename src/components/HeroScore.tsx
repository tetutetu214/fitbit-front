import { useMemo, useState } from 'react';
import type { HealthData } from '../types/health';
import { Card } from './ui/Card';

interface HeroScoreProps {
  data: HealthData;
}

interface Contributor {
  label: string;
  score: number;
  weight: number;
  detail: string;
}

function avg(values: (number | null)[]): number | null {
  const nums = values.filter((v): v is number => v !== null && !Number.isNaN(v));
  if (nums.length === 0) return null;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function clamp(n: number, min = 0, max = 100): number {
  return Math.max(min, Math.min(max, n));
}

function computeContributors(data: HealthData): Contributor[] {
  const last = data.dates.length - 1;
  if (last < 0) return [];

  // Sleep: 480 min target, weight efficiency
  const sleepMin = data.sleep_minutes[last] ?? 0;
  const sleepEff = data.sleep_efficiency[last] ?? null;
  const sleepDurScore = clamp((sleepMin / 480) * 100);
  const sleepScore = sleepEff !== null
    ? clamp(sleepDurScore * 0.6 + sleepEff * 0.4)
    : sleepDurScore;

  // HRV: compare last vs personal baseline (mean of series)
  const hrvBaseline = avg(data.hrv_rmssd);
  const hrvLast = data.hrv_rmssd[last];
  const hrvScore = hrvLast !== null && hrvBaseline !== null && hrvBaseline > 0
    ? clamp(50 + ((hrvLast - hrvBaseline) / hrvBaseline) * 100)
    : 50;

  // Resting HR: lower vs baseline is better
  const rhrBaseline = avg(data.resting_hr);
  const rhrLast = data.resting_hr[last];
  const rhrScore = rhrLast !== null && rhrBaseline !== null && rhrBaseline > 0
    ? clamp(50 - ((rhrLast - rhrBaseline) / rhrBaseline) * 100)
    : 50;

  // Activity: steps vs 10k
  const steps = data.steps[last] ?? 0;
  const activityScore = clamp((steps / 10000) * 100);

  return [
    {
      label: '睡眠',
      score: Math.round(sleepScore),
      weight: 0.35,
      detail: `${Math.floor(sleepMin / 60)}h ${sleepMin % 60}m${sleepEff !== null ? ` / 効率 ${sleepEff}%` : ''}`,
    },
    {
      label: 'HRV',
      score: Math.round(hrvScore),
      weight: 0.25,
      detail: hrvLast !== null ? `${hrvLast.toFixed(1)} ms` : '—',
    },
    {
      label: '安静時心拍',
      score: Math.round(rhrScore),
      weight: 0.2,
      detail: rhrLast !== null ? `${rhrLast} bpm` : '—',
    },
    {
      label: 'アクティビティ',
      score: Math.round(activityScore),
      weight: 0.2,
      detail: `${steps.toLocaleString()} 歩`,
    },
  ];
}

function zoneFor(score: number): { color: string; ring: string; label: string } {
  if (score >= 85) return { color: '#10b981', ring: '#10b981', label: '最適' };
  if (score >= 70) return { color: '#f59e0b', ring: '#f59e0b', label: '良好' };
  return { color: '#f43f5e', ring: '#f43f5e', label: '要注意' };
}

function contextMessage(score: number, contributors: Contributor[]): string {
  const weakest = [...contributors].sort((a, b) => a.score - b.score)[0];
  if (score >= 85) return '今日は最適なコンディション。挑戦的な活動に向いています。';
  if (score >= 70) return `良好な状態です。${weakest ? `${weakest.label}に少し気を配ると更に向上します。` : ''}`;
  return `回復が必要かもしれません。${weakest ? `特に${weakest.label}が低めです。` : ''}`;
}

interface ScoreRingProps {
  score: number;
  color: string;
}

function ScoreRing({ score, color }: ScoreRingProps) {
  const size = 200;
  const stroke = 14;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <svg width={size} height={size} className="block" role="img" aria-label={`Readiness score ${score}`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="#262b33"
        strokeWidth={stroke}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 1.2s ease-out' }}
      />
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        fontSize="56"
        fontWeight="700"
      >
        {score}
      </text>
    </svg>
  );
}

interface DetailSheetProps {
  contributors: Contributor[];
  onClose: () => void;
}

function DetailSheet({ contributors, onClose }: DetailSheetProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 sm:items-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md rounded-t-2xl border border-border bg-card p-5 sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-text">Contributors</h3>
          <button
            onClick={onClose}
            className="text-text2 hover:text-text"
            aria-label="閉じる"
          >
            ✕
          </button>
        </div>
        <ul className="space-y-3">
          {contributors.map((c) => {
            const z = zoneFor(c.score);
            return (
              <li key={c.label}>
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="text-sm text-text">{c.label}</span>
                  <span className="text-xs text-text2">
                    {c.detail} · 重み {Math.round(c.weight * 100)}%
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#262b33]">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${c.score}%`,
                        backgroundColor: z.color,
                        transition: 'width 0.8s ease-out',
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-sm font-semibold" style={{ color: z.color }}>
                    {c.score}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

export function HeroScore({ data }: HeroScoreProps) {
  const [open, setOpen] = useState(false);

  const { score, contributors } = useMemo(() => {
    const cs = computeContributors(data);
    if (cs.length === 0) return { score: 0, contributors: [] };
    const totalWeight = cs.reduce((a, c) => a + c.weight, 0);
    const weighted = cs.reduce((a, c) => a + c.score * c.weight, 0) / totalWeight;
    return { score: Math.round(weighted), contributors: cs };
  }, [data]);

  if (contributors.length === 0) return null;

  const zone = zoneFor(score);
  const message = contextMessage(score, contributors);

  return (
    <div className="px-8 pt-5 max-md:px-4">
      <Card
        className="flex cursor-pointer flex-col items-center gap-3 py-6 transition-colors hover:border-accent"
        onClick={() => setOpen(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setOpen(true);
          }
        }}
        aria-label={`Readiness ${score} ${zone.label}`}
      >
        <div className="text-[11px] uppercase tracking-wider text-text2">Readiness</div>
        <ScoreRing score={score} color={zone.ring} />
        <div
          className="rounded-full px-3 py-1 text-xs font-semibold"
          style={{ backgroundColor: `${zone.color}22`, color: zone.color }}
        >
          {zone.label}
        </div>
        <p className="max-w-md text-center text-sm text-text2">{message}</p>
        <div className="text-[11px] text-text3">タップで詳細を表示</div>
      </Card>
      {open && <DetailSheet contributors={contributors} onClose={() => setOpen(false)} />}
    </div>
  );
}
