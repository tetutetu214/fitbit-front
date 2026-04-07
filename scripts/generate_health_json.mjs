/**
 * data/daily/*.json → public/data/health.json 変換スクリプト
 * dashboard_html.py の extract_metrics と同等のロジック
 *
 * Usage: node scripts/generate_health_json.mjs
 */
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');

const DATA_DIR = process.env.DATA_DIR || resolve(PROJECT_ROOT, 'data');
const DAILY_DIR = resolve(DATA_DIR, 'daily');
const TANITA_DIR = resolve(DATA_DIR, 'daily_tanita');
const OUTPUT_DIR = resolve(PROJECT_ROOT, 'public', 'data');

function loadTanitaByDate() {
  const byDate = {};
  if (!existsSync(TANITA_DIR)) return byDate;
  const files = readdirSync(TANITA_DIR).filter(f => f.endsWith('.json'));
  for (const f of files) {
    const dateStr = f.replace('.json', '');
    try {
      const json = JSON.parse(readFileSync(resolve(TANITA_DIR, f), 'utf-8'));
      const measurements = json.measurements ?? {};
      const timestamps = Object.keys(measurements).sort();
      let weight = null;
      let bodyFat = null;
      for (const ts of timestamps) {
        const m = measurements[ts];
        if (typeof m.weight === 'number') weight = m.weight;
        if (typeof m.body_fat === 'number') bodyFat = m.body_fat;
      }
      byDate[dateStr] = { weight, body_fat: bodyFat };
    } catch {
      // ignore
    }
  }
  return byDate;
}

function loadDailyData() {
  if (!existsSync(DAILY_DIR)) {
    console.error(`Error: ${DAILY_DIR} not found. Run fetch_data.py first.`);
    process.exit(1);
  }
  const files = readdirSync(DAILY_DIR)
    .filter(f => f.endsWith('.json'))
    .sort();

  if (files.length === 0) {
    console.error(`Error: No JSON files in ${DAILY_DIR}`);
    process.exit(1);
  }

  const data = {};
  for (const f of files) {
    const dateStr = f.replace('.json', '');
    data[dateStr] = JSON.parse(readFileSync(resolve(DAILY_DIR, f), 'utf-8'));
  }
  return data;
}

function extractMetrics(data) {
  const metrics = {
    dates: [], resting_hr: [], steps: [], active_calories: [],
    sleep_minutes: [], sleep_efficiency: [],
    deep: [], light: [], rem: [], wake: [],
    hrv_rmssd: [], spo2_avg: [], spo2_min: [], spo2_max: [],
    sedentary_minutes: [],
    recovery_scores: [],
    sleep_timelines: [],
    hr_zones: [],
    goals: [],
    weight: [],
    body_fat: [],
  };

  const tanitaByDate = loadTanitaByDate();

  for (const [dateStr, day] of Object.entries(data)) {
    metrics.dates.push(dateStr);

    const hrData = day.heartrate?.['activities-heart'] ?? [{}];
    const hrValue = hrData[0]?.value ?? {};
    const rhr = hrValue.restingHeartRate ?? null;
    metrics.resting_hr.push(rhr);

    const zones = hrValue.heartRateZones ?? [];
    metrics.hr_zones.push(zones.length > 0 ? zones : null);

    const summary = day.activity?.summary ?? {};
    metrics.steps.push(summary.steps ?? 0);
    metrics.active_calories.push(summary.activityCalories ?? 0);
    metrics.sedentary_minutes.push(summary.sedentaryMinutes ?? null);
    metrics.goals.push(day.activity?.goals ?? null);

    const sleepSummary = day.sleep?.summary ?? {};
    const sleepMin = sleepSummary.totalMinutesAsleep ?? 0;
    metrics.sleep_minutes.push(sleepMin);

    const sleepRecords = day.sleep?.sleep ?? [];
    const mainSleep = sleepRecords.find(s => s.isMainSleep) ?? null;
    const eff = mainSleep?.efficiency ?? null;
    metrics.sleep_efficiency.push(eff);

    const stages = sleepSummary.stages ?? {};
    metrics.deep.push(stages.deep ?? 0);
    metrics.light.push(stages.light ?? 0);
    metrics.rem.push(stages.rem ?? 0);
    metrics.wake.push(stages.wake ?? 0);

    if (mainSleep?.levels) {
      metrics.sleep_timelines.push({
        data: mainSleep.levels.data ?? [],
        shortData: mainSleep.levels.shortData ?? [],
      });
    } else {
      metrics.sleep_timelines.push(null);
    }

    const hrvList = day.hrv?.hrv ?? [];
    const hrvVal = hrvList[0]?.value?.dailyRmssd ?? null;
    metrics.hrv_rmssd.push(hrvVal);

    const spo2Data = day.spo2 ?? {};
    const spo2Val = typeof spo2Data.value === 'object' ? spo2Data.value : null;
    metrics.spo2_avg.push(spo2Val?.avg ?? null);
    metrics.spo2_min.push(spo2Val?.min ?? null);
    metrics.spo2_max.push(spo2Val?.max ?? null);

    if (hrvVal != null && rhr != null && eff != null && sleepMin > 0) {
      const hrvS = Math.max(0, Math.min(100, (hrvVal - 10) / 70 * 100));
      const rhrS = Math.max(0, Math.min(100, (90 - rhr) / 40 * 100));
      const effS = Math.min(100, eff);
      let timeS;
      if (sleepMin >= 420 && sleepMin <= 540) {
        timeS = 100;
      } else if (sleepMin < 420) {
        timeS = Math.max(0, sleepMin / 420 * 100);
      } else {
        timeS = Math.max(0, 100 - (sleepMin - 540) / 120 * 50);
      }
      const score = Math.round((hrvS * 0.35 + rhrS * 0.25 + effS * 0.25 + timeS * 0.15) * 10) / 10;
      metrics.recovery_scores.push(score);
    } else {
      metrics.recovery_scores.push(null);
    }

    const tanita = tanitaByDate[dateStr];
    metrics.weight.push(tanita?.weight ?? null);
    metrics.body_fat.push(tanita?.body_fat ?? null);
  }

  return metrics;
}

const data = loadDailyData();
console.log(`Loaded ${Object.keys(data).length} days of data`);

const metrics = extractMetrics(data);

mkdirSync(OUTPUT_DIR, { recursive: true });
const outputPath = resolve(OUTPUT_DIR, 'health.json');
writeFileSync(outputPath, JSON.stringify(metrics, null, 2));
console.log(`Generated: ${outputPath}`);
