import { useEffect, useState } from 'react';
import { useReducedMotion } from '../../lib/useReducedMotion';

interface CountUpProps {
  value: number;
  /** 中間値も渡されるため、format 側で丸めること */
  format?: (v: number) => string;
  duration?: number;
}

/**
 * 0→value をイージング付きでカウントアップ表示する。
 * prefers-reduced-motion 時はアニメーションせず最終値を即時表示。
 */
export function CountUp({ value, format, duration = 800 }: CountUpProps) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (reduced) return;
    let raf: number;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
      setDisplay(value * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduced]);

  const shown = reduced ? value : display;
  return <>{format ? format(shown) : Math.round(shown).toLocaleString()}</>;
}
