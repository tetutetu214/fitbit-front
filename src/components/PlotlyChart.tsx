import { useRef, useEffect } from 'react';
import Plotly from 'plotly.js-dist-min';

const baseLayout: Partial<Plotly.Layout> = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { color: '#7d8590', family: '-apple-system,sans-serif', size: 11 },
  margin: { t: 8, r: 16, b: 36, l: 44 },
  xaxis: { gridcolor: '#21262d' },
  yaxis: { gridcolor: '#21262d' },
  hovermode: 'x unified' as const,
  showlegend: false,
};

interface PlotlyChartProps {
  data: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
  style?: React.CSSProperties;
}

export function PlotlyChart({ data, layout, style }: PlotlyChartProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const mergedLayout = { ...baseLayout, ...layout };
    Plotly.newPlot(el, data, mergedLayout, { responsive: true, displayModeBar: false });
    return () => { Plotly.purge(el); };
  }, [data, layout]);

  return <div ref={ref} style={{ width: '100%', height: '100%', ...style }} />;
}
