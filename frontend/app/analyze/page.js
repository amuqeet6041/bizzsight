"use client";

import { useState } from "react";
import Link from "next/link";

import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";

export default function AnalyzePage() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  const [step, setStep] = useState("upload");

  const [mappingData, setMappingData] = useState(null);
  const [mapping, setMapping] = useState({});

  const [resultData, setResultData] = useState(null);
  const [analysisTab, setAnalysisTab] = useState("numerical");

  const [dateRange, setDateRange] = useState("all");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [groupBy, setGroupBy] = useState("monthly");
  const [compare, setCompare] = useState("none");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // --------------------------------------------------
  // FILE VALIDATION
  // --------------------------------------------------

  const isValidFile = (selectedFile) => {
    if (!selectedFile) return false;

    const validExtensions = [".csv", ".xls", ".xlsx"];

    return validExtensions.some((extension) =>
      selectedFile.name.toLowerCase().endsWith(extension)
    );
  };

  // --------------------------------------------------
  // FILE SELECTION
  // --------------------------------------------------

  const handleFileSelect = (selectedFile) => {
    setError("");

    if (!selectedFile) return;

    if (!isValidFile(selectedFile)) {
      setError("Please upload a CSV, XLS, or XLSX file.");
      return;
    }

    setFile(selectedFile);
  };

  const handleInputChange = (event) => {
    const selectedFile = event.target.files?.[0];

    if (selectedFile) {
      handleFileSelect(selectedFile);
    }
  };

  // --------------------------------------------------
  // DRAG & DROP
  // --------------------------------------------------

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (event) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0];

    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  // --------------------------------------------------
  // SUGGEST MAPPING
  // --------------------------------------------------

  const handleContinueToMapping = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();

      formData.append("file", file);

      const response = await fetch("/api/suggest-mapping", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.details ||
            data?.error ||
            "Unable to analyze the uploaded file."
        );
      }

      setMappingData(data);

      // Build initial mapping from backend suggestions
      const initialMapping = {};

      Object.entries(data.suggestions || {}).forEach(
        ([column, suggestion]) => {
          initialMapping[column] = suggestion?.suggested_field || "";
        }
      );

      setMapping(initialMapping);

      setStep("mapping");
    } catch (err) {
      console.error("MAPPING ERROR:", err);

      setError(
        err?.message ||
          "Something went wrong while reading your file."
      );
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------
  // MAPPING CHANGE
  // --------------------------------------------------

  const handleMappingChange = (column, field) => {
    setMapping((previous) => ({
      ...previous,
      [column]: field,
    }));
  };

  // --------------------------------------------------
  // PROCESS DATA
  // --------------------------------------------------

  const handleProcess = async () => {
    if (!file) {
      setError("No file selected.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const confirmedMapping = {};

      Object.entries(mapping).forEach(([column, field]) => {
        if (field) {
          confirmedMapping[column] = field;
        }
      });

      const formData = new FormData();

      formData.append("file", file);

      formData.append(
        "mapping",
        JSON.stringify(confirmedMapping)
      );

      const response = await fetch("/api/process", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data?.details ||
            data?.error ||
            "Unable to process your data."
        );
      }

      console.log("PROCESS RESULT:", data);

      setResultData(data);

      setStep("results");
    } catch (err) {
      console.error("PROCESS ERROR:", err);

      setError(
        err?.message ||
          "Something went wrong while processing your data."
      );
    } finally {
      setLoading(false);
    }
  };

  // --------------------------------------------------
  // RESET
  // --------------------------------------------------

  const handleStartOver = () => {
    setFile(null);
    setMappingData(null);
    setMapping({});
    setResultData(null);
    setError("");
    setStep("upload");
    setAnalysisTab("numerical");
    setDateRange("all");
    setCustomStart("");
    setCustomEnd("");
    setGroupBy("monthly");
    setCompare("none");
  };

  // --------------------------------------------------
  // DOWNLOAD EXCEL
  // --------------------------------------------------

  const handleDownloadExcel = () => {
    if (!resultData?.excel_file_base64) {
      setError("Excel file is not available.");
      return;
    }

    try {
      const byteCharacters = atob(
        resultData.excel_file_base64
      );

      const byteNumbers = new Array(
        byteCharacters.length
      );

      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }

      const byteArray = new Uint8Array(byteNumbers);

      const blob = new Blob([byteArray], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });

      const url = URL.createObjectURL(blob);

      const link = document.createElement("a");

      link.href = url;
      link.download = "BizSight_Analysis.xlsx";

      document.body.appendChild(link);

      link.click();

      document.body.removeChild(link);

      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("DOWNLOAD ERROR:", err);

      setError("Unable to download the Excel file.");
    }
  };

  // --------------------------------------------------
  // CHART HELPERS & DERIVED DATA
  // --------------------------------------------------

  const toNumber = (value) => {
    const num = Number(value);

    return Number.isFinite(num) ? num : 0;
  };

  const hasChartData = (data, keys = []) => {
    if (!Array.isArray(data) || data.length === 0) return false;

    if (keys.length === 0) return true;

    return data.some((record) =>
      keys.some((key) => toNumber(record[key]) !== 0)
    );
  };

  const formatCompact = (value) => {
    const num = Number(value);

    if (!Number.isFinite(num)) return "";

    if (Math.abs(num) >= 1000000) {
      return `${(num / 1000000).toFixed(1)}M`;
    }

    if (Math.abs(num) >= 1000) {
      return `${(num / 1000).toFixed(1)}K`;
    }

    return `${Math.round(num)}`;
  };

  const formatPercentTick = (value) => `${Math.round(value)}%`;

  const tooltipStyle = {
    backgroundColor: "#0D1117",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: "12px",
    color: "#fff",
  };

  // ==================================================
  // DATE FILTERING & TIME-SERIES AGGREGATION
  // ==================================================

  const hasDateData =
    Array.isArray(resultData?.daily_timeline) &&
    resultData.daily_timeline.length > 0 &&
    resultData?.date_range?.min &&
    resultData?.date_range?.max;

  const parseISO = (value) => {
    if (!value) return null;
    const text = String(value);
    const date = new Date(
      text.length === 10 ? `${text}T00:00:00` : text
    );
    return Number.isNaN(date.getTime()) ? null : date;
  };

  const toISOString = (date) => {
    if (!date || Number.isNaN(date.getTime())) return null;
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  };

  const addDaysTo = (date, days) => {
    const copy = new Date(date);
    copy.setDate(copy.getDate() + days);
    return copy;
  };

  const addMonthsTo = (date, months) => {
    const copy = new Date(date);
    copy.setMonth(copy.getMonth() + months);
    return copy;
  };

  const startOfMonthTo = (date) =>
    new Date(date.getFullYear(), date.getMonth(), 1);

  const startOfQuarterTo = (date) => {
    const quarterMonth = Math.floor(date.getMonth() / 3) * 3;
    return new Date(date.getFullYear(), quarterMonth, 1);
  };

  const clampDate = (date, min, max) =>
    Math.min(
      Math.max(date.getTime(), min.getTime()),
      max.getTime()
    );

  const datasetStart = parseISO(resultData?.date_range?.min);
  const datasetEnd = parseISO(resultData?.date_range?.max);

  const getRangeBounds = () => {
    if (!hasDateData || !datasetStart || !datasetEnd)
      return null;

    let start;
    let end;

    switch (dateRange) {
      case "all":
        return { start: datasetStart, end: datasetEnd };
      case "today":
        start = datasetEnd;
        end = datasetEnd;
        break;
      case "yesterday": {
        const yesterday = addDaysTo(datasetEnd, -1);
        start = yesterday;
        end = yesterday;
        break;
      }
      case "last_7":
        start = addDaysTo(datasetEnd, -6);
        end = datasetEnd;
        break;
      case "last_30":
        start = addDaysTo(datasetEnd, -29);
        end = datasetEnd;
        break;
      case "last_90":
        start = addDaysTo(datasetEnd, -89);
        end = datasetEnd;
        break;
      case "this_month":
        start = startOfMonthTo(datasetEnd);
        end = datasetEnd;
        break;
      case "last_month": {
        const monthStart = startOfMonthTo(datasetEnd);
        start = addMonthsTo(monthStart, -1);
        end = addDaysTo(monthStart, -1);
        break;
      }
      case "this_quarter":
        start = startOfQuarterTo(datasetEnd);
        end = datasetEnd;
        break;
      case "last_quarter": {
        const quarterStart = startOfQuarterTo(datasetEnd);
        start = addMonthsTo(quarterStart, -3);
        end = addDaysTo(quarterStart, -1);
        break;
      }
      case "this_year":
        start = new Date(datasetEnd.getFullYear(), 0, 1);
        end = datasetEnd;
        break;
      case "last_year":
        start = new Date(datasetEnd.getFullYear() - 1, 0, 1);
        end = new Date(datasetEnd.getFullYear(), 0, 0);
        break;
      case "custom": {
        const customStartDate = parseISO(customStart);
        const customEndDate = parseISO(customEnd);
        if (!customStartDate || !customEndDate) return null;
        start = customStartDate;
        end = customEndDate;
        break;
      }
      default:
        return { start: datasetStart, end: datasetEnd };
    }

    start = new Date(clampDate(start, datasetStart, datasetEnd));
    end = new Date(clampDate(end, datasetStart, datasetEnd));

    if (start.getTime() > end.getTime()) {
      [start, end] = [end, start];
    }

    return { start, end };
  };

  const filterRowsByRange = (rows = [], range) =>
    rows.filter((record) => {
      const date = parseISO(record.date);
      if (!date) return false;
      return (
        date.getTime() >= range.start.getTime() &&
        date.getTime() <= range.end.getTime()
      );
    });

  const computePrevRange = () => {
    const range = getRangeBounds();
    if (!range || compare === "none") return null;

    if (compare === "previous_year") {
      const prevStart = new Date(
        range.start.getFullYear() - 1,
        range.start.getMonth(),
        range.start.getDate()
      );
      const prevEnd = new Date(
        range.end.getFullYear() - 1,
        range.end.getMonth(),
        range.end.getDate()
      );
      return { start: prevStart, end: prevEnd };
    }

    const spanDays =
      Math.round(
        (range.end.getTime() - range.start.getTime()) /
          86400000
      ) + 1;
    const prevEnd = addDaysTo(range.start, -1);
    const prevStart = addDaysTo(prevEnd, -(spanDays - 1));
    return { start: prevStart, end: prevEnd };
  };

  const bucketKeyOf = (dateText, mode) => {
    const date = parseISO(dateText);
    if (!date) return null;

    if (mode === "weekly") {
      const offset = (date.getDay() + 6) % 7;
      return toISOString(addDaysTo(date, -offset));
    }

    if (mode === "monthly") {
      return `${date.getFullYear()}-${String(
        date.getMonth() + 1
      ).padStart(2, "0")}`;
    }

    if (mode === "quarterly") {
      return `${date.getFullYear()}-Q${
        Math.floor(date.getMonth() / 3) + 1
      }`;
    }

    if (mode === "yearly") {
      return `${date.getFullYear()}`;
    }

    return toISOString(date);
  };

  const bucketLabelOf = (key, mode) => {
    if (mode === "daily" || mode === "weekly") {
      const date = parseISO(key);
      return date
        ? date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })
        : key;
    }

    if (mode === "monthly") {
      const [year, month] = key.split("-");
      const date = new Date(Number(year), Number(month) - 1, 1);
      return date.toLocaleDateString(undefined, {
        month: "short",
        year: "2-digit",
      });
    }

    if (mode === "quarterly") {
      const [year, quarter] = key.split("-Q");
      return `Q${quarter} '${year.slice(2)}`;
    }

    if (mode === "yearly") return key;

    return key;
  };

  const buildSeries = (rows = [], mode = groupBy) => {
    const buckets = new Map();

    rows.forEach((record) => {
      const key = bucketKeyOf(record.date, mode);
      if (!key) return;

      const bucket = buckets.get(key) || {
        revenue: 0,
        cogs: 0,
        shipping: 0,
        marketing: 0,
        orders: 0,
      };
      bucket.revenue += toNumber(record.revenue);
      bucket.cogs += toNumber(record.cogs);
      bucket.shipping += toNumber(record.shipping);
      bucket.marketing += toNumber(record.marketing);
      bucket.orders += toNumber(record.orders);
      buckets.set(key, bucket);
    });

    const keys = Array.from(buckets.keys()).sort();

    return keys.map((key) => {
      const bucket = buckets.get(key);
      const grossProfit =
        bucket.revenue - bucket.cogs - bucket.shipping;
      const netProfit = grossProfit - bucket.marketing;

      return {
        month: bucketLabelOf(key, mode),
        revenue: bucket.revenue,
        cogs: bucket.cogs,
        shipping: bucket.shipping,
        marketing: bucket.marketing,
        gross_profit: grossProfit,
        net_profit: netProfit,
        orders: bucket.orders,
      };
    });
  };

  const mergeComparisonSeries = (current, previous) => {
    if (!previous || previous.length === 0) return current;

    return current.map((record, index) => {
      const prev = previous[index] || {};
      const prevRevenue = toNumber(prev.revenue);
      const prevGross = toNumber(prev.gross_profit);
      const prevNet = toNumber(prev.net_profit);
      const prevOrders = toNumber(prev.orders);

      return {
        ...record,
        prev_revenue: prevRevenue,
        prev_cogs: toNumber(prev.cogs),
        prev_shipping: toNumber(prev.shipping),
        prev_marketing: toNumber(prev.marketing),
        prev_gross_profit: prevGross,
        prev_net_profit: prevNet,
        prev_orders: prevOrders,
        prev_gross_margin:
          prevRevenue > 0
            ? (prevGross / prevRevenue) * 100
            : null,
        prev_net_margin:
          prevRevenue > 0
            ? (prevNet / prevRevenue) * 100
            : null,
        prev_aov:
          prevOrders > 0 ? prevRevenue / prevOrders : null,
      };
    });
  };

  const activeSeries = (() => {
    const range = getRangeBounds();
    if (!range || !hasDateData)
      return { current: [], previous: null };

    const current = buildSeries(
      filterRowsByRange(resultData.daily_timeline, range),
      groupBy
    );

    let previous = null;
    const prevRange = computePrevRange();
    if (prevRange) {
      const prevSeries = buildSeries(
        filterRowsByRange(resultData.daily_timeline, prevRange),
        groupBy
      );
      if (prevSeries.length > 0) previous = prevSeries;
    }

    return { current, previous };
  })();

  const compareEnabled =
    hasDateData &&
    compare !== "none" &&
    activeSeries.previous &&
    activeSeries.previous.length > 0;

  const prevSeriesLabel =
    compare === "previous_year"
      ? "Previous Year"
      : "Previous Period";

  const revenueTrend = hasDateData
    ? mergeComparisonSeries(
        activeSeries.current,
        activeSeries.previous
      )
    : resultData?.chart_data?.revenue_trend || [];

  const ordersTrend = revenueTrend.map((record) => ({
    month: record.month,
    orders: record.orders,
    prev_orders: record.prev_orders,
  }));

  const grossMarginData = revenueTrend.map((record) => ({
    month: record.month,
    gross_margin:
      toNumber(record.revenue) > 0
        ? (toNumber(record.gross_profit) /
            toNumber(record.revenue)) *
          100
        : null,
    prev_gross_margin: record.prev_gross_margin ?? null,
  }));

  const netMarginData = revenueTrend.map((record) => ({
    month: record.month,
    net_margin:
      toNumber(record.revenue) > 0
        ? (toNumber(record.net_profit) /
            toNumber(record.revenue)) *
          100
        : null,
    prev_net_margin: record.prev_net_margin ?? null,
  }));

  const aovData = revenueTrend.map((record) => ({
    month: record.month,
    aov:
      toNumber(record.orders) > 0
        ? toNumber(record.revenue) / toNumber(record.orders)
        : null,
    prev_aov: record.prev_aov ?? null,
  }));

  const costTotals = revenueTrend.reduce(
    (totals, record) => {
      totals.cogs += toNumber(record.cogs);
      totals.shipping += toNumber(record.shipping);
      totals.marketing += toNumber(record.marketing);

      return totals;
    },
    { cogs: 0, shipping: 0, marketing: 0 }
  );

  const totalCosts =
    costTotals.cogs +
    costTotals.shipping +
    costTotals.marketing;

  const costCompositionData = [
    {
      name: "COGS",
      value: costTotals.cogs,
      color: "#FBBF24",
    },
    {
      name: "Shipping",
      value: costTotals.shipping,
      color: "#60A5FA",
    },
    {
      name: "Marketing",
      value: costTotals.marketing,
      color: "#F472B6",
    },
  ];

  // ==================================================
  // PERIOD METRICS, COMPARISON & KPI VALUES
  // ==================================================

  const sumRows = (rows = []) =>
    rows.reduce(
      (totals, record) => {
        totals.revenue += toNumber(record.revenue);
        totals.cogs += toNumber(record.cogs);
        totals.shipping += toNumber(record.shipping);
        totals.marketing += toNumber(record.marketing);
        totals.orders += toNumber(record.orders);
        totals.cancelled += toNumber(record.cancelled);
        return totals;
      },
      {
        revenue: 0,
        cogs: 0,
        shipping: 0,
        marketing: 0,
        orders: 0,
        cancelled: 0,
      }
    );

  const rangeBounds = getRangeBounds();

  const periodTotals =
    hasDateData && rangeBounds
      ? sumRows(
          filterRowsByRange(
            resultData.daily_timeline,
            rangeBounds
          )
        )
      : null;

  const prevTotals = (() => {
    if (!hasDateData) return null;
    const prevRange = computePrevRange();
    if (!prevRange) return null;
    return sumRows(
      filterRowsByRange(resultData.daily_timeline, prevRange)
    );
  })();

  const deriveTotals = (totals) => {
    if (!totals) return null;
    const grossProfit =
      totals.revenue - totals.cogs - totals.shipping;
    return {
      revenue: totals.revenue,
      cogs: totals.cogs,
      shipping: totals.shipping,
      marketing: totals.marketing,
      orders: totals.orders,
      cancelled: totals.cancelled,
      gross_profit: grossProfit,
      net_profit: grossProfit - totals.marketing,
      aov: totals.orders > 0 ? totals.revenue / totals.orders : 0,
      return_rate:
        totals.orders + totals.cancelled > 0
          ? totals.cancelled /
            (totals.orders + totals.cancelled)
          : 0,
    };
  };

  const periodDerived = deriveTotals(periodTotals);
  const previousDerived = deriveTotals(prevTotals);

  const deltaOf = (
    currentValue,
    previousValue,
    lowerIsBetter = false
  ) => {
    if (
      previousValue == null ||
      previousValue === 0 ||
      currentValue == null
    ) {
      return null;
    }
    const pct =
      ((currentValue - previousValue) /
        Math.abs(previousValue)) *
      100;
    return { pct, good: lowerIsBetter ? pct <= 0 : pct >= 0 };
  };

  const compareAvailable =
    hasDateData &&
    compare !== "none" &&
    previousDerived &&
    previousDerived.orders > 0;

  const deltaRevenue = compareAvailable
    ? deltaOf(periodDerived.revenue, previousDerived.revenue)
    : null;

  const deltaGrossProfit = compareAvailable
    ? deltaOf(
        periodDerived.gross_profit,
        previousDerived.gross_profit
      )
    : null;

  const deltaNetProfit = compareAvailable
    ? deltaOf(
        periodDerived.net_profit,
        previousDerived.net_profit
      )
    : null;

  const deltaOrders = compareAvailable
    ? deltaOf(periodDerived.orders, previousDerived.orders)
    : null;

  const deltaAov = compareAvailable
    ? deltaOf(periodDerived.aov, previousDerived.aov)
    : null;

  const deltaReturnRate = compareAvailable
    ? deltaOf(
        periodDerived.return_rate,
        previousDerived.return_rate,
        true
      )
    : null;

  const formatMoney = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return "N/A";
    return `$${num.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formatPercent = (value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return "N/A";
    return `${(num * 100).toFixed(1)}%`;
  };

  const analyzeCustomersForRange = (
    rows,
    firstOrders,
    start,
    end
  ) => {
    const customers = new Map();

    rows.forEach((record) => {
      const existing = customers.get(record.customer) || {
        customer: record.customer,
        revenue: 0,
        orders: 0,
      };
      existing.revenue += toNumber(record.revenue);
      existing.orders += toNumber(record.orders);
      customers.set(record.customer, existing);
    });

    const list = Array.from(customers.values()).sort(
      (a, b) => b.revenue - a.revenue
    );

    const newCustomers = list.filter((row) => {
      const first = parseISO(firstOrders[row.customer]);
      return (
        first &&
        first.getTime() >= start.getTime() &&
        first.getTime() <= end.getTime()
      );
    }).length;

    return {
      totalCustomers: list.length,
      repeatCustomers: list.filter((row) => row.orders > 1)
        .length,
      newCustomers,
      returningCustomers: list.length - newCustomers,
      repeatRate:
        list.length > 0
          ? list.filter((row) => row.orders > 1).length /
            list.length
          : null,
      topCustomer: list[0] || null,
      totalRevenue: list.reduce(
        (sum, row) => sum + row.revenue,
        0
      ),
      top5: list.slice(0, 5),
    };
  };

  const customerAnalysis =
    hasDateData &&
    resultData?.customer_data?.available &&
    rangeBounds
      ? analyzeCustomersForRange(
          filterRowsByRange(
            resultData.customer_data.rows || [],
            rangeBounds
          ),
          resultData.customer_data.first_orders || {},
          rangeBounds.start,
          rangeBounds.end
        )
      : null;

  const previousCustomerAnalysis = (() => {
    if (
      !hasDateData ||
      !resultData?.customer_data?.available
    )
      return null;
    const prevRange = computePrevRange();
    if (!prevRange) return null;
    return analyzeCustomersForRange(
      filterRowsByRange(
        resultData.customer_data.rows || [],
        prevRange
      ),
      resultData.customer_data.first_orders || {},
      prevRange.start,
      prevRange.end
    );
  })();

  const kpiCac =
    hasDateData
      ? customerAnalysis &&
        customerAnalysis.newCustomers > 0 &&
        periodDerived &&
        periodDerived.marketing > 0
        ? formatMoney(
            periodDerived.marketing /
              customerAnalysis.newCustomers
          )
        : "N/A"
      : resultData?.display_metrics?.CAC ?? "N/A";

  const deltaCac =
    compareAvailable &&
    kpiCac !== "N/A" &&
    previousCustomerAnalysis &&
    previousCustomerAnalysis.newCustomers > 0
      ? deltaOf(
          periodDerived.marketing /
            customerAnalysis.newCustomers,
          previousDerived.marketing /
            previousCustomerAnalysis.newCustomers,
          true
        )
      : null;

  const kpiRepeatRate =
    hasDateData
      ? customerAnalysis && customerAnalysis.repeatRate != null
        ? formatPercent(customerAnalysis.repeatRate)
        : "N/A"
      : resultData?.display_metrics?.["Repeat Purchase Rate"] ??
        "N/A";

  const deltaRepeatRate =
    compareAvailable &&
    customerAnalysis &&
    customerAnalysis.repeatRate != null &&
    previousCustomerAnalysis &&
    previousCustomerAnalysis.repeatRate != null
      ? deltaOf(
          customerAnalysis.repeatRate,
          previousCustomerAnalysis.repeatRate
        )
      : null;

  const kpiReturnRate =
    hasDateData && periodDerived
      ? formatPercent(periodDerived.return_rate)
      : resultData?.display_metrics?.["Return/Cancel Rate"] ??
        "N/A";

  const kpiCards = [
    {
      label: "Revenue",
      value:
        hasDateData && periodDerived
          ? formatMoney(periodDerived.revenue)
          : resultData?.display_metrics?.Revenue ?? "N/A",
      description: "Total Sales",
      positive: true,
      delta: deltaRevenue,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Gross Profit",
      value:
        hasDateData && periodDerived
          ? formatMoney(periodDerived.gross_profit)
          : resultData?.display_metrics?.["Gross Profit"] ?? "N/A",
      description: "Before Marketing",
      positive: true,
      delta: deltaGrossProfit,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Net Profit",
      value:
        hasDateData && periodDerived
          ? formatMoney(periodDerived.net_profit)
          : resultData?.display_metrics?.["Net Profit"] ?? "N/A",
      description: "After Marketing",
      positive: true,
      delta: deltaNetProfit,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Orders",
      value:
        hasDateData && periodDerived
          ? periodDerived.orders.toLocaleString()
          : resultData?.display_metrics?.Orders ?? "N/A",
      description: "Completed Orders",
      positive: true,
      delta: deltaOrders,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Average Order Value",
      value:
        hasDateData && periodDerived
          ? formatMoney(periodDerived.aov)
          : resultData?.display_metrics?.AOV ?? "N/A",
      description: "Revenue per Order",
      delta: deltaAov,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Customer Acquisition Cost",
      value: kpiCac,
      description: "Cost per New Customer",
      delta: deltaCac,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Return / Cancel Rate",
      value: kpiReturnRate,
      description: "Cancelled / Returned",
      delta: deltaReturnRate,
      deltaLabel: prevSeriesLabel,
    },
    {
      label: "Repeat Purchase Rate",
      value: kpiRepeatRate,
      description: "Returning Customers",
      delta: deltaRepeatRate,
      deltaLabel: prevSeriesLabel,
    },
  ];

  // ==================================================
  // CUSTOMER & PRODUCT ANALYSIS (for selected period)
  // ==================================================

  const productAnalysis = (() => {
    if (!hasDateData || !resultData?.product_data?.available || !rangeBounds)
      return null;

    const rows = filterRowsByRange(
      resultData.product_data.rows || [],
      rangeBounds
    );
    const hasQuantity = Boolean(
      resultData.product_data.has_quantity
    );
    const products = new Map();

    rows.forEach((record) => {
      const existing = products.get(record.product) || {
        product: record.product,
        revenue: 0,
        units: 0,
        orders: 0,
      };
      existing.revenue += toNumber(record.revenue);
      existing.units += toNumber(record.units);
      existing.orders += toNumber(record.orders);
      products.set(record.product, existing);
    });

    const list = Array.from(products.values()).sort(
      (a, b) => b.revenue - a.revenue
    );
    const byVolume = [...list].sort(
      (a, b) =>
        (hasQuantity ? b.units : b.orders) -
        (hasQuantity ? a.units : a.orders)
    );

    return {
      hasQuantity,
      totalProducts: list.length,
      topByRevenue: list[0] || null,
      bestSeller: byVolume[0] || null,
      totalRevenue: list.reduce(
        (sum, row) => sum + row.revenue,
        0
      ),
      totalUnits: list.reduce(
        (sum, row) => sum + row.units,
        0
      ),
      totalOrders: list.reduce(
        (sum, row) => sum + row.orders,
        0
      ),
      top5: list.slice(0, 5),
    };
  })();

  const customerChartData = (
    customerAnalysis?.top5 || []
  ).map((row) => {
    const name =
      row.customer.length > 16
        ? `${row.customer.slice(0, 16)}…`
        : row.customer;
    return { name, revenue: row.revenue };
  });

  const productChartData = (productAnalysis?.top5 || []).map(
    (row) => {
      const name =
        row.product.length > 16
          ? `${row.product.slice(0, 16)}…`
          : row.product;
      return { name, revenue: row.revenue };
    }
  );

  // ==================================================
  // RANGE LABEL & BUSINESS INSIGHTS
  // ==================================================

  const formatRangeLabel = (range) => {
    if (!range) return "";
    const fmt = (date) =>
      date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    if (dateRange === "all") {
      return `${fmt(datasetStart)} – ${fmt(datasetEnd)}`;
    }
    return `${fmt(range.start)} – ${fmt(range.end)}`;
  };

  const businessInsights = (() => {
    if (!hasDateData || !periodDerived) {
      return resultData?.insights || [];
    }

    const notes = [];

    if (periodDerived.net_profit < 0) {
      notes.push(
        "⚠️ Net profit is negative for this period — total costs currently exceed revenue."
      );
    }

    const cacValue =
      customerAnalysis && customerAnalysis.newCustomers > 0
        ? periodDerived.marketing / customerAnalysis.newCustomers
        : null;

    if (
      cacValue != null &&
      periodDerived.aov > 0 &&
      cacValue > periodDerived.aov
    ) {
      notes.push(
        "⚠️ Customer Acquisition Cost (CAC) is higher than Average Order Value (AOV) in this period — acquiring new customers may be unprofitable on a per-order basis."
      );
    }

    if (periodDerived.return_rate > 0.15) {
      notes.push(
        `⚠️ Return/Cancel rate is ${formatPercent(
          periodDerived.return_rate
        )} in this period, which is high for eCommerce — consider product quality or delivery issues.`
      );
    }

    if (deltaRevenue && Math.abs(deltaRevenue.pct) >= 1) {
      notes.push(
        deltaRevenue.pct > 0
          ? `✅ Revenue is up ${deltaRevenue.pct.toFixed(
              1
            )}% compared to ${prevSeriesLabel.toLowerCase()}.`
          : `⚠️ Revenue is down ${Math.abs(
              deltaRevenue.pct
            ).toFixed(1)}% compared to ${prevSeriesLabel.toLowerCase()}.`
      );
    }

    if (deltaOrders && Math.abs(deltaOrders.pct) >= 1) {
      notes.push(
        `📦 Order volume ${
          deltaOrders.pct >= 0 ? "increased" : "decreased"
        } by ${Math.abs(deltaOrders.pct).toFixed(
          1
        )}% compared to ${prevSeriesLabel.toLowerCase()}.`
      );
    }

    if (customerAnalysis) {
      const { topCustomer } = customerAnalysis;
      if (topCustomer && customerAnalysis.totalRevenue > 0) {
        const share =
          topCustomer.revenue / customerAnalysis.totalRevenue;
        notes.push(
          `👤 Top customer "${topCustomer.customer}" contributed ${formatMoney(
            topCustomer.revenue
          )} (${(share * 100).toFixed(
            1
          )}% of selected-period revenue).`
        );
      }

      if (customerAnalysis.repeatRate != null) {
        notes.push(
          `🔁 Repeat purchase rate is ${formatPercent(
            customerAnalysis.repeatRate
          )} — ${
            customerAnalysis.repeatRate >= 0.3
              ? "a healthy share of customers return."
              : "most revenue comes from first-time customers."
          }`
        );
      }
    }

    if (productAnalysis && productAnalysis.bestSeller) {
      const best = productAnalysis.bestSeller;
      const volumeText = productAnalysis.hasQuantity
        ? `${best.units.toLocaleString()} units`
        : `${best.orders.toLocaleString()} orders`;
      notes.push(
        `🏷️ Best seller "${best.product}" moved ${volumeText} worth ${formatMoney(
          best.revenue
        )} in the selected period.`
      );
    }

    if (notes.length === 0) {
      notes.push(
        "✅ No major red flags detected for this period."
      );
    }

    return notes;
  })();

  // --------------------------------------------------
  // PAGE
  // --------------------------------------------------

  return (
    <main className="min-h-screen bg-[#070A0D] text-white">

      {/* --------------------------------------------------
          TOP NAVIGATION
      -------------------------------------------------- */}

      <nav className="h-20 border-b border-white/10 flex items-center">
        <div className="w-full max-w-7xl mx-auto px-6 flex items-center justify-between">

          <Link
            href="/"
            className="text-2xl font-bold tracking-tight"
          >
            Biz<span className="text-emerald-400">Sight</span>
          </Link>

          <Link
            href="/"
            className="text-sm text-gray-400 hover:text-white transition"
          >
            ← Back to Home
          </Link>

        </div>
      </nav>

      {/* --------------------------------------------------
          MAIN CONTENT
      -------------------------------------------------- */}

      <div className="max-w-7xl mx-auto px-6 py-12">

        {/* --------------------------------------------------
            STEP INDICATOR
        -------------------------------------------------- */}

        <div className="flex items-center justify-center mb-12">

          <div className="flex items-center gap-3">

            <StepIndicator
              number="1"
              label="Upload"
              active={step === "upload"}
              completed={
                step === "mapping" ||
                step === "results"
              }
            />

            <div className="w-12 h-px bg-white/10" />

            <StepIndicator
              number="2"
              label="Mapping"
              active={step === "mapping"}
              completed={step === "results"}
            />

            <div className="w-12 h-px bg-white/10" />

            <StepIndicator
              number="3"
              label="Analysis"
              active={step === "results"}
              completed={false}
            />

          </div>

        </div>

        {/* --------------------------------------------------
            ERROR
        -------------------------------------------------- */}

        {error && (
          <div className="max-w-3xl mx-auto mb-6 rounded-xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* ==================================================
            UPLOAD SCREEN
        ================================================== */}

        {step === "upload" && (
          <section className="max-w-3xl mx-auto">

            <div className="text-center mb-10">

              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-emerald-400/10 border border-emerald-400/20 mb-5">
                <span className="text-2xl">
                  ↑
                </span>
              </div>

              <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
                Analyze Your Business
              </h1>

              <p className="text-gray-400 mt-4 max-w-xl mx-auto">
                Upload your business data and let BizSight
                automatically clean, analyze and understand it.
              </p>

            </div>

            {/* Upload Box */}

            <label
              htmlFor="file-upload"
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`block cursor-pointer rounded-3xl border-2 border-dashed p-12 text-center transition ${
                isDragging
                  ? "border-emerald-400 bg-emerald-400/10"
                  : "border-white/10 bg-[#0D1117] hover:border-emerald-400/40"
              }`}
            >

              <input
                id="file-upload"
                type="file"
                accept=".csv,.xls,.xlsx"
                className="hidden"
                onChange={handleInputChange}
              />

              <div className="w-16 h-16 mx-auto rounded-2xl bg-white/5 flex items-center justify-center mb-5">
                <span className="text-3xl">
                  📊
                </span>
              </div>

              {file ? (
                <>
                  <h2 className="text-xl font-semibold">
                    {file.name}
                  </h2>

                  <p className="text-gray-400 mt-2">
                    File selected successfully
                  </p>
                </>
              ) : (
                <>
                  <h2 className="text-xl font-semibold">
                    Drop your file here
                  </h2>

                  <p className="text-gray-400 mt-2">
                    or click to browse from your computer
                  </p>

                  <p className="text-xs text-gray-500 mt-5">
                    Supported formats: CSV, XLS, XLSX
                  </p>
                </>
              )}

            </label>

            {/* Continue Button */}

            <button
              onClick={handleContinueToMapping}
              disabled={!file || loading}
              className="w-full mt-6 rounded-xl bg-emerald-400 px-6 py-4 font-semibold text-black transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading
                ? "Reading Your Data..."
                : "Continue"}
            </button>

          </section>
        )}

        {/* ==================================================
            MAPPING SCREEN
        ================================================== */}

        {step === "mapping" && mappingData && (
          <section>

            <div className="mb-8">

              <div className="flex items-center gap-3 mb-3">
                <div className="w-2 h-2 rounded-full bg-emerald-400" />

                <span className="text-sm font-medium text-emerald-400">
                  DATA MAPPING
                </span>
              </div>

              <h1 className="text-4xl font-bold">
                Confirm Your Columns
              </h1>

              <p className="text-gray-400 mt-3 max-w-2xl">
                BizSight automatically identified your columns.
                Review the suggested mappings before analysis.
              </p>

            </div>

            <div className="rounded-2xl border border-white/10 bg-[#0D1117] overflow-hidden">

              <div className="overflow-x-auto">

                <table className="w-full text-left">

                  <thead className="border-b border-white/10 bg-white/[0.02]">

                    <tr>

                      <th className="px-6 py-4 text-sm font-medium text-gray-400">
                        Your Column
                      </th>

                      <th className="px-6 py-4 text-sm font-medium text-gray-400">
                        BizSight Field
                      </th>

                      <th className="px-6 py-4 text-sm font-medium text-gray-400">
                        Confidence
                      </th>

                    </tr>

                  </thead>

                  <tbody>

                    {Object.entries(
                      mappingData.suggestions || {}
                    ).map(([column, suggestion]) => (

                      <tr
                        key={column}
                        className="border-b border-white/5 last:border-0"
                      >

                        <td className="px-6 py-5">
                          <span className="font-medium">
                            {column}
                          </span>
                        </td>

                        <td className="px-6 py-5">

                          <select
                            value={mapping[column] || ""}
                            onChange={(event) =>
                              handleMappingChange(
                                column,
                                event.target.value
                              )
                            }
                            className="w-full max-w-xs rounded-lg border border-white/10 bg-[#070A0D] px-4 py-3 text-sm text-white outline-none focus:border-emerald-400/50"
                          >

                            <option value="">
                              Ignore this column
                            </option>

                            {(mappingData.standard_fields || []).map(
                              (field) => (
                                <option
                                  key={field}
                                  value={field}
                                >
                                  {field}
                                </option>
                              )
                            )}

                          </select>

                        </td>

                        <td className="px-6 py-5">

                          {suggestion?.confidence ? (
                            <span className="text-emerald-400">
                              {Math.round(
                                suggestion.confidence
                              )}
                              %
                            </span>
                          ) : (
                            <span className="text-gray-500">
                              —
                            </span>
                          )}

                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

              </div>

            </div>

            <div className="flex flex-col sm:flex-row gap-4 mt-6">

              <button
                onClick={() => setStep("upload")}
                className="flex-1 rounded-xl border border-white/10 px-6 py-4 font-medium text-gray-300 hover:bg-white/5 transition"
              >
                ← Back
              </button>

              <button
                onClick={handleProcess}
                disabled={loading}
                className="flex-1 rounded-xl bg-emerald-400 px-6 py-4 font-semibold text-black hover:bg-emerald-300 transition disabled:opacity-40"
              >
                {loading
                  ? "Analyzing Your Data..."
                  : "Analyze My Business →"}
              </button>

            </div>

          </section>
        )}

        {/* ==================================================
            RESULTS SCREEN
        ================================================== */}

        {step === "results" && resultData && (
          <section>

            {/* Header */}

            <div className="mb-10">

              <div className="flex items-center gap-3 mb-3">

                <div className="w-2 h-2 rounded-full bg-emerald-400" />

                <span className="text-sm text-emerald-400 font-medium">
                  ANALYSIS COMPLETE
                </span>

              </div>

              <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-5">

                <div>

                  <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
                    Your Business Analysis
                  </h1>

                  <p className="text-gray-400 mt-3 max-w-2xl">
                    BizSight analyzed your data and generated
                    financial and business insights.
                  </p>

                </div>

                <button
                  onClick={handleStartOver}
                  className="rounded-xl border border-white/10 px-5 py-3 text-sm font-medium text-gray-300 hover:bg-white/5 transition"
                >
                  Analyze Another File
                </button>

              </div>

            </div>

            {/* ==================================================
                ANALYSIS TABS
            ================================================== */}

            <div className="mb-8 inline-flex w-full sm:w-auto flex-col sm:flex-row rounded-xl border border-white/10 bg-[#0D1117] p-1.5 gap-1.5">

              <button
                onClick={() => setAnalysisTab("numerical")}
                className={`flex-1 sm:flex-none rounded-lg px-6 py-2.5 text-sm font-medium transition whitespace-nowrap ${
                  analysisTab === "numerical"
                    ? "bg-emerald-400 text-black"
                    : "text-gray-400 hover:text-white hover:bg-white/5"
                }`}
              >
                Numerical Analysis
              </button>

              <button
                onClick={() => setAnalysisTab("graphical")}
                className={`flex-1 sm:flex-none rounded-lg px-6 py-2.5 text-sm font-medium transition whitespace-nowrap ${
                  analysisTab === "graphical"
                    ? "bg-emerald-400 text-black"
                    : "text-gray-400 hover:text-white hover:bg-white/5"
                }`}
              >
                Graphical Analysis
              </button>

            </div>

            {/* ==================================================
                DATE FILTER BAR
            ================================================== */}

            {hasDateData && (
              <div className="mb-8 rounded-2xl border border-white/10 bg-[#0D1117] p-5">

                <div className="flex flex-wrap items-end gap-4">

                  <FilterField label="Date Range">
                    <select
                      value={dateRange}
                      onChange={(event) =>
                        setDateRange(event.target.value)
                      }
                      className="w-full rounded-lg border border-white/10 bg-[#070A0D] px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/50"
                    >
                      <option value="all">All Time</option>
                      <option value="today">Today</option>
                      <option value="yesterday">Yesterday</option>
                      <option value="last_7">Last 7 Days</option>
                      <option value="last_30">Last 30 Days</option>
                      <option value="last_90">Last 90 Days</option>
                      <option value="this_month">This Month</option>
                      <option value="last_month">Last Month</option>
                      <option value="this_quarter">This Quarter</option>
                      <option value="last_quarter">Last Quarter</option>
                      <option value="this_year">This Year</option>
                      <option value="last_year">Last Year</option>
                      <option value="custom">Custom Range</option>
                    </select>
                  </FilterField>

                  {dateRange === "custom" && (
                    <>
                      <FilterField label="From">
                        <input
                          type="date"
                          value={customStart}
                          min={resultData?.date_range?.min}
                          max={resultData?.date_range?.max}
                          onChange={(event) =>
                            setCustomStart(event.target.value)
                          }
                          className="w-full rounded-lg border border-white/10 bg-[#070A0D] px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/50"
                        />
                      </FilterField>

                      <FilterField label="To">
                        <input
                          type="date"
                          value={customEnd}
                          min={resultData?.date_range?.min}
                          max={resultData?.date_range?.max}
                          onChange={(event) =>
                            setCustomEnd(event.target.value)
                          }
                          className="w-full rounded-lg border border-white/10 bg-[#070A0D] px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/50"
                        />
                      </FilterField>
                    </>
                  )}

                  <FilterField label="Group By">
                    <select
                      value={groupBy}
                      onChange={(event) =>
                        setGroupBy(event.target.value)
                      }
                      className="w-full rounded-lg border border-white/10 bg-[#070A0D] px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/50"
                    >
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="monthly">Monthly</option>
                      <option value="quarterly">Quarterly</option>
                      <option value="yearly">Yearly</option>
                    </select>
                  </FilterField>

                  <FilterField label="Compare">
                    <select
                      value={compare}
                      onChange={(event) =>
                        setCompare(event.target.value)
                      }
                      className="w-full rounded-lg border border-white/10 bg-[#070A0D] px-4 py-2.5 text-sm text-white outline-none focus:border-emerald-400/50"
                    >
                      <option value="none">No Comparison</option>
                      <option value="previous_period">
                        Previous Period
                      </option>
                      <option value="previous_year">
                        Previous Year
                      </option>
                    </select>
                  </FilterField>

                </div>

                <div className="mt-4 text-xs text-gray-500">
                  Showing{" "}
                  <span className="text-gray-300 font-medium">
                    {formatRangeLabel(rangeBounds)}
                  </span>
                  {compareEnabled && (
                    <>
                      {" "}
                      · compared to{" "}
                      <span className="text-gray-300 font-medium">
                        {prevSeriesLabel.toLowerCase()}
                      </span>
                    </>
                  )}
                </div>

              </div>
            )}

            {/* ==================================================
                NUMERICAL ANALYSIS
            ================================================== */}

            {analysisTab === "numerical" && (
              <div>

                {/* ==================================================
                    KPI CARDS
                ================================================== */}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">

                  {kpiCards.map((card) => (
                    <MetricCard
                      key={card.label}
                      label={card.label}
                      value={card.value}
                      description={card.description}
                      positive={card.positive}
                      delta={card.delta}
                      deltaLabel={card.deltaLabel}
                    />
                  ))}

                </div>

                {/* ==================================================
                    FINANCIAL OVERVIEW
                ================================================== */}

                <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">

                  <div className="rounded-2xl border border-white/10 bg-[#0D1117] p-7">

                    <div className="flex items-center justify-between mb-6">

                      <div>

                        <h2 className="text-xl font-semibold">
                          Financial Overview
                        </h2>

                        <p className="text-sm text-gray-500 mt-1">
                          Breakdown of your business finances
                        </p>

                      </div>

                      <span className="text-2xl">
                        ₿
                      </span>

                    </div>

                    <div className="space-y-5">

                      <FinancialRow
                        label="Revenue"
                        value={
                          hasDateData && periodDerived
                            ? formatMoney(periodDerived.revenue)
                            : resultData?.display_metrics?.Revenue ??
                              "N/A"
                        }
                        delta={
                          compareAvailable
                            ? deltaOf(
                                periodDerived.revenue,
                                previousDerived.revenue
                              )
                            : null
                        }
                        deltaLabel={prevSeriesLabel}
                      />

                      <FinancialRow
                        label="COGS"
                        value={
                          hasDateData && periodDerived
                            ? formatMoney(periodDerived.cogs)
                            : resultData?.display_metrics?.COGS ??
                              "N/A"
                        }
                        delta={
                          compareAvailable
                            ? deltaOf(
                                periodDerived.cogs,
                                previousDerived.cogs,
                                true
                              )
                            : null
                        }
                        deltaLabel={prevSeriesLabel}
                      />

                      <FinancialRow
                        label="Shipping Cost"
                        value={
                          hasDateData && periodDerived
                            ? formatMoney(periodDerived.shipping)
                            : resultData?.display_metrics?.[
                                "Shipping Cost"
                              ] ?? "N/A"
                        }
                        delta={
                          compareAvailable
                            ? deltaOf(
                                periodDerived.shipping,
                                previousDerived.shipping,
                                true
                              )
                            : null
                        }
                        deltaLabel={prevSeriesLabel}
                      />

                      <FinancialRow
                        label="Marketing Spend"
                        value={
                          hasDateData && periodDerived
                            ? formatMoney(periodDerived.marketing)
                            : resultData?.display_metrics?.[
                                "Marketing Spend"
                              ] ?? "N/A"
                        }
                        delta={
                          compareAvailable
                            ? deltaOf(
                                periodDerived.marketing,
                                previousDerived.marketing,
                                true
                              )
                            : null
                        }
                        deltaLabel={prevSeriesLabel}
                      />

                      <FinancialRow
                        label="Gross Profit"
                        value={
                          hasDateData && periodDerived
                            ? formatMoney(periodDerived.gross_profit)
                            : resultData?.display_metrics?.[
                                "Gross Profit"
                              ] ?? "N/A"
                        }
                        delta={
                          compareAvailable
                            ? deltaOf(
                                periodDerived.gross_profit,
                                previousDerived.gross_profit
                              )
                            : null
                        }
                        deltaLabel={prevSeriesLabel}
                      />

                      <FinancialRow
                        label="Net Profit"
                        value={
                          hasDateData && periodDerived
                            ? formatMoney(periodDerived.net_profit)
                            : resultData?.display_metrics?.[
                                "Net Profit"
                              ] ?? "N/A"
                        }
                        highlight
                        delta={
                          compareAvailable
                            ? deltaOf(
                                periodDerived.net_profit,
                                previousDerived.net_profit
                              )
                            : null
                        }
                        deltaLabel={prevSeriesLabel}
                      />

                    </div>

                  </div>

                  {/* Cleaning Report */}

                  <div className="rounded-2xl border border-white/10 bg-[#0D1117] p-7">

                    <div className="flex items-center justify-between mb-6">

                      <div>

                        <h2 className="text-xl font-semibold">
                          Data Quality
                        </h2>

                        <p className="text-sm text-gray-500 mt-1">
                          What BizSight found while cleaning your data
                        </p>

                      </div>

                      <span className="text-2xl">
                        ✓
                      </span>

                    </div>

                    <div className="grid grid-cols-2 gap-4">

                      <ReportCard
                        label="Rows Before"
                        value={
                          resultData?.cleaning_report?.rows_before ??
                          "N/A"
                        }
                      />

                      <ReportCard
                        label="Rows After"
                        value={
                          resultData?.cleaning_report?.rows_after ??
                          "N/A"
                        }
                      />

                      <ReportCard
                        label="Duplicates Removed"
                        value={
                          resultData?.cleaning_report
                            ?.dropped_duplicate_rows ??
                          0
                        }
                      />

                      <ReportCard
                        label="Invalid Dates"
                        value={
                          resultData?.cleaning_report
                            ?.unparseable_dates ??
                          0
                        }
                      />

                    </div>

                  </div>

                </div>

                {/* ==================================================
                    CUSTOMER & PRODUCT INSIGHTS
                ================================================== */}

                <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">

                  {/* Customer Insights */}

                  <div className="rounded-2xl border border-white/10 bg-[#0D1117] p-7">

                    <div className="flex items-center justify-between mb-6">

                      <div>

                        <h2 className="text-xl font-semibold">
                          Customer Insights
                        </h2>

                        <p className="text-sm text-gray-500 mt-1">
                          Who is buying in the selected period
                        </p>

                      </div>

                      <span className="text-2xl">
                        👤
                      </span>

                    </div>

                    {hasDateData &&
                    !resultData?.customer_data?.available ? (
                      <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-6 text-sm text-gray-400">
                        No customer information was mapped. Add a
                        Customer / Email / Phone column during the
                        mapping step to unlock customer insights.
                      </div>
                    ) : customerAnalysis ? (
                      <>
                        <div className="grid grid-cols-2 gap-4 mb-6">

                          <MiniStat
                            label="Customers"
                            value={customerAnalysis.totalCustomers.toLocaleString()}
                          />

                          <MiniStat
                            label="Repeat Rate"
                            value={
                              customerAnalysis.repeatRate != null
                                ? formatPercent(
                                    customerAnalysis.repeatRate
                                  )
                                : "N/A"
                            }
                          />

                          <MiniStat
                            label="New Customers"
                            value={customerAnalysis.newCustomers.toLocaleString()}
                          />

                          <MiniStat
                            label="Returning"
                            value={customerAnalysis.returningCustomers.toLocaleString()}
                          />

                        </div>

                        {customerAnalysis.topCustomer && (
                          <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-4 mb-5">

                            <p className="text-xs text-gray-500 mb-1">
                              TOP CUSTOMER
                            </p>

                            <p className="font-semibold truncate">
                              {customerAnalysis.topCustomer.customer}
                            </p>

                            <p className="text-sm text-gray-400 mt-1">
                              {formatMoney(
                                customerAnalysis.topCustomer.revenue
                              )}{" "}
                              ·{" "}
                              {customerAnalysis.totalRevenue > 0
                                ? `${(
                                    (customerAnalysis.topCustomer
                                      .revenue /
                                      customerAnalysis.totalRevenue) *
                                    100
                                  ).toFixed(1)}% of revenue`
                                : "0% of revenue"}
                            </p>

                          </div>
                        )}

                        {customerChartData.length > 0 && (
                          <div className="w-full h-[210px]">

                            <ResponsiveContainer
                              width="100%"
                              height="100%"
                            >

                              <BarChart
                                data={customerChartData}
                                margin={{
                                  top: 5,
                                  right: 10,
                                  left: 0,
                                  bottom: 5,
                                }}
                              >

                                <CartesianGrid
                                  strokeDasharray="3 3"
                                  stroke="rgba(255,255,255,0.06)"
                                />

                                <XAxis
                                  dataKey="name"
                                  stroke="#6B7280"
                                  tick={{
                                    fill: "#9CA3AF",
                                    fontSize: 11,
                                  }}
                                />

                                <YAxis
                                  stroke="#6B7280"
                                  tick={{
                                    fill: "#9CA3AF",
                                    fontSize: 11,
                                  }}
                                  tickFormatter={formatCompact}
                                />

                                <Tooltip
                                  contentStyle={tooltipStyle}
                                  formatter={(value) => [
                                    formatMoney(value),
                                    "Revenue",
                                  ]}
                                />

                                <Bar
                                  dataKey="revenue"
                                  name="Revenue"
                                  fill="#34D399"
                                  radius={[6, 6, 0, 0]}
                                />

                              </BarChart>

                            </ResponsiveContainer>

                          </div>
                        )}

                      </>
                    ) : (
                      <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-6 text-sm text-gray-400">
                        No complete customer data was found for this
                        period.
                      </div>
                    )}

                  </div>

                  {/* Product Insights */}

                  <div className="rounded-2xl border border-white/10 bg-[#0D1117] p-7">

                    <div className="flex items-center justify-between mb-6">

                      <div>

                        <h2 className="text-xl font-semibold">
                          Product Insights
                        </h2>

                        <p className="text-sm text-gray-500 mt-1">
                          What is selling in the selected period
                        </p>

                      </div>

                      <span className="text-2xl">
                        🏷️
                      </span>

                    </div>

                    {hasDateData &&
                    !resultData?.product_data?.available ? (
                      <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-6 text-sm text-gray-400">
                        No product information was mapped. Add a
                        Product / SKU column during the mapping step
                        to unlock product insights.
                      </div>
                    ) : productAnalysis ? (
                      <>
                        <div className="grid grid-cols-2 gap-4 mb-6">

                          <MiniStat
                            label="Products"
                            value={productAnalysis.totalProducts.toLocaleString()}
                          />

                          <MiniStat
                            label={
                              productAnalysis.hasQuantity
                                ? "Units Sold"
                                : "Line Items"
                            }
                            value={productAnalysis.totalUnits.toLocaleString()}
                          />

                          <MiniStat
                            label="Best Seller"
                            value={
                              productAnalysis.bestSeller
                                ? productAnalysis.bestSeller.product
                                    .length > 14
                                  ? `${productAnalysis.bestSeller.product.slice(
                                      0,
                                      14
                                    )}…`
                                  : productAnalysis.bestSeller.product
                                : "—"
                            }
                          />

                          <MiniStat
                            label="Revenue"
                            value={formatMoney(
                              productAnalysis.totalRevenue
                            )}
                          />

                        </div>

                        {productAnalysis.bestSeller && (
                          <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-4 mb-5">

                            <p className="text-xs text-gray-500 mb-1">
                              BEST SELLER
                            </p>

                            <p className="font-semibold truncate">
                              {productAnalysis.bestSeller.product}
                            </p>

                            <p className="text-sm text-gray-400 mt-1">
                              {productAnalysis.hasQuantity
                                ? `${productAnalysis.bestSeller.units.toLocaleString()} units`
                                : `${productAnalysis.bestSeller.orders.toLocaleString()} orders`}{" "}
                              ·{" "}
                              {formatMoney(
                                productAnalysis.bestSeller.revenue
                              )}
                            </p>

                          </div>
                        )}

                        {productChartData.length > 0 && (
                          <div className="w-full h-[210px]">

                            <ResponsiveContainer
                              width="100%"
                              height="100%"
                            >

                              <BarChart
                                data={productChartData}
                                margin={{
                                  top: 5,
                                  right: 10,
                                  left: 0,
                                  bottom: 5,
                                }}
                              >

                                <CartesianGrid
                                  strokeDasharray="3 3"
                                  stroke="rgba(255,255,255,0.06)"
                                />

                                <XAxis
                                  dataKey="name"
                                  stroke="#6B7280"
                                  tick={{
                                    fill: "#9CA3AF",
                                    fontSize: 11,
                                  }}
                                />

                                <YAxis
                                  stroke="#6B7280"
                                  tick={{
                                    fill: "#9CA3AF",
                                    fontSize: 11,
                                  }}
                                  tickFormatter={formatCompact}
                                />

                                <Tooltip
                                  contentStyle={tooltipStyle}
                                  formatter={(value) => [
                                    formatMoney(value),
                                    "Revenue",
                                  ]}
                                />

                                <Bar
                                  dataKey="revenue"
                                  name="Revenue"
                                  fill="#FBBF24"
                                  radius={[6, 6, 0, 0]}
                                />

                              </BarChart>

                            </ResponsiveContainer>

                          </div>
                        )}

                      </>
                    ) : (
                      <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-6 text-sm text-gray-400">
                        No complete product data was found for this
                        period.
                      </div>
                    )}

                  </div>

                </div>

                {/* ==================================================
                    AI INSIGHTS
                ================================================== */}

                <div className="mt-6 rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.04] p-7">

                  <div className="flex items-center gap-3 mb-6">

                    <div className="w-10 h-10 rounded-xl bg-emerald-400/10 border border-emerald-400/20 flex items-center justify-center">
                      💡
                    </div>

                    <div>

                      <h2 className="text-xl font-semibold">
                        Business Insights
                      </h2>

                      <p className="text-sm text-gray-500 mt-1">
                        Automated recommendations based on your data
                      </p>

                    </div>

                  </div>

                  <div className="space-y-3">

                    {businessInsights.length > 0 ? (
                      businessInsights.map((insight, index) => (

                        <div
                          key={index}
                          className="rounded-xl border border-white/10 bg-[#0D1117] px-5 py-4 text-gray-300"
                        >
                          {insight}
                        </div>

                      ))
                    ) : (
                      <div className="text-gray-400">
                        No insights were generated.
                      </div>
                    )}

                  </div>

                </div>

                {/* ==================================================
                    CLEANED DATA PREVIEW
                ================================================== */}

                <div className="mt-6 rounded-2xl border border-white/10 bg-[#0D1117] overflow-hidden">

                  <div className="p-7 border-b border-white/10">

                    <h2 className="text-xl font-semibold">
                      Cleaned Data Preview
                    </h2>

                    <p className="text-sm text-gray-500 mt-1">
                      Preview of the cleaned dataset used for analysis
                    </p>

                  </div>

                  <div className="overflow-x-auto">

                    {resultData?.cleaned_preview?.length > 0 ? (

                      <table className="w-full text-left">

                        <thead className="bg-white/[0.02] border-b border-white/10">

                          <tr>

                            {Object.keys(
                              resultData.cleaned_preview[0]
                            ).map((column) => (

                              <th
                                key={column}
                                className="px-5 py-4 text-xs font-medium text-gray-500 whitespace-nowrap"
                              >
                                {column}
                              </th>

                            ))}

                          </tr>

                        </thead>

                        <tbody>

                          {resultData.cleaned_preview
                            .slice(0, 10)
                            .map((row, rowIndex) => (

                              <tr
                                key={rowIndex}
                                className="border-b border-white/5 last:border-0"
                              >

                                {Object.keys(row).map(
                                  (column) => (

                                    <td
                                      key={column}
                                      className="px-5 py-4 text-sm text-gray-300 whitespace-nowrap"
                                    >
                                      {String(
                                        row[column] ?? ""
                                      )}
                                    </td>

                                  )
                                )}

                              </tr>

                            ))}

                        </tbody>

                      </table>

                    ) : (

                      <div className="p-8 text-center text-gray-500">
                        No preview data available.
                      </div>

                    )}

                  </div>

                </div>

                {/* ==================================================
                    ACTIONS
                ================================================== */}

                <div className="mt-8 flex flex-col sm:flex-row gap-4">

                  <button
                    onClick={handleDownloadExcel}
                    className="flex-1 rounded-xl bg-emerald-400 px-6 py-4 font-semibold text-black hover:bg-emerald-300 transition"
                  >
                    ↓ Download Cleaned Excel
                  </button>

                  <button
                    onClick={handleStartOver}
                    className="flex-1 rounded-xl border border-white/10 px-6 py-4 font-medium text-gray-300 hover:bg-white/5 transition"
                  >
                    Analyze Another File
                  </button>

                </div>

              </div>
            )}

            {/* ==================================================
                GRAPHICAL ANALYSIS
            ================================================== */}

            {analysisTab === "graphical" && (
              <div>

                {/* Section Header */}

                <div className="mb-8">

                  <div className="flex items-center gap-3 mb-3">

                    <div className="w-2 h-2 rounded-full bg-emerald-400" />

                    <span className="text-sm font-medium text-emerald-400">
                      GRAPHICAL ANALYSIS
                    </span>

                  </div>

                  <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
                    Visual Insights
                  </h2>

                  <p className="text-gray-400 mt-3 max-w-2xl">
                    Interactive charts generated from your business data.
                  </p>

                </div>

                {/* Revenue vs Net Profit */}

                <ChartCard
                  title="Revenue vs Net Profit"
                  description="Revenue and net profit performance over time"
                >

                  {hasChartData(revenueTrend, [
                    "revenue",
                    "net_profit",
                  ]) ? (

                    <div className="w-full h-[350px]">

                      <ResponsiveContainer
                        width="100%"
                        height="100%"
                      >

                        <LineChart
                          data={revenueTrend}
                          margin={{
                            top: 10,
                            right: 20,
                            left: 0,
                            bottom: 5,
                          }}
                        >

                          <CartesianGrid
                            strokeDasharray="3 3"
                            stroke="rgba(255,255,255,0.06)"
                          />

                          <XAxis
                            dataKey="month"
                            stroke="#6B7280"
                            tick={{
                              fill: "#9CA3AF",
                              fontSize: 12,
                            }}
                          />

                          <YAxis
                            stroke="#6B7280"
                            tick={{
                              fill: "#9CA3AF",
                              fontSize: 12,
                            }}
                            tickFormatter={formatCompact}
                          />

                          <Tooltip
                            contentStyle={tooltipStyle}
                          />

                          <Legend />

                          <Line
                            type="monotone"
                            dataKey="revenue"
                            name="Revenue"
                            stroke="#34D399"
                            strokeWidth={3}
                            dot={{ r: 4 }}
                            activeDot={{ r: 6 }}
                          />

                          <Line
                            type="monotone"
                            dataKey="net_profit"
                            name="Net Profit"
                            stroke="#60A5FA"
                            strokeWidth={3}
                            dot={{ r: 4 }}
                            activeDot={{ r: 6 }}
                          />

                          {compareEnabled && (
                            <>
                              <Line
                                type="monotone"
                                dataKey="prev_revenue"
                                name={`Revenue (${prevSeriesLabel})`}
                                stroke="#34D399"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                              />

                              <Line
                                type="monotone"
                                dataKey="prev_net_profit"
                                name={`Net Profit (${prevSeriesLabel})`}
                                stroke="#60A5FA"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                              />
                            </>
                          )}

                        </LineChart>

                      </ResponsiveContainer>

                    </div>

                  ) : (

                    <ChartEmpty />

                  )}

                </ChartCard>

                {/* Orders Trend + Cost Breakdown */}

                <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">

                  <ChartCard
                    title="Orders Trend"
                    description="Number of completed orders over time"
                  >

                    {hasChartData(ordersTrend, ["orders"]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <BarChart
                            data={ordersTrend}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatCompact}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                            />

                            <Legend />

                            <Bar
                              dataKey="orders"
                              name="Orders"
                              fill="#34D399"
                              radius={[6, 6, 0, 0]}
                            />

                            {compareEnabled && (
                              <Bar
                                dataKey="prev_orders"
                                name={`Orders (${prevSeriesLabel})`}
                                fill="#047857"
                                radius={[6, 6, 0, 0]}
                              />
                            )}

                          </BarChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                  <ChartCard
                    title="Cost Breakdown"
                    description="COGS, shipping and marketing costs over time"
                  >

                    {hasChartData(revenueTrend, [
                      "cogs",
                      "shipping",
                      "marketing",
                    ]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <BarChart
                            data={revenueTrend}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatCompact}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                            />

                            <Legend />

                            <Bar
                              dataKey="cogs"
                              name="COGS"
                              stackId="cost"
                              fill="#FBBF24"
                            />

                            <Bar
                              dataKey="shipping"
                              name="Shipping"
                              stackId="cost"
                              fill="#60A5FA"
                            />

                            <Bar
                              dataKey="marketing"
                              name="Marketing"
                              stackId="cost"
                              fill="#F472B6"
                              radius={[6, 6, 0, 0]}
                            />

                          </BarChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                </div>

                {/* Profitability Trend + Revenue vs Costs */}

                <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">

                  <ChartCard
                    title="Profitability Trend"
                    description="Gross profit compared with net profit over time"
                  >

                    {hasChartData(revenueTrend, [
                      "gross_profit",
                      "net_profit",
                    ]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <LineChart
                            data={revenueTrend}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatCompact}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                            />

                            <Legend />

                            <Line
                              type="monotone"
                              dataKey="gross_profit"
                              name="Gross Profit"
                              stroke="#A78BFA"
                              strokeWidth={3}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />

                            <Line
                              type="monotone"
                              dataKey="net_profit"
                              name="Net Profit"
                              stroke="#60A5FA"
                              strokeWidth={3}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />

                            {compareEnabled && (
                              <>
                                <Line
                                  type="monotone"
                                  dataKey="prev_gross_profit"
                                  name={`Gross Profit (${prevSeriesLabel})`}
                                  stroke="#A78BFA"
                                  strokeWidth={2}
                                  strokeDasharray="5 5"
                                  dot={false}
                                />

                                <Line
                                  type="monotone"
                                  dataKey="prev_net_profit"
                                  name={`Net Profit (${prevSeriesLabel})`}
                                  stroke="#60A5FA"
                                  strokeWidth={2}
                                  strokeDasharray="5 5"
                                  dot={false}
                                />
                              </>
                            )}

                          </LineChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                  <ChartCard
                    title="Revenue vs Business Costs"
                    description="Revenue compared with major business costs over time"
                  >

                    {hasChartData(revenueTrend, [
                      "revenue",
                      "cogs",
                      "shipping",
                      "marketing",
                    ]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <BarChart
                            data={revenueTrend}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                            barCategoryGap="18%"
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatCompact}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                            />

                            <Legend />

                            <Bar
                              dataKey="revenue"
                              name="Revenue"
                              fill="#34D399"
                            />

                            <Bar
                              dataKey="cogs"
                              name="COGS"
                              fill="#FBBF24"
                            />

                            <Bar
                              dataKey="shipping"
                              name="Shipping"
                              fill="#60A5FA"
                            />

                            <Bar
                              dataKey="marketing"
                              name="Marketing"
                              fill="#F472B6"
                              radius={[6, 6, 0, 0]}
                            />

                          </BarChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                </div>

                {/* Gross Profit Margin + Net Profit Margin */}

                <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">

                  <ChartCard
                    title="Gross Profit Margin"
                    description="Gross profit margin percentage over time"
                  >

                    {hasChartData(grossMarginData, [
                      "gross_margin",
                    ]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <LineChart
                            data={grossMarginData}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatPercentTick}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                              formatter={(value) => [
                                `${Number(value).toFixed(1)}%`,
                                "Gross Profit Margin",
                              ]}
                            />

                            <Line
                              type="monotone"
                              dataKey="gross_margin"
                              name="Gross Profit Margin"
                              stroke="#34D399"
                              strokeWidth={3}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />

                            {compareEnabled && (
                              <Line
                                type="monotone"
                                dataKey="prev_gross_margin"
                                name={`Gross Profit Margin (${prevSeriesLabel})`}
                                stroke="#34D399"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                              />
                            )}

                          </LineChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                  <ChartCard
                    title="Net Profit Margin"
                    description="Net profit margin percentage over time"
                  >

                    {hasChartData(netMarginData, [
                      "net_margin",
                    ]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <LineChart
                            data={netMarginData}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatPercentTick}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                              formatter={(value) => [
                                `${Number(value).toFixed(1)}%`,
                                "Net Profit Margin",
                              ]}
                            />

                            <Line
                              type="monotone"
                              dataKey="net_margin"
                              name="Net Profit Margin"
                              stroke="#60A5FA"
                              strokeWidth={3}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />

                            {compareEnabled && (
                              <Line
                                type="monotone"
                                dataKey="prev_net_margin"
                                name={`Net Profit Margin (${prevSeriesLabel})`}
                                stroke="#60A5FA"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                              />
                            )}

                          </LineChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                </div>

                {/* Cost Composition + Average Order Value Trend */}

                <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">

                  <ChartCard
                    title="Overall Cost Composition"
                    description="Share of total business costs by category"
                  >

                    {totalCosts > 0 ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <PieChart>

                            <Pie
                              data={costCompositionData}
                              dataKey="value"
                              nameKey="name"
                              innerRadius="55%"
                              outerRadius="80%"
                              paddingAngle={3}
                            >

                              {costCompositionData.map(
                                (entry) => (
                                  <Cell
                                    key={entry.name}
                                    fill={entry.color}
                                  />
                                )
                              )}

                            </Pie>

                            <Tooltip
                              contentStyle={tooltipStyle}
                              formatter={(value, name) => [
                                formatCompact(value),
                                name,
                              ]}
                            />

                            <Legend />

                          </PieChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                  <ChartCard
                    title="Average Order Value Trend"
                    description="Average revenue generated per order over time"
                  >

                    {hasChartData(aovData, ["aov"]) ? (

                      <div className="w-full h-[300px]">

                        <ResponsiveContainer
                          width="100%"
                          height="100%"
                        >

                          <LineChart
                            data={aovData}
                            margin={{
                              top: 10,
                              right: 10,
                              left: 0,
                              bottom: 5,
                            }}
                          >

                            <CartesianGrid
                              strokeDasharray="3 3"
                              stroke="rgba(255,255,255,0.06)"
                            />

                            <XAxis
                              dataKey="month"
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                            />

                            <YAxis
                              stroke="#6B7280"
                              tick={{
                                fill: "#9CA3AF",
                                fontSize: 12,
                              }}
                              tickFormatter={formatCompact}
                            />

                            <Tooltip
                              contentStyle={tooltipStyle}
                            />

                            <Legend />

                            <Line
                              type="monotone"
                              dataKey="aov"
                              name="Average Order Value"
                              stroke="#34D399"
                              strokeWidth={3}
                              dot={{ r: 4 }}
                              activeDot={{ r: 6 }}
                            />

                            {compareEnabled && (
                              <Line
                                type="monotone"
                                dataKey="prev_aov"
                                name={`Average Order Value (${prevSeriesLabel})`}
                                stroke="#34D399"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                dot={false}
                              />
                            )}

                          </LineChart>

                        </ResponsiveContainer>

                      </div>

                    ) : (

                      <ChartEmpty />

                    )}

                  </ChartCard>

                </div>

              </div>
            )}

          </section>
        )}

      </div>

    </main>
  );
}


// ======================================================
// STEP INDICATOR COMPONENT
// ======================================================

function StepIndicator({
  number,
  label,
  active,
  completed,
}) {
  return (
    <div className="flex items-center gap-2">

      <div
        className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold border transition ${
          active
            ? "bg-emerald-400 text-black border-emerald-400"
            : completed
            ? "bg-emerald-400/10 text-emerald-400 border-emerald-400/30"
            : "bg-white/5 text-gray-500 border-white/10"
        }`}
      >
        {completed ? "✓" : number}
      </div>

      <span
        className={`text-sm ${
          active || completed
            ? "text-white"
            : "text-gray-500"
        }`}
      >
        {label}
      </span>

    </div>
  );
}


