import type { HealthData } from '../types/health';
import { Card } from './ui/Card';

interface GoalRingsProps {
  data: HealthData;
}

export function GoalRings({ data }: GoalRingsProps) {
  const last = data.dates.length - 1;
  if (last < 0) return null;

  const goals = data.goals[last] || {};
  const items = [
    { label: '歩数', actual: data.steps[last], goal: goals.steps ?? 10000, unit: '歩' },
    { label: '距離', actual: 0, goal: goals.distance ?? 8.05, unit: 'km', decimals: 1 },
    { label: '消費カロリー', actual: data.active_calories[last] || 0, goal: goals.caloriesOut ?? 2244, unit: 'kcal' },
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
            <div className="relative mx-auto mb-2 h-[100px] w-[100px]">
              <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#21262d" strokeWidth="6" />
                <circle
                  cx="50" cy="50" r="40" fill="none"
                  stroke={color} strokeWidth="6"
                  strokeDasharray={`${dashLen} 251.2`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-lg font-bold" style={{ color }}>
                {Math.round(pct)}%
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
