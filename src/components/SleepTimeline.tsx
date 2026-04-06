import { useState } from 'react';
import type { SleepTimeline as SleepTimelineData, SleepTimelineEntry } from '../types/health';

interface SleepTimelineProps {
  timeline: SleepTimelineData | null;
}

const colorMap: Record<string, string> = {
  deep: '#1a237e', light: '#5c6bc0', rem: '#26a69a', wake: '#ef5350',
};
const nameMap: Record<string, string> = {
  deep: '深い眠り', light: '浅い眠り', rem: 'レム睡眠', wake: '覚醒',
};

export function SleepTimeline({ timeline }: SleepTimelineProps) {
  const [showShort, setShowShort] = useState(false);

  if (!timeline || !timeline.data || timeline.data.length === 0) {
    return <div className="p-5 text-text2">睡眠データがありません</div>;
  }

  const allData = timeline.data;
  const startTime = new Date(allData[0].dateTime).getTime();
  const lastEntry = allData[allData.length - 1];
  const endTime = new Date(lastEntry.dateTime).getTime() + lastEntry.seconds * 1000;
  const totalMs = endTime - startTime;

  const startLabel = new Date(startTime).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
  const endLabel = new Date(endTime).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

  const renderBars = (entries: SleepTimelineEntry[]) => (
    <div className="relative my-2 h-[50px] overflow-hidden rounded-md bg-card2">
      {entries.map((d, i) => {
        const s = new Date(d.dateTime).getTime();
        const left = ((s - startTime) / totalMs) * 100;
        const width = ((d.seconds * 1000) / totalMs) * 100;
        const mins = Math.round(d.seconds / 60);
        const time = new Date(d.dateTime).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
        return (
          <div
            key={i}
            className="absolute top-0 h-full"
            style={{
              left: `${left}%`,
              width: `${width}%`,
              background: colorMap[d.level] || '#555',
            }}
            title={`${nameMap[d.level] || d.level} ${time} (${mins}分)`}
          />
        );
      })}
    </div>
  );

  const merged = timeline.shortData
    ? [...allData, ...timeline.shortData].sort(
        (a, b) => new Date(a.dateTime).getTime() - new Date(b.dateTime).getTime(),
      )
    : null;

  return (
    <>
      <div className="mb-2 flex flex-wrap gap-3">
        {Object.entries(nameMap).map(([k, v]) => (
          <span key={k} className="flex items-center gap-1 text-[11px] text-text2">
            <span className="h-3 w-3 rounded-sm" style={{ background: colorMap[k] }} />
            {v}
          </span>
        ))}
      </div>

      {renderBars(allData)}
      <div className="flex justify-between text-[10px] text-text3">
        <span>{startLabel}</span>
        <span>{endLabel}</span>
      </div>

      {timeline.shortData && timeline.shortData.length > 0 && (
        <>
          <button
            className="mt-1.5 cursor-pointer rounded border border-accent bg-transparent px-2 py-0.5 text-[11px] text-accent hover:bg-accent/10"
            onClick={() => setShowShort((p) => !p)}
          >
            {showShort ? '短い覚醒を非表示' : `短い覚醒を表示 (${timeline.shortData.length}回)`}
          </button>
          {showShort && merged && (
            <div className="mt-2">
              <div className="mb-1 text-[11px] text-text2">
                短い覚醒（30〜120秒）
              </div>
              {renderBars(merged)}
              <div className="flex justify-between text-[10px] text-text3">
                <span>{startLabel}</span>
                <span>{endLabel}</span>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
