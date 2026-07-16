import { useMemo, useRef, useState } from 'react';
import type { HealthData } from '../types/health';
import { Header } from './Header';
import { DateStrip } from './DateStrip';
import { HeroScore } from './HeroScore';
import { SummaryCards } from './SummaryCards';
import { GoalRings } from './GoalRings';
import { SleepTimeline } from './SleepTimeline';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './ui/Card';
import { readinessScore, zoneFor } from '../lib/readiness';
import {
  RestingHRChart,
  StepsChart,
  SleepStagesChart,
  HRVChart,
  SpO2Chart,
  HRZoneDonut,
  BodyCompositionChart,
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

const SWIPE_THRESHOLD = 60;

export function Dashboard({ data }: DashboardProps) {
  const last = data.dates.length - 1;
  const [selectedIdx, setSelectedIdx] = useState(last);
  const touchStart = useRef<{ x: number; y: number } | null>(null);

  const dotColors = useMemo(
    () =>
      data.dates.map((_, i) => {
        const s = readinessScore(data, i);
        return s === null ? null : zoneFor(s).color;
      }),
    [data],
  );

  const select = (i: number) => {
    setSelectedIdx(Math.max(0, Math.min(last, i)));
  };

  // 左スワイプ=翌日 / 右スワイプ=前日（縦スクロールと区別するため横成分優位のみ）
  const onTouchStart = (e: React.TouchEvent) => {
    touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
  };
  const onTouchEnd = (e: React.TouchEvent) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (!start) return;
    const dx = e.changedTouches[0].clientX - start.x;
    const dy = e.changedTouches[0].clientY - start.y;
    if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    select(selectedIdx + (dx < 0 ? 1 : -1));
  };

  return (
    <>
      <Header lastDate={last >= 0 ? data.dates[last] : ''} />
      <DateStrip
        dates={data.dates}
        selected={selectedIdx}
        onSelect={select}
        dotColors={dotColors}
      />

      <div
        key={selectedIdx >= 0 ? data.dates[selectedIdx] : 'empty'}
        className="animate-fade-slide"
        onTouchStart={onTouchStart}
        onTouchEnd={onTouchEnd}
      >
        <HeroScore data={data} index={selectedIdx} />
        <SummaryCards data={data} index={selectedIdx} />

        <div className="px-8 max-md:px-4">
          <SectionTitle>活動目標の達成率</SectionTitle>
        </div>
        <GoalRings data={data} index={selectedIdx} />

        <div className="px-8 pb-5 max-md:px-4">
          <SectionTitle>睡眠</SectionTitle>
          <ChartGrid>
            <Card className="flex flex-col">
              <CardHeader><CardTitle>睡眠タイムライン</CardTitle></CardHeader>
              <CardContent className="flex flex-1 flex-col justify-center">
                <SleepTimeline timeline={selectedIdx >= 0 ? data.sleep_timelines[selectedIdx] : null} />
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
              <CardHeader><CardTitle>心拍ゾーン</CardTitle></CardHeader>
              <CardContent><HRZoneDonut data={data} index={selectedIdx} /></CardContent>
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

        <div className="px-8 pb-5 max-md:px-4">
          <SectionTitle>体組成</SectionTitle>
          <ChartGrid>
            <Card>
              <CardHeader><CardTitle>体重・体脂肪率の推移</CardTitle></CardHeader>
              <CardContent><BodyCompositionChart data={data} /></CardContent>
              <CardFooter>※TANITA 体組成計のデータ</CardFooter>
            </Card>
          </ChartGrid>
        </div>
      </div>
    </>
  );
}
