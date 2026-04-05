import type { HealthData } from '../types/health';

interface SummaryCardsProps {
  data: HealthData;
}

export function SummaryCards({ data }: SummaryCardsProps) {
  const last = data.dates.length - 1;
  if (last < 0) return null;

  const score = data.recovery_scores[last];
  const sleepMin = data.sleep_minutes[last];

  const scoreClass =
    score !== null
      ? score >= 67
        ? 'score-good'
        : score >= 34
          ? 'score-mod'
          : 'score-poor'
      : '';

  const cards = [
    {
      label: '回復スコア',
      val: score !== null ? String(Math.round(score)) : '—',
      cls: scoreClass,
      sub: score !== null ? (score >= 67 ? '良好' : score >= 34 ? '普通' : '低い') : 'データ不足',
    },
    {
      label: '安静時心拍数',
      val: data.resting_hr[last] !== null ? String(data.resting_hr[last]) : '—',
      unit: 'bpm',
      color: '#ff6b6b',
      sub: '正常: 60〜100',
    },
    {
      label: '歩数',
      val: data.steps[last] > 0 ? data.steps[last].toLocaleString() : '—',
      color: data.steps[last] >= 10000 ? '#00d68f' : '#4ecdc4',
      sub: data.steps[last] >= 10000 ? '目標達成!' : '目標: 10,000',
    },
    {
      label: '睡眠',
      val:
        sleepMin > 0
          ? `${Math.floor(sleepMin / 60)}h ${sleepMin % 60}m`
          : '—',
      color: '#a78bfa',
      sub: data.sleep_efficiency[last] ? `効率: ${data.sleep_efficiency[last]}%` : '',
    },
    {
      label: 'HRV',
      val: data.hrv_rmssd[last] !== null ? data.hrv_rmssd[last]!.toFixed(1) : '—',
      unit: 'ms',
      color: '#00d68f',
      sub: '高いほど良好',
    },
    {
      label: '血中酸素',
      val: data.spo2_avg[last] !== null ? data.spo2_avg[last]!.toFixed(1) : '—',
      unit: '%',
      color: '#00bcd4',
      sub: '正常: 95〜100%',
    },
  ];

  return (
    <div className="summary">
      {cards.map((c) => (
        <div className="s-card" key={c.label}>
          <div className="label">{c.label}</div>
          <div className={`val ${c.cls ?? ''}`} style={{ color: c.color ?? undefined }}>
            {c.val}
            {c.unit && <span className="unit">{c.unit}</span>}
          </div>
          <div className="sub">{c.sub}</div>
        </div>
      ))}
    </div>
  );
}
