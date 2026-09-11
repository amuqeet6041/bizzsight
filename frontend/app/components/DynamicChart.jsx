"use client";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

import {
  toFinite,
  formatCompact,
  formatChartValue,
} from "./formatting";

// Generic chart renderer driven entirely by a backend chart_spec object.
// No chart id / metric name is hardcoded here: the spec provides type,
// x_key, series, data and value_format.

const PALETTE = [
  "#34D399",
  "#60A5FA",
  "#FBBF24",
  "#A78BFA",
  "#F472B6",
  "#F87171",
  "#2DD4BF",
  "#FDE047",
];

const AXIS_STROKE = "#6B7280";

const TICK_STYLE = {
  fill: "#9CA3AF",
  fontSize: 11,
};

const TOOLTIP_STYLE = {
  backgroundColor: "#0D1117",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: "12px",
  color: "#fff",
};

const DEFAULT_HEIGHT = 300;

function safeTooltipValue(value) {
  if (value && typeof value === "object" && "value" in value) {
    return value.value;
  }

  return value;
}

export default function DynamicChart({
  spec,
  height = DEFAULT_HEIGHT,
}) {
  console.log(
  "[CHART FRONTEND]",
  spec?.id,
  "xKey:",
  spec?.x_key,
  "type:",
  spec?.type,
  "series:",
  spec?.series,
  "data:",
  JSON.stringify(spec?.data)
);

if (spec?.id === "revenue_trend") {
  console.log(
    "[REVENUE TREND FULL SPEC]",
    JSON.stringify(spec, null, 2)
  );
}

  if (!spec) {
    return <EmptyChart height={height} />;
  }

  const rawData = Array.isArray(spec.data) ? spec.data : [];

  const xKey = spec.x_key || "name";

  const series = Array.isArray(spec.series)
    ? spec.series
    : [];

  const valueKey = series[0]?.key || "value";

  const format = spec.value_format || "";

  const isPercent = format === "percent";

  const isPie =
    spec.type === "pie" ||
    spec.type === "donut";

  // Remove rows that do not contain usable chart data.
  const chartData = isPie
    ? rawData.filter(
        (row) =>
          row &&
          toFinite(row[valueKey]) !== null
      )
    : rawData.filter(
        (row) =>
          row &&
          row[xKey] !== null &&
          row[xKey] !== undefined
      );

  if (chartData.length === 0) {
    return <EmptyChart height={height} />;
  }

  const tooltipFormatter = (value) => {
    const raw = safeTooltipValue(value);

    const num = toFinite(raw);

    if (num === null) {
      return isPercent
        ? ""
        : formatChartValue(raw, format);
    }

    if (isPercent) {
      return `${(num * 100).toFixed(1)}%`;
    }

    return formatChartValue(num, format);
  };

  const axisTickFormatter = (value) => {
    const num = toFinite(value);

    if (num === null) {
      return "";
    }

    if (isPercent) {
      return `${Math.round(num * 100)}%`;
    }

    return formatCompact(num);
  };

  const commonMargin = {
    top: 10,
    right: 20,
    left: 0,
    bottom: 5,
  };

  const axisProps = {
    stroke: AXIS_STROKE,
    tick: TICK_STYLE,
  };

  let chart = null;

  // --------------------------------------------------
  // LINE / AREA CHART
  // --------------------------------------------------

  if (
    spec.type === "line" ||
    spec.type === "area"
  ) {
    const ChartComponent =
      spec.type === "area"
        ? AreaChart
        : LineChart;

    chart = (
      <ChartComponent
        data={chartData}
        margin={commonMargin}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(255,255,255,0.06)"
        />

        <XAxis
          dataKey={xKey}
          stroke={axisProps.stroke}
          tick={axisProps.tick}
          interval="preserveStartEnd"
          minTickGap={20}
        />

        <YAxis
          stroke={axisProps.stroke}
          tick={axisProps.tick}
          tickFormatter={axisTickFormatter}
          width={60}
        />

        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={tooltipFormatter}
        />

        {series.length > 1 && <Legend />}

        {series.map((s, index) => {
          const dashed = s.dashed === true;

          const props = {
            type: "monotone",
            dataKey: s.key,
            name: s.label || s.key,
            stroke:
              PALETTE[
                index % PALETTE.length
              ],
            strokeWidth: dashed ? 2 : 3,
            strokeDasharray: dashed
              ? "5 5"
              : undefined,
            dot: dashed
              ? false
              : { r: 6 },
            activeDot: dashed
              ? false
              : { r: 7 },
          };

          return spec.type === "area" ? (
            <Area
              key={s.key}
              {...props}
              fill={
                PALETTE[
                  index % PALETTE.length
                ]
              }
              fillOpacity={
                dashed ? 0 : 0.15
              }
            />
          ) : (
            <Line
              key={s.key}
              {...props}
            />
          );
        })}
      </ChartComponent>
    );
  }

  // --------------------------------------------------
  // BAR CHART
  // --------------------------------------------------

  else if (spec.type === "bar") {
    chart = (
      <BarChart
        data={chartData}
        margin={commonMargin}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(255,255,255,0.06)"
        />

        <XAxis
          dataKey={xKey}
          stroke={axisProps.stroke}
          tick={axisProps.tick}
          interval="preserveStartEnd"
          minTickGap={20}
        />

        <YAxis
          stroke={axisProps.stroke}
          tick={axisProps.tick}
          tickFormatter={axisTickFormatter}
          width={60}
        />

        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={tooltipFormatter}
        />

        {series.length > 1 && <Legend />}

        {series.map((s, index) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label || s.key}
            fill={
              PALETTE[
                index % PALETTE.length
              ]
            }
            radius={[6, 6, 0, 0]}
          />
        ))}
      </BarChart>
    );
  }

  // --------------------------------------------------
  // PIE / DONUT CHART
  // --------------------------------------------------

  else if (isPie) {
    chart = (
      <PieChart>
        <Pie
          data={chartData}
          dataKey={valueKey}
          nameKey={xKey}
          innerRadius={
            spec.type === "donut"
              ? "55%"
              : 0
          }
          outerRadius="80%"
          paddingAngle={
            spec.type === "donut"
              ? 3
              : 0
          }
          stroke="none"
        >
          {chartData.map(
            (row, index) => (
              <Cell
                key={index}
                fill={
                  PALETTE[
                    index %
                      PALETTE.length
                  ]
                }
              />
            )
          )}
        </Pie>

        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={tooltipFormatter}
        />

        <Legend />
      </PieChart>
    );
  }

  // --------------------------------------------------
  // UNKNOWN CHART TYPE
  // --------------------------------------------------

  else {
    return (
      <EmptyChart
        height={height}
      />
    );
  }

  // --------------------------------------------------
  // RESPONSIVE CONTAINER
  // --------------------------------------------------

  return (
    <div
      className="w-full"
      style={{ height }}
    >
      <ResponsiveContainer
        width="100%"
        height="100%"
      >
        {chart}
      </ResponsiveContainer>
    </div>
  );
}

// --------------------------------------------------
// EMPTY CHART
// --------------------------------------------------

export function EmptyChart({
  height = DEFAULT_HEIGHT,
}) {
  return (
    <div
      className="w-full flex items-center justify-center text-gray-500 text-sm"
      style={{ height }}
    >
      No visualizations are available
      for this dataset.
    </div>
  );
}