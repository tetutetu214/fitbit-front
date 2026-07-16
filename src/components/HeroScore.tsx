import { useEffect, useMemo, useState } from 'react';
import type { HealthData } from '../types/health';
import { Card } from './ui/Card';
import { BottomSheet } from './ui/BottomSheet';
import { computeContributors, hasDataAt, zoneFor, type Contributor } from '../lib/readiness';

interface HeroScoreProps {
  data: HealthData;
  index: number;
}

/**
 * Zone palette for ContributorList progress bars.
 * Blue = optimal, Orange = caution, Red = needs improvement.
 */
function contributorZoneFor(score: number): { color: string } {
  if (score >= 85) return { color: '#00bcd4' };
  if (score >= 70) return { color: '#ffb347' };
  return { color: '#ff6b6b' };
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

interface ContributorListProps {
  contributors: Contributor[];
}

function ContributorList({ contributors }: ContributorListProps) {
  // Start progress bars at 0 and animate to their target width after mount
  // so the fill-in animation plays every time the sheet opens.
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setAnimated(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <ul className="space-y-4">
      {contributors.map((c, i) => {
        const z = contributorZoneFor(c.score);
        return (
          <li key={c.label}>
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-sm font-medium text-text">{c.label}</span>
              <span className="text-xs text-text2">{c.detail}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#262b33]">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: animated ? `${c.score}%` : '0%',
                    backgroundColor: z.color,
                    transition: `width 0.9s cubic-bezier(0.22, 1, 0.36, 1) ${i * 80}ms`,
                  }}
                />
              </div>
              <span
                className="w-8 text-right text-sm font-semibold"
                style={{ color: z.color }}
              >
                {c.score}
              </span>
            </div>
            <div className="mt-1 text-[11px] text-text3">{c.baseline}</div>
          </li>
        );
      })}
    </ul>
  );
}

export function HeroScore({ data, index }: HeroScoreProps) {
  const [open, setOpen] = useState(false);

  const { score, contributors } = useMemo(() => {
    if (!hasDataAt(data, index)) return { score: 0, contributors: [] as Contributor[] };
    const cs = computeContributors(data, index);
    if (cs.length === 0) return { score: 0, contributors: [] as Contributor[] };
    const totalWeight = cs.reduce((a, c) => a + c.weight, 0);
    const weighted = cs.reduce((a, c) => a + c.score * c.weight, 0) / totalWeight;
    return { score: Math.round(weighted), contributors: cs };
  }, [data, index]);

  if (contributors.length === 0) {
    return (
      <div className="px-8 pt-5 max-md:px-4">
        <Card className="flex flex-col items-center gap-2 py-8">
          <div className="text-[11px] uppercase tracking-wider text-text2">Readiness</div>
          <div className="text-sm text-text2">この日のデータがありません</div>
        </Card>
      </div>
    );
  }

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
      {open && (
        <BottomSheet title="Contributors" onClose={() => setOpen(false)} snapPoints={[60, 85]}>
          <ContributorList contributors={contributors} />
        </BottomSheet>
      )}
    </div>
  );
}
