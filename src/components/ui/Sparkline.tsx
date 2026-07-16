import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, ReferenceArea } from 'recharts';
import { useReducedMotion } from '../../lib/useReducedMotion';

interface SparklinePoint {
  date: string;
  value: number | null;
}

interface SparklineProps {
  points: SparklinePoint[];
  color: string;
  /** 正常範囲帯 [下限, 上限]。表示ドメイン外は自動クリップ */
  band?: [number, number];
  ariaLabel: string;
}

/**
 * MetricCard 内に埋め込む軸・グリッドなしのスパークライン（Tufte データワード）。
 */
export function Sparkline({ points, color, band, ariaLabel }: SparklineProps) {
  const reduced = useReducedMotion();
  const valid = points.filter((p) => p.value !== null);
  if (valid.length < 2) return null;

  return (
    <div className="mx-auto h-12 w-full max-w-[150px]" role="img" aria-label={ariaLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
          <XAxis dataKey="date" hide />
          <YAxis hide domain={['auto', 'auto']} />
          {band && (
            <ReferenceArea
              y1={band[0]}
              y2={band[1]}
              fill="rgba(125, 133, 144, 0.14)"
              strokeWidth={0}
              ifOverflow="hidden"
            />
          )}
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
            connectNulls
            isAnimationActive={!reduced}
            animationDuration={800}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
