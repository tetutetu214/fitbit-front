import type { HealthData } from '../types/health';

/** サンプルデータ: 開発・プレビュー用 */
export const sampleData: HealthData = {
  dates: ['2026-03-30', '2026-03-31', '2026-04-01', '2026-04-02', '2026-04-03', '2026-04-04', '2026-04-05'],
  resting_hr: [62, 60, 63, 58, 61, 59, 60],
  steps: [8432, 12045, 6890, 11230, 9876, 7654, 10234],
  active_calories: [320, 480, 210, 450, 380, 290, 410],
  sleep_minutes: [420, 390, 450, 380, 410, 440, 400],
  sleep_efficiency: [92, 88, 95, 85, 91, 93, 90],
  deep: [80, 65, 90, 55, 75, 85, 70],
  light: [200, 190, 210, 185, 195, 210, 190],
  rem: [100, 95, 110, 90, 100, 105, 95],
  wake: [40, 40, 40, 50, 40, 40, 45],
  hrv_rmssd: [38.5, 42.1, 35.8, 48.2, 40.5, 44.8, 41.2],
  spo2_avg: [97.2, 96.8, 97.5, 96.5, 97.0, 97.3, 96.9],
  spo2_min: [95.0, 94.5, 95.2, 94.0, 95.1, 95.3, 94.8],
  spo2_max: [99.0, 98.5, 99.2, 98.0, 98.8, 99.1, 98.6],
  recovery_scores: [65, 72, 58, 78, 68, 75, 70],
  sleep_timelines: [
    null, null, null, null, null, null,
    {
      data: [
        { dateTime: '2026-04-04T23:15:00', level: 'light', seconds: 900 },
        { dateTime: '2026-04-04T23:30:00', level: 'deep', seconds: 3600 },
        { dateTime: '2026-04-05T00:30:00', level: 'light', seconds: 1800 },
        { dateTime: '2026-04-05T01:00:00', level: 'rem', seconds: 2700 },
        { dateTime: '2026-04-05T01:45:00', level: 'light', seconds: 1200 },
        { dateTime: '2026-04-05T02:05:00', level: 'deep', seconds: 3000 },
        { dateTime: '2026-04-05T02:55:00', level: 'light', seconds: 1500 },
        { dateTime: '2026-04-05T03:20:00', level: 'rem', seconds: 2400 },
        { dateTime: '2026-04-05T04:00:00', level: 'wake', seconds: 600 },
        { dateTime: '2026-04-05T04:10:00', level: 'light', seconds: 1800 },
        { dateTime: '2026-04-05T04:40:00', level: 'deep', seconds: 2400 },
        { dateTime: '2026-04-05T05:20:00', level: 'rem', seconds: 1800 },
        { dateTime: '2026-04-05T05:50:00', level: 'light', seconds: 1200 },
        { dateTime: '2026-04-05T06:10:00', level: 'wake', seconds: 300 },
      ],
      shortData: [
        { dateTime: '2026-04-05T01:42:00', level: 'wake', seconds: 60 },
        { dateTime: '2026-04-05T03:18:00', level: 'wake', seconds: 90 },
        { dateTime: '2026-04-05T05:48:00', level: 'wake', seconds: 45 },
      ],
    },
  ],
  hr_zones: [
    null, null, null, null, null, null,
    [
      { name: 'Out of Range', minutes: 1200, caloriesOut: 1800 },
      { name: 'Fat Burn', minutes: 35, caloriesOut: 280 },
      { name: 'Cardio', minutes: 18, caloriesOut: 195 },
      { name: 'Peak', minutes: 5, caloriesOut: 68 },
    ],
  ],
  goals: [
    null, null, null, null, null, null,
    { steps: 10000, distance: 8.05, caloriesOut: 2244, activeMinutes: 30 },
  ],
};
