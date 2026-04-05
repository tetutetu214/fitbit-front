"""Fitbitヘルスデータのインタラクティブ HTML ダッシュボード生成"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
DAILY_DIR = DATA_DIR / "daily"
OUTPUT_DIR = DATA_DIR / "charts"


def load_daily_data() -> dict:
    data = {}
    if not DAILY_DIR.exists():
        print(f"Error: {DAILY_DIR} not found. Run fetch_data.py first.")
        sys.exit(1)
    for f in sorted(DAILY_DIR.glob("*.json")):
        with open(f) as fp:
            data[f.stem] = json.load(fp)
    return data


def extract_metrics(data: dict) -> dict:
    metrics = {
        "dates": [], "resting_hr": [], "steps": [], "active_calories": [],
        "sleep_minutes": [], "sleep_efficiency": [],
        "deep": [], "light": [], "rem": [], "wake": [],
        "hrv_rmssd": [], "spo2_avg": [], "spo2_min": [], "spo2_max": [],
        "recovery_scores": [],
    }
    for date_str, day in data.items():
        metrics["dates"].append(date_str)

        hr_data = day.get("heartrate", {}).get("activities-heart", [{}])
        rhr = hr_data[0].get("value", {}).get("restingHeartRate") if hr_data else None
        metrics["resting_hr"].append(rhr)

        summary = day.get("activity", {}).get("summary", {})
        metrics["steps"].append(summary.get("steps", 0))
        metrics["active_calories"].append(summary.get("activityCalories", 0))

        sleep_summary = day.get("sleep", {}).get("summary", {})
        sleep_min = sleep_summary.get("totalMinutesAsleep", 0)
        metrics["sleep_minutes"].append(sleep_min)
        sleep_records = day.get("sleep", {}).get("sleep", [])
        main_sleep = next((s for s in sleep_records if s.get("isMainSleep")), None)
        eff = main_sleep.get("efficiency") if main_sleep else None
        metrics["sleep_efficiency"].append(eff)
        stages = sleep_summary.get("stages", {})
        metrics["deep"].append(stages.get("deep", 0))
        metrics["light"].append(stages.get("light", 0))
        metrics["rem"].append(stages.get("rem", 0))
        metrics["wake"].append(stages.get("wake", 0))

        hrv_list = day.get("hrv", {}).get("hrv", [])
        hrv_val = hrv_list[0]["value"]["dailyRmssd"] if hrv_list else None
        metrics["hrv_rmssd"].append(hrv_val)

        spo2_data = day.get("spo2", {})
        spo2_val = spo2_data.get("value") if isinstance(spo2_data.get("value"), dict) else None
        metrics["spo2_avg"].append(spo2_val.get("avg") if spo2_val else None)
        metrics["spo2_min"].append(spo2_val.get("min") if spo2_val else None)
        metrics["spo2_max"].append(spo2_val.get("max") if spo2_val else None)

        # Recovery Score
        if hrv_val and rhr and eff and sleep_min > 0:
            hrv_s = max(0, min(100, (hrv_val - 10) / 70 * 100))
            rhr_s = max(0, min(100, (90 - rhr) / 40 * 100))
            eff_s = min(100, eff)
            if 420 <= sleep_min <= 540:
                time_s = 100
            elif sleep_min < 420:
                time_s = max(0, sleep_min / 420 * 100)
            else:
                time_s = max(0, 100 - (sleep_min - 540) / 120 * 50)
            score = round(hrv_s * 0.35 + rhr_s * 0.25 + eff_s * 0.25 + time_s * 0.15, 1)
            metrics["recovery_scores"].append(score)
        else:
            metrics["recovery_scores"].append(None)

    return metrics


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fitbit Health Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  :root {
    --bg: #0f1117;
    --card: #1a1d29;
    --text: #e4e6eb;
    --text2: #8b8fa3;
    --green: #00d68f;
    --red: #ff6b6b;
    --blue: #4ecdc4;
    --purple: #a78bfa;
    --orange: #ffb347;
    --cyan: #00bcd4;
    --border: #2a2d3a;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  .header {
    padding: 24px 32px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header h1 {
    font-size: 24px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--blue), var(--purple));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header .date { color: var(--text2); font-size: 14px; }

  .summary-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    padding: 24px 32px;
  }
  .card {
    background: var(--card);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border);
    transition: transform 0.2s;
  }
  .card:hover { transform: translateY(-2px); }
  .card .label { font-size: 12px; color: var(--text2); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
  .card .value { font-size: 28px; font-weight: 700; }
  .card .unit { font-size: 14px; color: var(--text2); margin-left: 4px; }
  .card .sub { font-size: 12px; color: var(--text2); margin-top: 4px; }

  .score-card .value {
    font-size: 36px;
  }
  .score-good { color: var(--green); }
  .score-moderate { color: var(--orange); }
  .score-poor { color: var(--red); }

  .charts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
    gap: 16px;
    padding: 0 32px 32px;
  }
  .chart-card {
    background: var(--card);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border);
  }
  .chart-card h3 {
    font-size: 14px;
    color: var(--text2);
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  @media (max-width: 768px) {
    .charts { grid-template-columns: 1fr; }
    .summary-cards { grid-template-columns: repeat(2, 1fr); }
    .header { padding: 16px; }
    .charts { padding: 0 16px 16px; }
    .summary-cards { padding: 16px; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>Fitbit Health Dashboard</h1>
  <div class="date" id="lastUpdate"></div>
</div>

<div class="summary-cards" id="summaryCards"></div>

<div class="charts">
  <div class="chart-card"><h3>Resting Heart Rate</h3><div id="chartHR"></div></div>
  <div class="chart-card"><h3>Daily Steps</h3><div id="chartSteps"></div></div>
  <div class="chart-card"><h3>Sleep Stages</h3><div id="chartSleep"></div></div>
  <div class="chart-card"><h3>HRV (Heart Rate Variability)</h3><div id="chartHRV"></div></div>
  <div class="chart-card"><h3>Recovery Score</h3><div id="chartRecovery"></div></div>
  <div class="chart-card"><h3>SpO2 (Blood Oxygen)</h3><div id="chartSpO2"></div></div>
</div>

<script>
const DATA = __DATA_JSON__;

const plotlyLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { color: '#8b8fa3', family: '-apple-system, sans-serif' },
  margin: { t: 10, r: 20, b: 40, l: 50 },
  xaxis: { gridcolor: '#2a2d3a', tickangle: -45 },
  yaxis: { gridcolor: '#2a2d3a' },
  hovermode: 'x unified',
  showlegend: false,
};

const plotlyConfig = { responsive: true, displayModeBar: false };

// ---- Summary Cards ----
function renderSummary() {
  const latest = DATA.dates.length - 1;
  if (latest < 0) return;

  document.getElementById('lastUpdate').textContent =
    'Last updated: ' + DATA.dates[latest];

  const cards = [
    {
      label: 'Recovery Score',
      value: DATA.recovery_scores[latest],
      unit: '/ 100',
      cls: 'score-card',
      format: v => {
        const el = document.createElement('span');
        el.textContent = v !== null ? Math.round(v) : 'N/A';
        if (v >= 67) el.className = 'score-good';
        else if (v >= 34) el.className = 'score-moderate';
        else el.className = 'score-poor';
        return el;
      },
      sub: v => v >= 67 ? 'Good' : v >= 34 ? 'Moderate' : v !== null ? 'Poor' : ''
    },
    {
      label: 'Resting HR',
      value: DATA.resting_hr[latest],
      unit: 'bpm',
      color: '#ff6b6b',
      sub: () => 'Normal: 60-100'
    },
    {
      label: 'Steps',
      value: DATA.steps[latest],
      unit: '',
      color: DATA.steps[latest] >= 10000 ? '#00d68f' : '#4ecdc4',
      format: v => v !== null ? v.toLocaleString() : 'N/A',
      sub: v => v >= 10000 ? 'Goal reached!' : 'Goal: 10,000'
    },
    {
      label: 'Sleep',
      value: DATA.sleep_minutes[latest],
      unit: '',
      color: '#a78bfa',
      format: v => v > 0 ? Math.floor(v/60) + 'h ' + (v%60) + 'm' : 'N/A',
      sub: () => DATA.sleep_efficiency[latest] ? 'Efficiency: ' + DATA.sleep_efficiency[latest] + '%' : ''
    },
    {
      label: 'HRV',
      value: DATA.hrv_rmssd[latest],
      unit: 'ms',
      color: '#00d68f',
      format: v => v !== null ? v.toFixed(1) : 'N/A',
      sub: () => 'Higher is better'
    },
    {
      label: 'SpO2',
      value: DATA.spo2_avg[latest],
      unit: '%',
      color: '#00bcd4',
      format: v => v !== null ? v.toFixed(1) : 'N/A',
      sub: () => 'Normal: 95-100%'
    },
  ];

  const container = document.getElementById('summaryCards');
  cards.forEach(c => {
    const div = document.createElement('div');
    div.className = 'card ' + (c.cls || '');

    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = c.label;

    const valueDiv = document.createElement('div');
    valueDiv.className = 'value';
    if (c.color) valueDiv.style.color = c.color;

    if (c.format && typeof c.format === 'function' && c.cls === 'score-card') {
      valueDiv.appendChild(c.format(c.value));
    } else {
      const formatted = c.format ? c.format(c.value) : (c.value !== null ? c.value : 'N/A');
      valueDiv.textContent = formatted;
      if (c.unit && c.value !== null) {
        const unitSpan = document.createElement('span');
        unitSpan.className = 'unit';
        unitSpan.textContent = c.unit;
        valueDiv.appendChild(unitSpan);
      }
    }

    const sub = document.createElement('div');
    sub.className = 'sub';
    sub.textContent = typeof c.sub === 'function' ? c.sub(c.value) : (c.sub || '');

    div.appendChild(label);
    div.appendChild(valueDiv);
    div.appendChild(sub);
    container.appendChild(div);
  });
}

// ---- Charts ----
function renderCharts() {
  const dates = DATA.dates;

  // HR
  const hrDates = [], hrVals = [];
  dates.forEach((d, i) => {
    if (DATA.resting_hr[i] !== null) { hrDates.push(d); hrVals.push(DATA.resting_hr[i]); }
  });
  Plotly.newPlot('chartHR', [{
    x: hrDates, y: hrVals, type: 'scatter', mode: 'lines+markers+text',
    text: hrVals.map(String), textposition: 'top center', textfont: { size: 12, color: '#ff6b6b' },
    line: { color: '#ff6b6b', width: 3 }, marker: { size: 8, color: '#ff6b6b' },
    hovertemplate: '%{x}<br>RHR: %{y} bpm<extra></extra>'
  }], {...plotlyLayout, yaxis: {...plotlyLayout.yaxis, title: 'bpm'}}, plotlyConfig);

  // Steps
  const stepColors = DATA.steps.map(s => s >= 10000 ? '#00d68f' : '#4ecdc4');
  Plotly.newPlot('chartSteps', [{
    x: dates, y: DATA.steps, type: 'bar',
    marker: { color: stepColors, cornerradius: 4 },
    text: DATA.steps.map(s => s > 0 ? s.toLocaleString() : ''),
    textposition: 'outside', textfont: { size: 11, color: '#e4e6eb' },
    hovertemplate: '%{x}<br>Steps: %{y:,}<extra></extra>'
  }, {
    x: dates, y: dates.map(() => 10000), type: 'scatter', mode: 'lines',
    line: { color: '#ff6b6b', dash: 'dash', width: 1.5 }, name: 'Goal',
    hoverinfo: 'skip'
  }], {...plotlyLayout, showlegend: false}, plotlyConfig);

  // Sleep
  Plotly.newPlot('chartSleep', [
    { x: dates, y: DATA.deep, type: 'bar', name: 'Deep', marker: { color: '#1a237e', cornerradius: 2 },
      hovertemplate: 'Deep: %{y}m<extra></extra>' },
    { x: dates, y: DATA.light, type: 'bar', name: 'Light', marker: { color: '#5c6bc0', cornerradius: 2 },
      hovertemplate: 'Light: %{y}m<extra></extra>' },
    { x: dates, y: DATA.rem, type: 'bar', name: 'REM', marker: { color: '#26a69a', cornerradius: 2 },
      hovertemplate: 'REM: %{y}m<extra></extra>' },
    { x: dates, y: DATA.wake, type: 'bar', name: 'Wake', marker: { color: '#ef5350', cornerradius: 2 },
      hovertemplate: 'Wake: %{y}m<extra></extra>' },
  ], {
    ...plotlyLayout,
    barmode: 'stack',
    showlegend: true,
    legend: { orientation: 'h', y: 1.15, font: { size: 11 } },
    yaxis: {...plotlyLayout.yaxis, title: 'minutes'}
  }, plotlyConfig);

  // HRV
  const hrvDates = [], hrvVals = [];
  dates.forEach((d, i) => {
    if (DATA.hrv_rmssd[i] !== null) { hrvDates.push(d); hrvVals.push(DATA.hrv_rmssd[i]); }
  });
  Plotly.newPlot('chartHRV', [{
    x: hrvDates, y: hrvVals, type: 'scatter', mode: 'lines+markers+text',
    text: hrvVals.map(v => v.toFixed(1)), textposition: 'top center', textfont: { size: 12, color: '#00d68f' },
    line: { color: '#00d68f', width: 3 }, marker: { size: 8, color: '#00d68f' },
    fill: 'tozeroy', fillcolor: 'rgba(0,214,143,0.1)',
    hovertemplate: '%{x}<br>RMSSD: %{y:.1f} ms<extra></extra>'
  }], {...plotlyLayout, yaxis: {...plotlyLayout.yaxis, title: 'RMSSD (ms)'}}, plotlyConfig);

  // Recovery
  const recDates = [], recVals = [], recColors = [];
  dates.forEach((d, i) => {
    if (DATA.recovery_scores[i] !== null) {
      recDates.push(d); recVals.push(DATA.recovery_scores[i]);
      recColors.push(DATA.recovery_scores[i] >= 67 ? '#00d68f' : DATA.recovery_scores[i] >= 34 ? '#ffb347' : '#ff6b6b');
    }
  });
  Plotly.newPlot('chartRecovery', [{
    x: recDates, y: recVals, type: 'bar',
    marker: { color: recColors, cornerradius: 4 },
    text: recVals.map(v => Math.round(v)), textposition: 'outside',
    textfont: { size: 14, color: '#e4e6eb' },
    hovertemplate: '%{x}<br>Score: %{y:.1f}/100<extra></extra>'
  }], {
    ...plotlyLayout,
    yaxis: {...plotlyLayout.yaxis, title: 'Score', range: [0, 105]},
    shapes: [
      { type: 'rect', x0: -0.5, x1: recDates.length, y0: 67, y1: 100, fillcolor: 'rgba(0,214,143,0.05)', line: { width: 0 } },
      { type: 'rect', x0: -0.5, x1: recDates.length, y0: 34, y1: 67, fillcolor: 'rgba(255,179,71,0.05)', line: { width: 0 } },
      { type: 'rect', x0: -0.5, x1: recDates.length, y0: 0, y1: 34, fillcolor: 'rgba(255,107,107,0.05)', line: { width: 0 } },
    ]
  }, plotlyConfig);

  // SpO2
  const spo2Dates = [], spo2Avg = [], spo2Min = [], spo2Max = [];
  dates.forEach((d, i) => {
    if (DATA.spo2_avg[i] !== null) {
      spo2Dates.push(d); spo2Avg.push(DATA.spo2_avg[i]);
      spo2Min.push(DATA.spo2_min[i]); spo2Max.push(DATA.spo2_max[i]);
    }
  });
  Plotly.newPlot('chartSpO2', [
    { x: spo2Dates, y: spo2Max, type: 'scatter', mode: 'lines', line: { width: 0 }, showlegend: false, hoverinfo: 'skip' },
    { x: spo2Dates, y: spo2Min, type: 'scatter', mode: 'lines', line: { width: 0 },
      fill: 'tonexty', fillcolor: 'rgba(0,188,212,0.15)', showlegend: false, hoverinfo: 'skip' },
    { x: spo2Dates, y: spo2Avg, type: 'scatter', mode: 'lines+markers+text',
      text: spo2Avg.map(v => v.toFixed(1) + '%'), textposition: 'top center', textfont: { size: 12, color: '#00bcd4' },
      line: { color: '#00bcd4', width: 3 }, marker: { size: 8, color: '#00bcd4' },
      name: 'Avg', hovertemplate: '%{x}<br>Avg: %{y:.1f}%<extra></extra>' },
  ], {...plotlyLayout, yaxis: {...plotlyLayout.yaxis, title: '%', range: [90, 101]}}, plotlyConfig);
}

renderSummary();
renderCharts();
</script>
</body>
</html>"""


def main():
    data = load_daily_data()
    print(f"Loaded {len(data)} days of data")

    metrics = extract_metrics(data)

    # HTMLにデータを埋め込み
    metrics_json = json.dumps(metrics, ensure_ascii=False)
    html = HTML_TEMPLATE.replace("__DATA_JSON__", metrics_json)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "dashboard.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard saved: {output_path}")
    print(f"Open in browser: file://{output_path.resolve()}")


if __name__ == "__main__":
    main()
