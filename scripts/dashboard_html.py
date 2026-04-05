"""Fitbitヘルスデータのインタラクティブ HTML ダッシュボード生成
Issues: #24(日本語化) #25(サマリー) #26(睡眠タイムライン) #27(目標リング)
        #28(心拍ドーナツ) #29(HRV/SpO2レンジ) #30(ダークモード) #31(覚醒トグル)
"""
import json
import os
import sys
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
        "sleep_timelines": [],
        "hr_zones": [],
        "goals": [],
    }
    for date_str, day in data.items():
        metrics["dates"].append(date_str)

        hr_data = day.get("heartrate", {}).get("activities-heart", [{}])
        hr_value = hr_data[0].get("value", {}) if hr_data else {}
        rhr = hr_value.get("restingHeartRate")
        metrics["resting_hr"].append(rhr)

        zones = hr_value.get("heartRateZones", [])
        metrics["hr_zones"].append(zones)

        summary = day.get("activity", {}).get("summary", {})
        metrics["steps"].append(summary.get("steps", 0))
        metrics["active_calories"].append(summary.get("activityCalories", 0))
        metrics["goals"].append(day.get("activity", {}).get("goals", {}))

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

        if main_sleep and "levels" in main_sleep:
            levels = main_sleep["levels"]
            metrics["sleep_timelines"].append({
                "data": levels.get("data", []),
                "shortData": levels.get("shortData", []),
            })
        else:
            metrics["sleep_timelines"].append(None)

        hrv_list = day.get("hrv", {}).get("hrv", [])
        hrv_val = hrv_list[0]["value"]["dailyRmssd"] if hrv_list else None
        metrics["hrv_rmssd"].append(hrv_val)

        spo2_data = day.get("spo2", {})
        spo2_val = spo2_data.get("value") if isinstance(spo2_data.get("value"), dict) else None
        metrics["spo2_avg"].append(spo2_val.get("avg") if spo2_val else None)
        metrics["spo2_min"].append(spo2_val.get("min") if spo2_val else None)
        metrics["spo2_max"].append(spo2_val.get("max") if spo2_val else None)

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


def load_html_template() -> str:
    template_path = Path(__file__).resolve().parent / "dashboard_template.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    data = load_daily_data()
    print(f"Loaded {len(data)} days of data")

    metrics = extract_metrics(data)
    metrics_json = json.dumps(metrics, ensure_ascii=False)

    html = load_html_template().replace("__DATA_JSON__", metrics_json)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "dashboard.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard saved: {output_path}")


if __name__ == "__main__":
    main()
