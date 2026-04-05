"""Fitbitヘルスデータの可視化とRecovery Score試算"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))
DAILY_DIR = DATA_DIR / "daily"
OUTPUT_DIR = DATA_DIR / "charts"

rcParams["font.family"] = "sans-serif"
rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]


def load_daily_data() -> dict:
    """日付順にソートされたデータを返す"""
    data = {}
    if not DAILY_DIR.exists():
        print(f"Error: {DAILY_DIR} not found. Run fetch_data.py first.")
        sys.exit(1)
    for f in sorted(DAILY_DIR.glob("*.json")):
        with open(f) as fp:
            data[f.stem] = json.load(fp)
    return data


def extract_metrics(data: dict) -> dict:
    """各日のデータから主要指標を抽出"""
    metrics = {
        "dates": [], "date_labels": [],
        "resting_hr": [], "steps": [], "calories": [],
        "sleep_minutes": [], "sleep_efficiency": [],
        "deep_minutes": [], "light_minutes": [], "rem_minutes": [], "wake_minutes": [],
        "hrv_rmssd": [], "spo2_avg": [],
    }
    for date_str, day in data.items():
        metrics["dates"].append(datetime.strptime(date_str, "%Y-%m-%d"))
        metrics["date_labels"].append(date_str[5:])  # "04-05" 形式

        hr_data = day.get("heartrate", {}).get("activities-heart", [{}])
        rhr = hr_data[0].get("value", {}).get("restingHeartRate") if hr_data else None
        metrics["resting_hr"].append(rhr)

        summary = day.get("activity", {}).get("summary", {})
        metrics["steps"].append(summary.get("steps", 0))
        metrics["calories"].append(summary.get("activityCalories", 0))

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

        hrv_list = day.get("hrv", {}).get("hrv", [])
        metrics["hrv_rmssd"].append(hrv_list[0]["value"]["dailyRmssd"] if hrv_list else None)

        spo2_data = day.get("spo2", {})
        spo2_val = spo2_data.get("value")
        metrics["spo2_avg"].append(spo2_val.get("avg") if isinstance(spo2_val, dict) else None)

    return metrics


def calc_recovery_score(metrics: dict, idx: int) -> float | None:
    """Recovery Score (0-100)

    HRV(35%) + RHR(25%) + Sleep Efficiency(25%) + Sleep Duration(15%)
    """
    hrv = metrics["hrv_rmssd"][idx]
    rhr = metrics["resting_hr"][idx]
    eff = metrics["sleep_efficiency"][idx]
    sleep_min = metrics["sleep_minutes"][idx]

    if hrv is None or rhr is None or eff is None or sleep_min == 0:
        return None

    hrv_score = max(0, min(100, (hrv - 10) / 70 * 100))
    rhr_score = max(0, min(100, (90 - rhr) / 40 * 100))
    eff_score = min(100, eff)
    if 420 <= sleep_min <= 540:
        time_score = 100
    elif sleep_min < 420:
        time_score = max(0, sleep_min / 420 * 100)
    else:
        time_score = max(0, 100 - (sleep_min - 540) / 120 * 50)

    return round(hrv_score * 0.35 + rhr_score * 0.25 + eff_score * 0.25 + time_score * 0.15, 1)


def plot_dashboard(metrics: dict):
    """6パネルのダッシュボードを生成（文字列X軸で日付表示を安定させる）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    labels = metrics["date_labels"]
    n = len(labels)
    x = list(range(n))

    # データがある日だけのインデックスを事前計算
    def valid_indices(values):
        return [(i, v) for i, v in enumerate(values) if v is not None and v != 0]

    fig, axes = plt.subplots(3, 2, figsize=(14, 13))
    fig.patch.set_facecolor("#f8f9fa")
    fig.suptitle("Fitbit Health Dashboard", fontsize=18, fontweight="bold", y=0.99, color="#2c3e50")

    # ====== 1. Resting Heart Rate ======
    ax = axes[0, 0]
    ax.set_facecolor("#fff")
    valid = valid_indices(metrics["resting_hr"])
    if valid:
        xi, vi = zip(*valid)
        ax.plot(xi, vi, "o-", color="#e74c3c", linewidth=2.5, markersize=8, zorder=3)
        for i, v in zip(xi, vi):
            ax.annotate(f"{v}", (i, v), textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=11, fontweight="bold", color="#e74c3c")
    ax.set_title("Resting Heart Rate", fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("bpm", fontsize=10)
    ax.text(0.02, 0.95, "Lower is generally better\nHealthy range: 60-100 bpm",
            transform=ax.transAxes, fontsize=8, color="#7f8c8d", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.2)

    # ====== 2. Daily Steps ======
    ax = axes[0, 1]
    ax.set_facecolor("#fff")
    colors = ["#2ecc71" if s >= 10000 else "#3498db" for s in metrics["steps"]]
    bars = ax.bar(x, metrics["steps"], color=colors, width=0.5, zorder=3)
    ax.axhline(y=10000, color="#e74c3c", linestyle="--", alpha=0.6, linewidth=1.5, label="Goal: 10,000")
    for i, s in enumerate(metrics["steps"]):
        if s > 0:
            ax.annotate(f"{s:,}", (i, s), textcoords="offset points", xytext=(0, 5),
                       ha="center", fontsize=9, fontweight="bold")
    ax.set_title("Daily Steps", fontsize=12, fontweight="bold", pad=10)
    ax.text(0.02, 0.95, "Green = goal reached (10,000+)",
            transform=ax.transAxes, fontsize=8, color="#7f8c8d", va="top")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.2, axis="y")

    # ====== 3. Sleep Stages ======
    ax = axes[1, 0]
    ax.set_facecolor("#fff")
    deep = metrics["deep_minutes"]
    light = metrics["light_minutes"]
    rem = metrics["rem_minutes"]
    wake = metrics["wake_minutes"]
    has_sleep = any(d + l + r + w > 0 for d, l, r, w in zip(deep, light, rem, wake))
    if has_sleep:
        ax.bar(x, deep, color="#1a237e", width=0.5, label="Deep", zorder=3)
        bot1 = [d for d in deep]
        ax.bar(x, light, bottom=bot1, color="#5c6bc0", width=0.5, label="Light", zorder=3)
        bot2 = [d + l for d, l in zip(deep, light)]
        ax.bar(x, rem, bottom=bot2, color="#26a69a", width=0.5, label="REM", zorder=3)
        bot3 = [d + l + r for d, l, r in zip(deep, light, rem)]
        ax.bar(x, wake, bottom=bot3, color="#ef5350", width=0.5, label="Wake", zorder=3)
        # 合計時間をバーの上に表示
        for i in range(n):
            total = deep[i] + light[i] + rem[i] + wake[i]
            if total > 0:
                hours = total // 60
                mins = total % 60
                ax.annotate(f"{hours}h{mins}m", (i, total), textcoords="offset points",
                           xytext=(0, 5), ha="center", fontsize=9, fontweight="bold")
        ax.legend(fontsize=8, loc="upper left", ncol=4)
    ax.set_title("Sleep Stages", fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("minutes", fontsize=10)
    ax.text(0.02, 0.85, "Deep sleep aids physical recovery\nREM sleep aids memory & learning",
            transform=ax.transAxes, fontsize=8, color="#7f8c8d", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.2, axis="y")

    # ====== 4. HRV ======
    ax = axes[1, 1]
    ax.set_facecolor("#fff")
    valid = valid_indices(metrics["hrv_rmssd"])
    if valid:
        xi, vi = zip(*valid)
        ax.plot(xi, vi, "o-", color="#27ae60", linewidth=2.5, markersize=8, zorder=3)
        for i, v in zip(xi, vi):
            ax.annotate(f"{v:.1f}", (i, v), textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=11, fontweight="bold", color="#27ae60")
    ax.set_title("HRV (Heart Rate Variability)", fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("RMSSD (ms)", fontsize=10)
    ax.text(0.02, 0.95, "Higher = better recovery & fitness\nMeasured during sleep",
            transform=ax.transAxes, fontsize=8, color="#7f8c8d", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.2)

    # ====== 5. Recovery Score ======
    ax = axes[2, 0]
    ax.set_facecolor("#fff")
    scores = []
    score_x = []
    score_labels = []
    for i in range(n):
        score = calc_recovery_score(metrics, i)
        if score is not None:
            scores.append(score)
            score_x.append(i)
            score_labels.append(labels[i])

    if scores:
        bar_colors = ["#2ecc71" if s >= 67 else "#f39c12" if s >= 34 else "#e74c3c" for s in scores]
        ax.bar(score_x, scores, color=bar_colors, width=0.5, zorder=3)
        for sx, s in zip(score_x, scores):
            ax.annotate(f"{s:.0f}", (sx, s), textcoords="offset points", xytext=(0, 5),
                       ha="center", fontsize=12, fontweight="bold")
        ax.set_ylim(0, 105)
        ax.axhspan(67, 100, alpha=0.05, color="#2ecc71")
        ax.axhspan(34, 67, alpha=0.05, color="#f39c12")
        ax.axhspan(0, 34, alpha=0.05, color="#e74c3c")
        ax.text(0.98, 95, "Good", fontsize=8, color="#2ecc71", ha="right", transform=ax.get_yaxis_transform())
        ax.text(0.98, 50, "Moderate", fontsize=8, color="#f39c12", ha="right", transform=ax.get_yaxis_transform())
        ax.text(0.98, 17, "Poor", fontsize=8, color="#e74c3c", ha="right", transform=ax.get_yaxis_transform())
    ax.set_title("Recovery Score", fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("Score (0-100)", fontsize=10)
    ax.text(0.02, 0.95, "HRV 35% + RHR 25% + Sleep Eff. 25% + Duration 15%",
            transform=ax.transAxes, fontsize=8, color="#7f8c8d", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.2, axis="y")

    # ====== 6. SpO2 ======
    ax = axes[2, 1]
    ax.set_facecolor("#fff")
    valid = valid_indices(metrics["spo2_avg"])
    if valid:
        xi, vi = zip(*valid)
        ax.plot(xi, vi, "o-", color="#00acc1", linewidth=2.5, markersize=8, zorder=3)
        for i, v in zip(xi, vi):
            ax.annotate(f"{v:.1f}%", (i, v), textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=11, fontweight="bold", color="#00acc1")
        ax.set_ylim(90, 100)
    ax.set_title("SpO2 (Blood Oxygen)", fontsize=12, fontweight="bold", pad=10)
    ax.set_ylabel("%", fontsize=10)
    ax.text(0.02, 0.95, "Normal range: 95-100%\nMeasured during sleep",
            transform=ax.transAxes, fontsize=8, color="#7f8c8d", va="top")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.grid(True, alpha=0.2)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    output_path = OUTPUT_DIR / "dashboard.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Dashboard saved: {output_path}")


def print_summary(metrics: dict):
    """最新日のサマリーをターミナルに表示"""
    if not metrics["dates"]:
        print("No data available")
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
        label = "Good" if score >= 67 else "Moderate" if score >= 34 else "Poor"
        print(f"\n  Recovery Score   : {score:.0f}/100 ({label})")
    else:
        print(f"\n  Recovery Score   : N/A (insufficient data)")

    print(f"{'='*50}\n")


def main():
    data = load_daily_data()
    print(f"Loaded {len(data)} days of data")
    metrics = extract_metrics(data)
    print_summary(metrics)
    plot_dashboard(metrics)


if __name__ == "__main__":
    main()
