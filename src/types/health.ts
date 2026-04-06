export interface HRZone {
  name: string;
  minutes: number;
  caloriesOut: number;
}

export interface SleepTimelineEntry {
  dateTime: string;
  level: 'deep' | 'light' | 'rem' | 'wake' | 'restless' | 'asleep' | 'awake';
  seconds: number;
}

export interface SleepTimeline {
  data: SleepTimelineEntry[];
  shortData?: SleepTimelineEntry[];
}

export interface Goals {
  steps?: number;
  distance?: number;
  caloriesOut?: number;
  activeMinutes?: number;
}

export interface HealthData {
  dates: string[];
  resting_hr: (number | null)[];
  steps: number[];
  active_calories: number[];
  sleep_minutes: number[];
  sleep_efficiency: (number | null)[];
  deep: number[];
  light: number[];
  rem: number[];
  wake: number[];
  hrv_rmssd: (number | null)[];
  spo2_avg: (number | null)[];
  spo2_min: (number | null)[];
  spo2_max: (number | null)[];
  sedentary_minutes: (number | null)[];
  sleep_timelines: (SleepTimeline | null)[];
  hr_zones: (HRZone[] | null)[];
  goals: (Goals | null)[];
}
