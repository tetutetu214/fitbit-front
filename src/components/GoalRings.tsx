import { useEffect, useState } from 'react';
import type { HealthData } from '../types/health';
import { Card } from './ui/Card';
import { CountUp } from './ui/CountUp';
import { useReducedMotion } from '../lib/useReducedMotion';

interface GoalRingsProps {
  data: HealthData;
  index: number;
}

export function GoalRings({ data, index }: GoalRingsProps) {
  // マウント時に 0% からリングを充填する（reduced-motion 時は即時表示）
  const reduced = useReducedMotion();
  const [filled, setFilled] = useState(reduced);
  useEffect(() => {
    if (reduced) return;
    const id = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(id);
  }, [reduced]);

  if (index < 0 || index >= data.dates.length) return null;

  const goals = data.goals[index] || {};
  const items = [
    { label: '歩数', actual: data.steps[index], goal: goals.steps ?? 10000, unit: '歩' },
    { label: '距離', actual: 0, goal: goals.distance ?? 8.05, unit: 'km', decimals: 1 },
    { label: '消費カロリー', actual: data.active_calories[index] || 0, goal: goals.caloriesOut ?? 2244, unit: 'kcal' },
    { label: '活動時間', actual: 0, goal: goals.activeMinutes ?? 30, unit: '分' },
  ];

  return (
    <div className="grid grid-cols-4 gap-3 px-8 pb-5 max-md:grid-cols-2 max-md:px-4">
      {items.map((item) => {
        const pct = item.goal > 0 ? Math.min((item.actual / item.goal) * 100, 150) : 0;
        const achieved = pct >= 100;
        const color = achieved ? '#ffd700' : '#00bcd4';
        const dashLen = (Math.min(pct, 100) / 100) * 251.2;

        return (
          <Card key={item.label} className="text-center">
            <div
              className={`relative mx-auto mb-2 h-[100px] w-[100px] ${
                achieved && !reduced ? 'animate-goal-pop' : ''
              }`}
            >
              <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#21262d" strokeWidth="6" />
                <circle
                  cx="50" cy="50" r="40" fill="none"
                  stroke={color} strokeWidth="6"
                  strokeDasharray={`${filled ? dashLen : 0} 251.2`}
                  strokeLinecap="round"
                  style={{ transition: 'stroke-dasharray 0.8s ease-out' }}
                />
              </svg>
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-lg font-bold" style={{ color }}>
                <CountUp value={Math.round(pct)} format={(v) => `${Math.round(v)}%`} />
              </div>
            </div>
            <div className="text-[11px] text-text2">{item.label}</div>
            <div className="mt-0.5 text-[11px] text-text3">
              {item.decimals ? item.actual.toFixed(1) : item.actual.toLocaleString()}
              {' / '}
              {item.decimals ? item.goal.toFixed(1) : item.goal.toLocaleString()}
              {' '}{item.unit}
            </div>
          </Card>
        );
      })}
    </div>
  );
}
