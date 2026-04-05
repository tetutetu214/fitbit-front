import type { HealthData } from '../types/health';

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
    <div className="goal-rings">
      {items.map((item) => {
        const pct = item.goal > 0 ? Math.min((item.actual / item.goal) * 100, 150) : 0;
        const achieved = pct >= 100;
        const color = achieved ? '#ffd700' : '#00bcd4';
        const dashLen = (Math.min(pct, 100) / 100) * 251.2;

        return (
          <div className="ring-card" key={item.label}>
            <div className="ring-wrap">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="40" fill="none" stroke="#21262d" strokeWidth="6" />
                <circle
                  cx="50" cy="50" r="40" fill="none"
                  stroke={color} strokeWidth="6"
                  strokeDasharray={`${dashLen} 251.2`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="pct" style={{ color }}>{Math.round(pct)}%</div>
            </div>
            <div className="ring-label">{item.label}</div>
            <div className="ring-detail">
              {item.decimals ? item.actual.toFixed(1) : item.actual.toLocaleString()}
              {' / '}
              {item.decimals ? item.goal.toFixed(1) : item.goal.toLocaleString()}
              {' '}{item.unit}
            </div>
          </div>
        );
      })}
    </div>
  );
}
