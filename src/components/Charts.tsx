import type { HealthData } from '../types/health';
import { PlotlyChart } from './PlotlyChart';

/* eslint-disable @typescript-eslint/no-explicit-any */
// Plotly's TypeScript definitions are stricter than the actual runtime API.
// We use `as any` for mode and title fields that work at runtime but don't
// match the narrow union types in @types/plotly.js.

interface ChartsProps {
  data: HealthData;
}

/** 有効なデータだけを抽出するヘルパー */
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

export function RestingHRChart({ data }: ChartsProps) {
  const [hrd, hrv] = validItems(data.dates, data.resting_hr);
  return (
    <PlotlyChart
      data={[{
        x: hrd, y: hrv, type: 'scatter', mode: 'lines+markers+text' as any,
        text: hrv.map(String), textposition: 'top center',
        textfont: { size: 11, color: '#ff6b6b' },
        line: { color: '#ff6b6b', width: 3 }, marker: { size: 7 },
        hovertemplate: '%{x}<br>安静時心拍数: %{y} bpm<extra></extra>',
      }]}
      layout={{ yaxis: { gridcolor: '#21262d', title: { text: 'bpm' } } }}
    />
  );
}

export function StepsChart({ data }: ChartsProps) {
  return (
    <PlotlyChart
      data={[
        {
          x: data.dates, y: data.steps, type: 'bar',
          marker: { color: data.steps.map(s => s >= 10000 ? '#00d68f' : '#4ecdc4') },
          text: data.steps.map(s => s > 0 ? s.toLocaleString() : ''),
          textposition: 'outside', textfont: { size: 10, color: '#e6edf3' },
          hovertemplate: '%{x}<br>歩数: %{y:,}<extra></extra>',
        },
        {
          x: data.dates, y: data.dates.map(() => 10000),
          type: 'scatter', mode: 'lines',
          line: { color: '#ff6b6b', dash: 'dash', width: 1 },
          hoverinfo: 'skip', name: '目標',
        },
      ]}
    />
  );
}

export function SleepStagesChart({ data }: ChartsProps) {
  return (
    <PlotlyChart
      data={[
        { x: data.dates, y: data.deep, type: 'bar', name: '深い眠り', marker: { color: '#1a237e' }, hovertemplate: '深い眠り: %{y}分<extra></extra>' },
        { x: data.dates, y: data.light, type: 'bar', name: '浅い眠り', marker: { color: '#5c6bc0' }, hovertemplate: '浅い眠り: %{y}分<extra></extra>' },
        { x: data.dates, y: data.rem, type: 'bar', name: 'レム睡眠', marker: { color: '#26a69a' }, hovertemplate: 'レム睡眠: %{y}分<extra></extra>' },
        { x: data.dates, y: data.wake, type: 'bar', name: '覚醒', marker: { color: '#ef5350' }, hovertemplate: '覚醒: %{y}分<extra></extra>' },
      ]}
      layout={{
        barmode: 'stack',
        showlegend: true,
        legend: { orientation: 'h', y: 1.15, font: { size: 10 } },
        yaxis: { gridcolor: '#21262d', title: { text: '分' } },
      }}
    />
  );
}

export function HRVChart({ data }: ChartsProps) {
  const [hrvd, hrvv] = validItems(data.dates, data.hrv_rmssd);
  return (
    <PlotlyChart
      data={[{
        x: hrvd, y: hrvv, type: 'scatter', mode: 'lines+markers+text' as any,
        text: hrvv.map(v => v.toFixed(1)), textposition: 'top center',
        textfont: { size: 11, color: '#00d68f' },
        line: { color: '#00d68f', width: 3 }, marker: { size: 7 },
        fill: 'tozeroy', fillcolor: 'rgba(0,214,143,0.08)',
        hovertemplate: '%{x}<br>RMSSD: %{y:.1f} ms<extra></extra>',
      }]}
      layout={{
        yaxis: { gridcolor: '#21262d', title: { text: 'RMSSD (ms)' } },
        shapes: [
          { type: 'rect', x0: hrvd[0] || 0, x1: hrvd[hrvd.length - 1] || 1, y0: 50, y1: 100, fillcolor: 'rgba(0,214,143,0.06)', line: { width: 0 } },
          { type: 'rect', x0: hrvd[0] || 0, x1: hrvd[hrvd.length - 1] || 1, y0: 20, y1: 50, fillcolor: 'rgba(255,179,71,0.06)', line: { width: 0 } },
          { type: 'rect', x0: hrvd[0] || 0, x1: hrvd[hrvd.length - 1] || 1, y0: 0, y1: 20, fillcolor: 'rgba(255,107,107,0.06)', line: { width: 0 } },
        ],
        annotations: [
          { x: 1, y: 75, xref: 'paper', text: '良好', showarrow: false, font: { size: 9, color: '#00d68f' } },
          { x: 1, y: 35, xref: 'paper', text: '普通', showarrow: false, font: { size: 9, color: '#ffb347' } },
          { x: 1, y: 10, xref: 'paper', text: '低い', showarrow: false, font: { size: 9, color: '#ff6b6b' } },
        ],
      }}
    />
  );
}

