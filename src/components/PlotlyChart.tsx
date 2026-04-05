import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';

const baseLayout: Partial<Layout> = {
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
  data: Data[];
  layout?: Partial<Layout>;
  style?: React.CSSProperties;
}

export function PlotlyChart({ data, layout, style }: PlotlyChartProps) {
  return (
    <Plot
      data={data}
      layout={{ ...baseLayout, ...layout }}
      config={{ responsive: true, displayModeBar: false }}
      useResizeHandler
      style={{ width: '100%', height: '100%', ...style }}
    />
  );
}
