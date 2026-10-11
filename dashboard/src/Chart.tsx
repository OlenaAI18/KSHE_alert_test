import { useEffect, useRef } from "react";
import Plotly from "plotly.js-basic-dist-min";
import type { Data, Layout } from "plotly.js";
export function Chart({
  title,
  data,
  ylabel,
  description,
}: {
  title: string;
  data: Data[];
  ylabel?: string;
  description?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = ref.current!;
    let active = true;
    const layout: Partial<Layout> = {
      autosize: true,
      height: 330,
      margin: { t: 25, r: 22, b: 80, l: 65 },
      paper_bgcolor: "#fff",
      plot_bgcolor: "#fff",
      font: { family: "system-ui, sans-serif", size: 12, color: "#34455e" },
      colorway: ["#2256c7", "#009e9a", "#e99536", "#6a78a2"],
      hoverlabel: { bgcolor: "#172e50", font: { color: "#fff", size: 13 } },
      xaxis: { automargin: true, type: "category" },
      yaxis: {
        title: { text: ylabel },
        gridcolor: "#edf1f7",
        automargin: true,
      },
      legend: { orientation: "h", y: -0.3 },
      hovermode: "closest",
    };
    Plotly.newPlot(node, data, layout, {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["lasso2d", "select2d"],
      toImageButtonOptions: { format: "png", filename: "kyiv-research" },
    }).catch(() => {
      if (active)
        node.textContent = "Графік недоступний. Дані наведено у звітах.";
    });
    const observer = new ResizeObserver(() => Plotly.Plots.resize(node));
    observer.observe(node);
    return () => {
      active = false;
      observer.disconnect();
      Plotly.purge(node);
    };
  }, [data, ylabel]);
  return (
    <article className="chart-card">
      <h3>{title}</h3>
      <div ref={ref} role="img" aria-label={title} />
      {description && <p className="caption">{description}</p>}
    </article>
  );
}
