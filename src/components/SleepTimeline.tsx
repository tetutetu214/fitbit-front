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
    return <div style={{ color: '#7d8590', padding: 20 }}>睡眠データがありません</div>;
  }

  const allData = timeline.data;
  const startTime = new Date(allData[0].dateTime).getTime();
  const lastEntry = allData[allData.length - 1];
  const endTime = new Date(lastEntry.dateTime).getTime() + lastEntry.seconds * 1000;
  const totalMs = endTime - startTime;

  const startLabel = new Date(startTime).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
  const endLabel = new Date(endTime).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });

  const renderBars = (entries: SleepTimelineEntry[]) => (
    <div className="timeline-wrap">
      {entries.map((d, i) => {
        const s = new Date(d.dateTime).getTime();
        const left = ((s - startTime) / totalMs) * 100;
        const width = ((d.seconds * 1000) / totalMs) * 100;
        const mins = Math.round(d.seconds / 60);
        const time = new Date(d.dateTime).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
        return (
          <div
            key={i}
            className="timeline-bar"
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
      <div style={{ display: 'flex', gap: 12, marginBottom: 8, flexWrap: 'wrap' }}>
        {Object.entries(nameMap).map(([k, v]) => (
          <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#7d8590' }}>
            <span style={{ width: 12, height: 12, borderRadius: 2, background: colorMap[k] }} />
            {v}
          </span>
        ))}
      </div>

      {renderBars(allData)}
      <div className="timeline-labels">
        <span>{startLabel}</span>
        <span>{endLabel}</span>
      </div>

      {timeline.shortData && timeline.shortData.length > 0 && (
        <>
          <button className="toggle-btn" onClick={() => setShowShort((p) => !p)}>
            {showShort ? '短い覚醒を非表示' : `短い覚醒を表示 (${timeline.shortData.length}回)`}
          </button>
          {showShort && merged && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 11, color: '#7d8590', marginBottom: 4 }}>
                短い覚醒（30〜120秒）
              </div>
              {renderBars(merged)}
              <div className="timeline-labels">
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
