import type { HealthData } from '../types/health';
import { Header } from './Header';
import { SummaryCards } from './SummaryCards';
import { GoalRings } from './GoalRings';
import { SleepTimeline } from './SleepTimeline';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './ui/Card';
import {
  RestingHRChart,
  StepsChart,
  SleepStagesChart,
  HRVChart,
  SpO2Chart,
  HRZoneDonut,
} from './Charts';

interface DashboardProps {
  data: HealthData;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div className="my-5 mb-3 border-l-[3px] border-accent pl-2.5 text-[15px] tracking-wide text-text2">
      {children}
    </div>
  );
}

function ChartGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(460px,1fr))] gap-3.5 max-md:grid-cols-1">
      {children}
    </div>
  );
}

export function Dashboard({ data }: DashboardProps) {
  const last = data.dates.length - 1;

  return (
    <>
      <Header lastDate={last >= 0 ? data.dates[last] : ''} />
      <SummaryCards data={data} />

      <div className="px-8 max-md:px-4">
        <SectionTitle>活動目標の達成率</SectionTitle>
      </div>
      <GoalRings data={data} />

      <div className="px-8 pb-5 max-md:px-4">
        <SectionTitle>睡眠</SectionTitle>
        <ChartGrid>
          <Card>
            <CardHeader><CardTitle>睡眠タイムライン</CardTitle></CardHeader>
            <CardContent>
              <SleepTimeline timeline={last >= 0 ? data.sleep_timelines[last] : null} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>睡眠ステージ推移</CardTitle></CardHeader>
            <CardContent><SleepStagesChart data={data} /></CardContent>
          </Card>
        </ChartGrid>
      </div>

      <div className="px-8 pb-5 max-md:px-4">
        <SectionTitle>心臓・循環器</SectionTitle>
        <ChartGrid>
          <Card>
            <CardHeader><CardTitle>安静時心拍数</CardTitle></CardHeader>
            <CardContent><RestingHRChart data={data} /></CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>心拍ゾーン（本日）</CardTitle></CardHeader>
            <CardContent><HRZoneDonut data={data} /></CardContent>
          </Card>
        </ChartGrid>
      </div>

      <div className="px-8 pb-5 max-md:px-4">
        <SectionTitle>自律神経</SectionTitle>
        <ChartGrid>
          <Card>
            <CardHeader><CardTitle>HRV（自律神経ゆらぎ）</CardTitle></CardHeader>
            <CardContent><HRVChart data={data} /></CardContent>
            <CardFooter>※数値は個人差が大きいため、自分自身の推移を参考にしてください</CardFooter>
          </Card>
        </ChartGrid>
      </div>

      <div className="px-8 pb-5 max-md:px-4">
        <SectionTitle>血中酸素・歩数</SectionTitle>
        <ChartGrid>
          <Card>
            <CardHeader><CardTitle>血中酸素濃度 (SpO2)</CardTitle></CardHeader>
            <CardContent><SpO2Chart data={data} /></CardContent>
            <CardFooter>※正常範囲: 95〜100% 睡眠中に計測</CardFooter>
          </Card>
          <Card>
            <CardHeader><CardTitle>歩数</CardTitle></CardHeader>
            <CardContent><StepsChart data={data} /></CardContent>
          </Card>
        </ChartGrid>
      </div>
    </>
  );
}