// ======================================================
// METRIC CARD
// ======================================================

function MetricCard({
  label,
  value,
  description,
  positive = false,
  delta = null,
  deltaLabel = "previous period",
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#0D1117] p-6 hover:border-white/20 transition">

      <p className="text-sm text-gray-400">
        {label}
      </p>

      <h2 className="text-3xl font-semibold mt-3 break-words">
        {value}
      </h2>

      <p
        className={`text-sm mt-3 ${
          positive
            ? "text-emerald-400"
            : "text-gray-500"
        }`}
      >
        {description}
      </p>

      {delta && (
        <p
          className={`text-xs mt-1.5 font-medium ${
            delta.good
              ? "text-emerald-400"
              : "text-red-400"
          }`}
        >
          {delta.pct > 0
            ? "▲"
            : delta.pct < 0
            ? "▼"
            : "▶"}{" "}
          {Math.abs(delta.pct).toFixed(1)}% vs{" "}
          {deltaLabel.toLowerCase()}
        </p>
      )}

    </div>
  );
}


// ======================================================
// FINANCIAL ROW
// ======================================================

function FinancialRow({
  label,
  value,
  highlight = false,
  delta = null,
  deltaLabel = "previous period",
}) {
  return (
    <div
      className={`flex items-center justify-between py-3 border-b border-white/5 last:border-0 ${
        highlight ? "pt-4" : ""
      }`}
    >

      <span
        className={
          highlight
            ? "font-semibold text-white"
            : "text-gray-400"
        }
      >
        {label}
      </span>

      <div className="text-right">

        <span
          className={
            highlight
              ? "font-semibold text-emerald-400"
              : "text-gray-200"
          }
        >
          {value}
        </span>

        {delta && (
          <span
            className={`block text-xs mt-0.5 font-medium ${
              delta.good
                ? "text-emerald-400"
                : "text-red-400"
            }`}
          >
            {delta.pct > 0
              ? "▲"
              : delta.pct < 0
              ? "▼"
              : "▶"}{" "}
            {Math.abs(delta.pct).toFixed(1)}% vs{" "}
            {deltaLabel.toLowerCase()}
          </span>
        )}

      </div>

    </div>
  );
}


