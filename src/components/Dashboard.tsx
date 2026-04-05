import type { HealthData } from '../types/health';
import { Header } from './Header';
import { SummaryCards } from './SummaryCards';
import { GoalRings } from './GoalRings';
import { SleepTimeline } from './SleepTimeline';
import {
  RestingHRChart,
  StepsChart,
  SleepStagesChart,
  HRVChart,
  RecoveryChart,
  SpO2Chart,
  HRZoneDonut,
} from './Charts';

interface DashboardProps {
  data: HealthData;
}

export function Dashboard({ data }: DashboardProps) {
  const last = data.dates.length - 1;

  return (
    <>
      <Header lastDate={last >= 0 ? data.dates[last] : ''} />
      <SummaryCards data={data} />

      <div className="section">
        <div className="section-title">活動目標の達成率</div>
      </div>
      <GoalRings data={data} />

      <div className="section">
        <div className="section-title">睡眠</div>
        <div className="grid2">
          <div className="chart-card">
            <h3>睡眠タイムライン</h3>
            <SleepTimeline timeline={last >= 0 ? data.sleep_timelines[last] : null} />
          </div>
          <div className="chart-card">
            <h3>睡眠ステージ推移</h3>
            <SleepStagesChart data={data} />
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">心臓・循環器</div>
        <div className="grid2">
          <div className="chart-card">
            <h3>安静時心拍数</h3>
            <RestingHRChart data={data} />
          </div>
          <div className="chart-card">
            <h3>心拍ゾーン（本日）</h3>
            <HRZoneDonut data={data} />
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">回復・自律神経</div>
        <div className="grid2">
          <div className="chart-card">
            <h3>HRV（自律神経ゆらぎ）</h3>
            <HRVChart data={data} />
            <div className="note">※数値は個人差が大きいため、自分自身の推移を参考にしてください</div>
          </div>
          <div className="chart-card">
            <h3>回復スコア</h3>
            <RecoveryChart data={data} />
          </div>
        </div>
      </div>

      <div className="section">
        <div className="section-title">血中酸素・歩数</div>
        <div className="grid2">
          <div className="chart-card">
            <h3>血中酸素濃度 (SpO2)</h3>
            <SpO2Chart data={data} />
            <div className="note">※正常範囲: 95〜100%　睡眠中に計測</div>
          </div>
          <div className="chart-card">
            <h3>歩数</h3>
            <StepsChart data={data} />
          </div>
        </div>
      </div>
    </>
  );
}
