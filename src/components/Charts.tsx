import {
  ResponsiveContainer,
  LineChart, Line,
  BarChart, Bar,
  AreaChart, Area,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ReferenceLine, ReferenceArea,
  LabelList,
} from 'recharts';
import type { HealthData } from '../types/health';

/* ── shared ── */

interface ChartsProps {
  data: HealthData;
}

const GRID_COLOR = '#21262d';
const TEXT_COLOR = '#7d8590';
const LABEL_COLOR = '#e6edf3';

function CustomTooltip({ active, payload, formatter }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string; payload: Record<string, unknown> }>;
  formatter: (p: { value: number; name: string; color: string; payload: Record<string, unknown> }) => string;
}) {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="rounded-md border border-border bg-card2 px-2.5 py-1.5 text-xs text-text">
      {formatter(item)}
    </div>
  );
}

function shortDate(d: string) {
  const m = d.match(/(\d+)-(\d+)$/);
  return m ? `${parseInt(m[1])}/${parseInt(m[2])}` : d;
}

function validItems<T>(dates: string[], arr: (T | null)[]): [string[], T[]] {
  const d: string[] = [];
  const v: T[] = [];
  dates.forEach((dt, i) => {
    const val = arr[i];
    if (val !== null && val !== 0) {
      d.push(dt);
      v.push(val as T);
    }
  });
  return [d, v];
}

/* ── 安静時心拍数 ── */