export function RecoveryChart({ data }: ChartsProps) {
  const rd: string[] = [];
  const rv: number[] = [];
  const rc: string[] = [];
  data.dates.forEach((d, i) => {
    const s = data.recovery_scores[i];
    if (s !== null) {
      rd.push(d);
      rv.push(s);
      rc.push(s >= 67 ? '#00d68f' : s >= 34 ? '#ffb347' : '#ff6b6b');
    }
  });

  return (
    <PlotlyChart
      data={[{
        x: rd, y: rv, type: 'bar',
        marker: { color: rc },
        text: rv.map(v => String(Math.round(v))),
        textposition: 'outside', textfont: { size: 13, color: '#e6edf3' },
        hovertemplate: '%{x}<br>回復スコア: %{y:.1f}/100<extra></extra>',
      }]}
      layout={{
        yaxis: { gridcolor: '#21262d', title: { text: 'スコア' }, range: [0, 105] },
        shapes: [
          { type: 'rect', x0: -0.5, x1: rd.length, y0: 67, y1: 100, fillcolor: 'rgba(0,214,143,0.05)', line: { width: 0 } },
          { type: 'rect', x0: -0.5, x1: rd.length, y0: 34, y1: 67, fillcolor: 'rgba(255,179,71,0.05)', line: { width: 0 } },
          { type: 'rect', x0: -0.5, x1: rd.length, y0: 0, y1: 34, fillcolor: 'rgba(255,107,107,0.05)', line: { width: 0 } },
        ],
        annotations: [
          { x: 1, y: 83, xref: 'paper', text: '良好', showarrow: false, font: { size: 9, color: '#00d68f' } },
          { x: 1, y: 50, xref: 'paper', text: '普通', showarrow: false, font: { size: 9, color: '#ffb347' } },
          { x: 1, y: 17, xref: 'paper', text: '低い', showarrow: false, font: { size: 9, color: '#ff6b6b' } },
        ],
      }}
    />
  );
}

export function SpO2Chart({ data }: ChartsProps) {
  const [sd, sa] = validItems(data.dates, data.spo2_avg);
  const smin = sd.map((_, i) => data.spo2_min[data.dates.indexOf(sd[i])]);
  const smax = sd.map((_, i) => data.spo2_max[data.dates.indexOf(sd[i])]);

  return (
    <PlotlyChart
      data={[
        { x: sd, y: smax, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false, hoverinfo: 'skip' },
        {
          x: sd, y: smin, type: 'scatter', mode: 'lines', line: { width: 0 },
          fill: 'tonexty', fillcolor: 'rgba(0,188,212,0.12)', showlegend: false, hoverinfo: 'skip',
        },
        {
          x: sd, y: sa, type: 'scatter', mode: 'lines+markers+text' as any,
          text: sa.map(v => v.toFixed(1) + '%'), textposition: 'top center',
          textfont: { size: 11, color: '#00bcd4' },
          line: { color: '#00bcd4', width: 3 }, marker: { size: 7 },
          hovertemplate: '%{x}<br>平均: %{y:.1f}%<extra></extra>',
        },
      ]}
      layout={{
        yaxis: { gridcolor: '#21262d', title: { text: '%' }, range: [88, 101] },
        shapes: [
          { type: 'rect', x0: sd[0] || 0, x1: sd[sd.length - 1] || 1, y0: 95, y1: 101, fillcolor: 'rgba(0,214,143,0.05)', line: { width: 0 } },
          { type: 'rect', x0: sd[0] || 0, x1: sd[sd.length - 1] || 1, y0: 90, y1: 95, fillcolor: 'rgba(255,179,71,0.05)', line: { width: 0 } },
          { type: 'rect', x0: sd[0] || 0, x1: sd[sd.length - 1] || 1, y0: 85, y1: 90, fillcolor: 'rgba(255,107,107,0.05)', line: { width: 0 } },
        ],
        annotations: [
          { x: 1, y: 98, xref: 'paper', text: '正常', showarrow: false, font: { size: 9, color: '#00d68f' } },
          { x: 1, y: 92, xref: 'paper', text: '要注意', showarrow: false, font: { size: 9, color: '#ffb347' } },
        ],
      }}
    />
  );
}

export function HRZoneDonut({ data }: ChartsProps) {
  const last = data.dates.length - 1;
  const zones = data.hr_zones[last] || [];
  const rhr = data.resting_hr[last];

  if (zones.length === 0 && !rhr) return null;

  const zoneNameMap: Record<string, string> = {
    'Fat Burn': '脂肪燃焼帯', Cardio: '有酸素帯', Peak: '最大強度帯', 'Out of Range': '安静帯',
  };
  const zoneColors: Record<string, string> = {
    'Fat Burn': '#ffb347', Cardio: '#ff6b6b', Peak: '#e040fb', 'Out of Range': '#2a2d3a',
  };

  return (
    <PlotlyChart
      data={[{
        values: zones.map(z => z.minutes),
        labels: zones.map(z => zoneNameMap[z.name] || z.name),
        type: 'pie', hole: 0.65,
        marker: { colors: zones.map(z => zoneColors[z.name] || '#555') },
        textinfo: 'label+text',
        text: zones.map(z => z.minutes > 0 ? `${z.minutes}分` : ''),
        textposition: 'outside',
        textfont: { size: 11, color: '#e6edf3' },
        hovertemplate: '%{label}<br>%{value}分<br>%{customdata} kcal<extra></extra>',
        customdata: zones.map(z => Math.round(z.caloriesOut)),
        sort: false,
      }]}
      layout={{
        margin: { t: 10, r: 10, b: 10, l: 10 },
        annotations: rhr
          ? [{ text: `<b>${rhr}</b><br>bpm`, x: 0.5, y: 0.5, font: { size: 22, color: '#ff6b6b' }, showarrow: false }]
          : [],
      }}
    />
  );
}
