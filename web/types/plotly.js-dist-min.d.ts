declare module "plotly.js-dist-min" {
  type PlotlyData = {
    x?: Array<number | string>;
    y?: Array<number | string>;
    z?: Array<number | string>;
    text?: string[];
    mode?: string;
    type?: string;
    marker?: Record<string, unknown>;
    hovertemplate?: string;
  };

  type PlotlyLayout = Record<string, unknown>;
  type PlotlyConfig = Record<string, unknown>;

  export function newPlot(
    element: HTMLElement,
    data: PlotlyData[],
    layout?: PlotlyLayout,
    config?: PlotlyConfig,
  ): Promise<unknown>;

  export function purge(element: HTMLElement): void;
}
