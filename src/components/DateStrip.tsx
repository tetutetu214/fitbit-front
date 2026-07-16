import { useEffect, useMemo, useRef, useState } from 'react';
import { BottomSheet } from './ui/BottomSheet';

interface DateStripProps {
  dates: string[];
  selected: number;
  onSelect: (index: number) => void;
  /** 各日のスコア品質ドット色。データなしは null */
  dotColors: (string | null)[];
}

const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土'];

function parseDate(d: string): Date {
  return new Date(`${d}T00:00:00`);
}

interface CalendarGridProps {
  dates: string[];
  selected: number;
  dotColors: (string | null)[];
  onSelect: (index: number) => void;
  onClose: () => void;
}

function CalendarGrid({ dates, selected, dotColors, onSelect, onClose }: CalendarGridProps) {
  const indexByDate = useMemo(() => {
    const m = new Map<string, number>();
    dates.forEach((d, i) => m.set(d, i));
    return m;
  }, [dates]);

  const first = parseDate(dates[0]);
  const lastD = parseDate(dates[dates.length - 1]);
  const sel = parseDate(dates[selected]);
  const [viewYear, setViewYear] = useState(sel.getFullYear());
  const [viewMonth, setViewMonth] = useState(sel.getMonth());

  const canPrev = viewYear > first.getFullYear() ||
    (viewYear === first.getFullYear() && viewMonth > first.getMonth());
  const canNext = viewYear < lastD.getFullYear() ||
    (viewYear === lastD.getFullYear() && viewMonth < lastD.getMonth());

  const moveMonth = (delta: number) => {
    const d = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
  };

  const firstDow = new Date(viewYear, viewMonth, 1).getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const cells: (number | null)[] = [
    ...Array.from({ length: firstDow }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const pad = (n: number) => String(n).padStart(2, '0');

  return (
    <BottomSheet title="カレンダー" onClose={onClose} snapPoints={[55, 85]}>
      <div className="mb-3 flex items-center justify-between">
        <button
          onClick={() => moveMonth(-1)}
          disabled={!canPrev}
          className="rounded px-2 py-1 text-sm text-text2 hover:text-text disabled:opacity-30"
          aria-label="前の月"
        >
          ‹
        </button>
        <div className="text-sm font-semibold text-text">{viewYear}年{viewMonth + 1}月</div>
        <button
          onClick={() => moveMonth(1)}
          disabled={!canNext}
          className="rounded px-2 py-1 text-sm text-text2 hover:text-text disabled:opacity-30"
          aria-label="次の月"
        >
          ›
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAYS.map((w) => (
          <div key={w} className="py-1 text-[11px] text-text3">{w}</div>
        ))}
        {cells.map((day, i) => {
          if (day === null) return <div key={`pad-${i}`} />;
          const dateStr = `${viewYear}-${pad(viewMonth + 1)}-${pad(day)}`;
          const idx = indexByDate.get(dateStr);
          const isSelected = idx === selected;
          if (idx === undefined) {
            return (
              <div key={dateStr} className="py-1.5 text-sm text-text3/60">{day}</div>
            );
          }
          return (
            <button
              key={dateStr}
              onClick={() => { onSelect(idx); onClose(); }}
              className={`flex flex-col items-center rounded-lg py-1.5 text-sm transition-colors ${
                isSelected ? 'bg-accent/20 font-bold text-accent' : 'text-text hover:bg-card2'
              }`}
            >
              {day}
              <span
                className="mt-0.5 h-1.5 w-1.5 rounded-full"
                style={{ background: dotColors[idx] ?? '#484f58' }}
              />
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-[10px] text-text3">
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#10b981]" />最適</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#f59e0b]" />良好</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#f43f5e]" />要注意</span>
        <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[#484f58]" />データなし</span>
      </div>
    </BottomSheet>
  );
}

export function DateStrip({ dates, selected, onSelect, dotColors }: DateStripProps) {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const selectedRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }, [selected]);

  if (dates.length === 0) return null;

  const sel = parseDate(dates[selected]);
  const isToday = selected === dates.length - 1;

  return (
    <>
      <div className="sticky top-0 z-40 flex items-center gap-3 border-b border-border bg-bg/95 px-8 py-2 backdrop-blur max-md:px-4">
        <button
          onClick={() => setCalendarOpen(true)}
          className="shrink-0 rounded-lg px-2 py-1 text-[13px] font-semibold text-text hover:bg-card2"
          aria-label="カレンダーを開く"
        >
          {sel.getFullYear()}年{sel.getMonth() + 1}月 <span className="text-text3">▾</span>
        </button>
        <div className="flex flex-1 gap-1 overflow-x-auto scroll-smooth py-1 [scrollbar-width:none]">
          {dates.map((d, i) => {
            const dt = parseDate(d);
            const isSelected = i === selected;
            return (
              <button
                key={d}
                ref={isSelected ? selectedRef : undefined}
                onClick={() => onSelect(i)}
                className={`flex w-11 shrink-0 flex-col items-center rounded-lg border py-1 transition-colors ${
                  isSelected
                    ? 'border-accent bg-accent/15'
                    : 'border-transparent hover:bg-card2'
                }`}
                aria-label={d}
                aria-current={isSelected ? 'date' : undefined}
              >
                <span className="text-[10px] text-text3">{WEEKDAYS[dt.getDay()]}</span>
                <span className={`text-sm font-semibold ${isSelected ? 'text-accent' : 'text-text'}`}>
                  {dt.getDate()}
                </span>
                <span
                  className="mt-0.5 h-1.5 w-1.5 rounded-full"
                  style={{ background: dotColors[i] ?? '#484f58' }}
                />
              </button>
            );
          })}
        </div>
        <button
          onClick={() => onSelect(dates.length - 1)}
          disabled={isToday}
          className="shrink-0 rounded-full border border-accent px-3 py-1 text-xs font-semibold text-accent transition-opacity hover:bg-accent/10 disabled:opacity-30"
        >
          今日
        </button>
      </div>
      {calendarOpen && (
        <CalendarGrid
          dates={dates}
          selected={selected}
          dotColors={dotColors}
          onSelect={onSelect}
          onClose={() => setCalendarOpen(false)}
        />
      )}
    </>
  );
}