export function RestingHRChart({ data }: ChartsProps) {
  const [hrd, hrv] = validItems(data.dates, data.resting_hr);
  const chartData = hrd.map((d, i) => ({ date: d, hr: hrv[i] }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={chartData} margin={{ top: 20, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} unit=" bpm" width={52} />
        <Tooltip content={<CustomTooltip formatter={(p) => `安静時心拍数: ${p.value} bpm`} />} />
        <Line type="monotone" dataKey="hr" stroke="#ff6b6b" strokeWidth={3} dot={{ r: 4, fill: '#ff6b6b' }} activeDot={{ r: 6 }}>
          <LabelList dataKey="hr" position="top" fill="#ff6b6b" fontSize={11} />
        </Line>
      </LineChart>
    </ResponsiveContainer>
  );
}

/* ── 歩数 ── */

export function StepsChart({ data }: ChartsProps) {
  const chartData = data.dates.map((d, i) => ({
    date: d,
    steps: data.steps[i],
    fill: data.steps[i] >= 10000 ? '#00d68f' : '#4ecdc4',
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 24, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} width={48} />
        <Tooltip content={<CustomTooltip formatter={(p) => `歩数: ${Number(p.value).toLocaleString()}`} />} />
        <ReferenceLine y={10000} stroke="#ff6b6b" strokeDasharray="6 4" strokeWidth={1} label={{ value: '目標', fill: '#ff6b6b', fontSize: 10, position: 'right' }} />
        <Bar dataKey="steps" radius={[3, 3, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
          <LabelList dataKey="steps" position="top" fill={LABEL_COLOR} fontSize={10} formatter={(v) => Number(v) > 0 ? Number(v).toLocaleString() : ''} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── 睡眠ステージ ── */

const SLEEP_STAGES = [
  { key: 'deep', name: '深い眠り', color: '#1a237e' },
  { key: 'light', name: '浅い眠り', color: '#5c6bc0' },
  { key: 'rem', name: 'レム睡眠', color: '#26a69a' },
  { key: 'wake', name: '覚醒', color: '#ef5350' },
] as const;

export function SleepStagesChart({ data }: ChartsProps) {
  const chartData = data.dates.map((d, i) => ({
    date: d,
    deep: data.deep[i],
    light: data.light[i],
    rem: data.rem[i],
    wake: data.wake[i],
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} unit=" 分" width={48} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            return (
              <div className="rounded-md border border-border bg-card2 px-2.5 py-1.5 text-xs text-text">
                {payload.map((p, i) => (
                  <div key={i} style={{ color: p.color }}>{p.name}: {p.value as number}分</div>
                ))}
              </div>
            );
          }}
        />
        <Legend
          verticalAlign="top"
          wrapperStyle={{ fontSize: 10, color: TEXT_COLOR, paddingBottom: 8 }}
        />
        {SLEEP_STAGES.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} stackId="sleep" fill={s.color} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── HRV ── */

export function HRVChart({ data }: ChartsProps) {
  const [hrvd, hrvv] = validItems(data.dates, data.hrv_rmssd);
  const chartData = hrvd.map((d, i) => ({ date: d, hrv: hrvv[i] }));
  const yMax = Math.max(...hrvv, 60);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 20, right: 40, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} unit=" ms" width={52} domain={[0, yMax]} />
        <Tooltip content={<CustomTooltip formatter={(p) => `RMSSD: ${Number(p.value).toFixed(1)} ms`} />} />
        <ReferenceArea y1={50} y2={yMax} fill="rgba(0,214,143,0.06)" ifOverflow="hidden" />
        <ReferenceArea y1={20} y2={50} fill="rgba(255,179,71,0.06)" ifOverflow="hidden" />
        <ReferenceArea y1={0} y2={20} fill="rgba(255,107,107,0.06)" ifOverflow="hidden" />
        <Area type="monotone" dataKey="hrv" stroke="#00d68f" strokeWidth={3} fill="rgba(0,214,143,0.08)" dot={{ r: 4, fill: '#00d68f' }} activeDot={{ r: 6 }}>
          <LabelList dataKey="hrv" position="top" fill="#00d68f" fontSize={11} formatter={(v) => Number(v).toFixed(1)} />
        </Area>
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ── 回復スコア ── */

export function RecoveryChart({ data }: ChartsProps) {
  const chartData: Array<{ date: string; score: number; fill: string }> = [];
  data.dates.forEach((d, i) => {
    const s = data.recovery_scores[i];
    if (s !== null) {
      chartData.push({
        date: d,
        score: s,
        fill: s >= 67 ? '#00d68f' : s >= 34 ? '#ffb347' : '#ff6b6b',
      });
    }
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 24, right: 40, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} unit=" " width={36} domain={[0, 105]} />
        <Tooltip content={<CustomTooltip formatter={(p) => `回復スコア: ${Number(p.value).toFixed(1)}/100`} />} />
        <ReferenceArea y1={67} y2={100} fill="rgba(0,214,143,0.05)" ifOverflow="hidden" />
        <ReferenceArea y1={34} y2={67} fill="rgba(255,179,71,0.05)" ifOverflow="hidden" />
        <ReferenceArea y1={0} y2={34} fill="rgba(255,107,107,0.05)" ifOverflow="hidden" />
        <Bar dataKey="score" radius={[3, 3, 0, 0]}>
          {chartData.map((entry, i) => (
            <Cell key={i} fill={entry.fill} />
          ))}
          <LabelList dataKey="score" position="top" fill={LABEL_COLOR} fontSize={13} formatter={(v) => Math.round(Number(v))} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── SpO2 ── */

export function SpO2Chart({ data }: ChartsProps) {
  const [sd, sa] = validItems(data.dates, data.spo2_avg);
  const chartData = sd.map((d, i) => {
    const origIdx = data.dates.indexOf(d);
    return {
      date: d,
      avg: sa[i],
      min: data.spo2_min[origIdx],
      max: data.spo2_max[origIdx],
    };
  });

  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={chartData} margin={{ top: 20, right: 40, bottom: 4, left: 0 }}>
        <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: TEXT_COLOR, fontSize: 11 }} axisLine={false} tickLine={false} unit="%" width={44} domain={[88, 101]} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as { avg: number; min: number | null; max: number | null };
            return (
              <div className="rounded-md border border-border bg-card2 px-2.5 py-1.5 text-xs text-text">
                <div>平均: {d.avg.toFixed(1)}%</div>
                {d.min != null && <div>最低: {d.min.toFixed(1)}%</div>}
                {d.max != null && <div>最高: {d.max.toFixed(1)}%</div>}
              </div>
            );
          }}
        />
        <ReferenceArea y1={95} y2={101} fill="rgba(0,214,143,0.05)" ifOverflow="hidden" />
        <ReferenceArea y1={90} y2={95} fill="rgba(255,179,71,0.05)" ifOverflow="hidden" />
        <ReferenceArea y1={85} y2={90} fill="rgba(255,107,107,0.05)" ifOverflow="hidden" />
        <Area type="monotone" dataKey="max" stroke="none" fill="rgba(0,188,212,0.12)" activeDot={false} />
        <Area type="monotone" dataKey="min" stroke="none" fill="#161b22" activeDot={false} />
        <Area type="monotone" dataKey="avg" stroke="#00bcd4" strokeWidth={3} fill="none" dot={{ r: 4, fill: '#00bcd4' }} activeDot={{ r: 6 }}>
          <LabelList dataKey="avg" position="top" fill="#00bcd4" fontSize={11} formatter={(v) => `${Number(v).toFixed(1)}%`} />
        </Area>
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ── 心拍ゾーン ドーナツ ── */

const ZONE_NAME_MAP: Record<string, string> = {
  'Fat Burn': '脂肪燃焼帯', Cardio: '有酸素帯', Peak: '最大強度帯', 'Out of Range': '安静帯',
};
const ZONE_COLORS: Record<string, string> = {
  'Fat Burn': '#ffb347', Cardio: '#ff6b6b', Peak: '#e040fb', 'Out of Range': '#2a2d3a',
};

export function HRZoneDonut({ data }: ChartsProps) {
  const last = data.dates.length - 1;
  const zones = data.hr_zones[last] || [];
  const rhr = data.resting_hr[last];

  if (zones.length === 0 && !rhr) return null;

  const pieData = zones.map(z => ({
    name: ZONE_NAME_MAP[z.name] || z.name,
    value: z.minutes,
    calories: Math.round(z.caloriesOut),
    color: ZONE_COLORS[z.name] || '#555',
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={pieData}
          cx="50%"
          cy="50%"
          innerRadius={55}
          outerRadius={80}
          dataKey="value"
          paddingAngle={1}
          label={({ name, value }) => value > 0 ? `${name} ${value}分` : ''}
          labelLine={{ stroke: TEXT_COLOR }}
        >
          {pieData.map((entry, i) => (
            <Cell key={i} fill={entry.color} />
          ))}
        </Pie>
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload as { name: string; value: number; calories: number };
            return (
              <div className="rounded-md border border-border bg-card2 px-2.5 py-1.5 text-xs text-text">
                <div>{d.name}</div>
                <div>{d.value}分 / {d.calories} kcal</div>
              </div>
            );
          }}
        />
        {rhr && (
          <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" fill="#ff6b6b" style={{ fontSize: 22, fontWeight: 700 }}>
            {rhr}
            <tspan dx={2} style={{ fontSize: 12, fontWeight: 400 }}>bpm</tspan>
          </text>
        )}
      </PieChart>
    </ResponsiveContainer>
  );
}