// ======================================================
// REPORT CARD
// ======================================================

function ReportCard({
  label,
  value,
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#070A0D] p-5">

      <p className="text-xs text-gray-500 mb-2">
        {label}
      </p>

      <p className="text-2xl font-semibold">
        {value}
      </p>

    </div>
  );
}


// ======================================================
// CHART CARD
// ======================================================

function ChartCard({
  title,
  description,
  children,
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#0D1117] p-7">

      <div className="mb-6">

        <h2 className="text-xl font-semibold">
          {title}
        </h2>

        <p className="text-sm text-gray-500 mt-1">
          {description}
        </p>

      </div>

      {children}

    </div>
  );
}


// ======================================================
// CHART EMPTY STATE
// ======================================================

function ChartEmpty() {
  return (
    <div className="w-full h-[300px] flex items-center justify-center text-gray-500 text-sm">
      No data available for this chart.
    </div>
  );
}


// ======================================================
// MINI STAT
// ======================================================

function MiniStat({
  label,
  value,
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#070A0D] px-4 py-3">

      <p className="text-xs text-gray-500 mb-1">
        {label}
      </p>

      <p className="text-lg font-semibold truncate">
        {value}
      </p>

    </div>
  );
}


// ======================================================
// FILTER FIELD
// ======================================================

function FilterField({
  label,
  children,
}) {
  return (
    <label className="flex-1 min-w-[150px]">

      <span className="block text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
        {label}
      </span>

      {children}

    </label>
  );
}