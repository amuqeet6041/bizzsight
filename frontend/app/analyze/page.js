"use client";

import { useState } from "react";
import Link from "next/link";

export default function AnalyzePage() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);

  const [step, setStep] = useState("upload");

  const [mappingData, setMappingData] = useState(null);
  const [mapping, setMapping] = useState({});

  const [resultData, setResultData] = useState(null);

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
                KPI CARDS
            ================================================== */}

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">

              <MetricCard
                label="Revenue"
                value={
                  resultData?.display_metrics?.Revenue ??
                  "N/A"
                }
                description="Total Sales"
                positive
              />

              <MetricCard
                label="Gross Profit"
                value={
                  resultData?.display_metrics?.[
                    "Gross Profit"
                  ] ?? "N/A"
                }
                description="Before Marketing"
                positive
              />

              <MetricCard
                label="Net Profit"
                value={
                  resultData?.display_metrics?.[
                    "Net Profit"
                  ] ?? "N/A"
                }
                description="After Marketing"
                positive
              />

              <MetricCard
                label="Orders"
                value={
                  resultData?.display_metrics?.Orders ??
                  "N/A"
                }
                description="Completed Orders"
                positive
              />

              <MetricCard
                label="Average Order Value"
                value={
                  resultData?.display_metrics?.AOV ??
                  "N/A"
                }
                description="Revenue per Order"
              />

              <MetricCard
                label="Customer Acquisition Cost"
                value={
                  resultData?.display_metrics?.CAC ??
                  "N/A"
                }
                description="Cost per New Customer"
              />

              <MetricCard
                label="Return / Cancel Rate"
                value={
                  resultData?.display_metrics?.[
                    "Return/Cancel Rate"
                  ] ?? "N/A"
                }
                description="Cancelled / Returned"
              />

              <MetricCard
                label="Repeat Purchase Rate"
                value={
                  resultData?.display_metrics?.[
                    "Repeat Purchase Rate"
                  ] ?? "N/A"
                }
                description="Returning Customers"
              />

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
                      resultData?.display_metrics?.Revenue ??
                      "N/A"
                    }
                  />

                  <FinancialRow
                    label="COGS"
                    value={
                      resultData?.display_metrics?.COGS ??
                      "N/A"
                    }
                  />

                  <FinancialRow
                    label="Shipping Cost"
                    value={
                      resultData?.display_metrics?.[
                        "Shipping Cost"
                      ] ?? "N/A"
                    }
                  />

                  <FinancialRow
                    label="Marketing Spend"
                    value={
                      resultData?.display_metrics?.[
                        "Marketing Spend"
                      ] ?? "N/A"
                    }
                  />

                  <FinancialRow
                    label="Gross Profit"
                    value={
                      resultData?.display_metrics?.[
                        "Gross Profit"
                      ] ?? "N/A"
                    }
                  />

                  <FinancialRow
                    label="Net Profit"
                    value={
                      resultData?.display_metrics?.[
                        "Net Profit"
                      ] ?? "N/A"
                    }
                    highlight
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

                {resultData?.insights?.length > 0 ? (
                  resultData.insights.map(
                    (insight, index) => (

                      <div
                        key={index}
                        className="rounded-xl border border-white/10 bg-[#0D1117] px-5 py-4 text-gray-300"
                      >
                        {insight}
                      </div>

                    )
                  )
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

      <span
        className={
          highlight
            ? "font-semibold text-emerald-400"
            : "text-gray-200"
        }
      >
        {value}
      </span>

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