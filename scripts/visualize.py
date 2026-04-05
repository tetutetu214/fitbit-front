"""Fitbitヘルスデータの可視化とRecovery Score試算"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
DAILY_DIR = DATA_DIR / "daily"
OUTPUT_DIR = DATA_DIR / "charts"

# 日本語フォント対応（なければ英語フォールバック）
rcParams["font.family"] = "sans-serif"
rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Hiragino Sans", "Yu Gothic"]


def load_daily_data() -> dict:
    """日付順にソートされたデータを返す"""
    data = {}
    if not DAILY_DIR.exists():
        print(f"エラー: {DAILY_DIR} が見つかりません。先に fetch_data.py を実行してください")
        sys.exit(1)

    for f in sorted(DAILY_DIR.glob("*.json")):
        date_str = f.stem
        with open(f) as fp:
            data[date_str] = json.load(fp)
    return data


def extract_metrics(data: dict) -> dict:
    """各日のデータから主要指標を抽出"""
    metrics = {
        "dates": [],
        "resting_hr": [],
        "steps": [],
        "calories": [],
        "sleep_minutes": [],
        "sleep_efficiency": [],
        "deep_minutes": [],
        "light_minutes": [],
        "rem_minutes": [],
        "wake_minutes": [],
        "hrv_rmssd": [],
        "spo2_avg": [],
    }

    for date_str, day in data.items():
        metrics["dates"].append(datetime.strptime(date_str, "%Y-%m-%d"))

        # 心拍数
        hr_data = day.get("heartrate", {}).get("activities-heart", [{}])
        rhr = hr_data[0].get("value", {}).get("restingHeartRate") if hr_data else None
        metrics["resting_hr"].append(rhr)

        # 活動量
        summary = day.get("activity", {}).get("summary", {})
        metrics["steps"].append(summary.get("steps", 0))
        metrics["calories"].append(summary.get("activityCalories", 0))

        # 睡眠
        sleep_summary = day.get("sleep", {}).get("summary", {})
        metrics["sleep_minutes"].append(sleep_summary.get("totalMinutesAsleep", 0))

        sleep_records = day.get("sleep", {}).get("sleep", [])
        main_sleep = next((s for s in sleep_records if s.get("isMainSleep")), None)
        metrics["sleep_efficiency"].append(main_sleep.get("efficiency") if main_sleep else None)

        stages = sleep_summary.get("stages", {})
        metrics["deep_minutes"].append(stages.get("deep", 0))
        metrics["light_minutes"].append(stages.get("light", 0))
        metrics["rem_minutes"].append(stages.get("rem", 0))
        metrics["wake_minutes"].append(stages.get("wake", 0))

        # HRV
        hrv_list = day.get("hrv", {}).get("hrv", [])
        hrv_val = hrv_list[0].get("value", {}).get("dailyRmssd") if hrv_list else None
        metrics["hrv_rmssd"].append(hrv_val)

        # SpO2
        spo2_data = day.get("spo2", {})
        spo2_avg = spo2_data.get("value", {}).get("avg") if isinstance(spo2_data.get("value"), dict) else None
        metrics["spo2_avg"].append(spo2_avg)

    return metrics


def calc_recovery_score(metrics: dict, idx: int) -> float | None:
    """Recovery Score (0-100) を算出

    構成:
      HRV (35%): 個人ベースラインとの比較
      RHR (25%): 低いほど良い
      睡眠効率 (25%): そのまま%
      睡眠時間 (15%): 7-9時間を100%
    """
    hrv = metrics["hrv_rmssd"][idx]
    rhr = metrics["resting_hr"][idx]
    efficiency = metrics["sleep_efficiency"][idx]
    sleep_min = metrics["sleep_minutes"][idx]

    if hrv is None or rhr is None or efficiency is None or sleep_min == 0:
        return None

    # HRVスコア: ベースラインがまだないので絶対値ベースで簡易計算
    # RMSSD 20-80ms を 0-100 にマッピング
    hrv_score = max(0, min(100, (hrv - 10) / 70 * 100))

    # RHRスコア: 50-90bpm を 100-0 にマッピング（低いほど良い）
    rhr_score = max(0, min(100, (90 - rhr) / 40 * 100))

    # 睡眠効率スコア: そのまま
    eff_score = min(100, efficiency)

    # 睡眠時間スコア: 420-540分(7-9h)を100%、それ以外は減点
    if 420 <= sleep_min <= 540:
        time_score = 100
    elif sleep_min < 420:
        time_score = max(0, sleep_min / 420 * 100)
    else:
        time_score = max(0, 100 - (sleep_min - 540) / 120 * 50)

    score = hrv_score * 0.35 + rhr_score * 0.25 + eff_score * 0.25 + time_score * 0.15
    return round(score, 1)


def plot_dashboard(metrics: dict):
    """5パネルのダッシュボードを生成"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dates = metrics["dates"]

    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    fig.suptitle("Fitbit Health Dashboard", fontsize=16, fontweight="bold", y=0.98)

    # --- 1. Resting Heart Rate ---
    ax = axes[0, 0]
    valid = [(d, v) for d, v in zip(dates, metrics["resting_hr"]) if v is not None]
    if valid:
        d, v = zip(*valid)
        ax.plot(d, v, "o-", color="#e74c3c", linewidth=2, markersize=6)
        for di, vi in zip(d, v):
            ax.annotate(str(vi), (di, vi), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_title("Resting Heart Rate (bpm)")
    ax.set_ylabel("bpm")
    ax.grid(True, alpha=0.3)

    # --- 2. Steps ---
    ax = axes[0, 1]
    colors = ["#2ecc71" if s >= 10000 else "#3498db" for s in metrics["steps"]]
    ax.bar(dates, metrics["steps"], color=colors, width=0.6)
    ax.axhline(y=10000, color="#e74c3c", linestyle="--", alpha=0.7, label="Goal: 10,000")
    for d, s in zip(dates, metrics["steps"]):
        if s > 0:
            ax.annotate(f"{s:,}", (d, s), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=8)
    ax.set_title("Daily Steps")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # --- 3. Sleep Stages ---
    ax = axes[1, 0]
    deep = metrics["deep_minutes"]
    light = metrics["light_minutes"]
    rem = metrics["rem_minutes"]
    wake = metrics["wake_minutes"]
    has_sleep = any(d + l + r + w > 0 for d, l, r, w in zip(deep, light, rem, wake))
    if has_sleep:
        ax.bar(dates, deep, color="#1a237e", width=0.6, label="Deep")
        ax.bar(dates, light, bottom=deep, color="#5c6bc0", width=0.6, label="Light")
        ax.bar(dates, rem, bottom=[d + l for d, l in zip(deep, light)], color="#26a69a", width=0.6, label="REM")
        ax.bar(dates, wake, bottom=[d + l + r for d, l, r in zip(deep, light, rem)], color="#ef5350", width=0.6, label="Wake")
        ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Sleep Stages (minutes)")
    ax.set_ylabel("minutes")
    ax.grid(True, alpha=0.3, axis="y")

    # --- 4. HRV ---
    ax = axes[1, 1]
    valid = [(d, v) for d, v in zip(dates, metrics["hrv_rmssd"]) if v is not None]
    if valid:
        d, v = zip(*valid)
        ax.plot(d, v, "o-", color="#27ae60", linewidth=2, markersize=6)
        for di, vi in zip(d, v):
            ax.annotate(f"{vi:.1f}", (di, vi), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax.set_title("HRV - Daily RMSSD (ms)")
    ax.set_ylabel("ms")
    ax.grid(True, alpha=0.3)

    # --- 5. Recovery Score ---
    ax = axes[2, 0]
    scores = []
    score_dates = []
    for i in range(len(dates)):
        score = calc_recovery_score(metrics, i)
        if score is not None:
            scores.append(score)
            score_dates.append(dates[i])

    if scores:
        bar_colors = []
        for s in scores:
            if s >= 67:
                bar_colors.append("#2ecc71")
            elif s >= 34:
                bar_colors.append("#f39c12")
            else:
                bar_colors.append("#e74c3c")

        ax.bar(score_dates, scores, color=bar_colors, width=0.6)
        for d, s in zip(score_dates, scores):
            ax.annotate(f"{s:.0f}", (d, s), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=10, fontweight="bold")
        ax.set_ylim(0, 100)
        ax.axhline(y=67, color="#2ecc71", linestyle="--", alpha=0.5)
        ax.axhline(y=34, color="#f39c12", linestyle="--", alpha=0.5)
    ax.set_title("Recovery Score (0-100)")
    ax.set_ylabel("Score")
    ax.grid(True, alpha=0.3, axis="y")

    # --- 6. SpO2 ---
    ax = axes[2, 1]
    valid = [(d, v) for d, v in zip(dates, metrics["spo2_avg"]) if v is not None]
    if valid:
        d, v = zip(*valid)
        ax.plot(d, v, "o-", color="#00acc1", linewidth=2, markersize=6)
        for di, vi in zip(d, v):
            ax.annotate(f"{vi:.1f}%", (di, vi), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
        ax.set_ylim(90, 100)
    ax.set_title("SpO2 Average (%)")
    ax.set_ylabel("%")
    ax.grid(True, alpha=0.3)

    # 日付フォーマット
    for row in axes:
        for ax in row:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    output_path = OUTPUT_DIR / "dashboard.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"ダッシュボードを保存しました: {output_path}")


def print_summary(metrics: dict):
    """最新日のサマリーをターミナルに表示"""
    if not metrics["dates"]:
        print("データがありません")
        return

    idx = -1
    date = metrics["dates"][idx]
    print(f"\n{'='*50}")
    print(f"  Health Summary - {date.strftime('%Y-%m-%d')}")
    print(f"{'='*50}")

    rhr = metrics["resting_hr"][idx]
    print(f"  Heart Rate (RHR) : {rhr if rhr else 'N/A'} bpm")
    print(f"  Steps            : {metrics['steps'][idx]:,}")
    print(f"  Calories (Active): {metrics['calories'][idx]:,} kcal")

    sleep_min = metrics["sleep_minutes"][idx]
    if sleep_min > 0:
        hours = sleep_min // 60
        mins = sleep_min % 60
        eff = metrics["sleep_efficiency"][idx]
        print(f"  Sleep            : {hours}h {mins}m (efficiency: {eff}%)")
        print(f"    Deep: {metrics['deep_minutes'][idx]}m | Light: {metrics['light_minutes'][idx]}m | REM: {metrics['rem_minutes'][idx]}m | Wake: {metrics['wake_minutes'][idx]}m")
    else:
        print(f"  Sleep            : N/A")

    hrv = metrics["hrv_rmssd"][idx]
    print(f"  HRV (RMSSD)      : {f'{hrv:.1f} ms' if hrv else 'N/A'}")

    spo2 = metrics["spo2_avg"][idx]
    print(f"  SpO2             : {f'{spo2:.1f}%' if spo2 else 'N/A'}")

    score = calc_recovery_score(metrics, idx)
    if score is not None:
        if score >= 67:
            label = "Good"
        elif score >= 34:
            label = "Moderate"
        else:
            label = "Poor"
        print(f"\n  Recovery Score   : {score:.0f}/100 ({label})")
    else:
        print(f"\n  Recovery Score   : N/A (insufficient data)")

    print(f"{'='*50}\n")


def main():
    data = load_daily_data()
    print(f"{len(data)}日分のデータを読み込みました")

    metrics = extract_metrics(data)
    print_summary(metrics)
    plot_dashboard(metrics)


if __name__ == "__main__":
    main()
