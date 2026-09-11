"use client";

export default function MappingReview({
  columns,
  suggestions,
  standardFields,
  preview,
  mapping,
  setMapping,
  onConfirm,
  isLoading,
}) {
  const handleChange = (col, value) => {
    setMapping((prev) => {
      const updated = { ...prev };
      if (value === "(ignore)") {
        delete updated[col];
      } else {
        updated[col] = value;
      }
      return updated;
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-800">1. Preview of your data</h2>
        <div className="mt-2 overflow-x-auto rounded-lg border">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                {columns.map((col) => (
                  <th key={col} className="px-3 py-2 text-left font-medium text-gray-600">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.slice(0, 5).map((row, i) => (
                <tr key={i} className="border-t">
                  {columns.map((col) => (
                    <td key={col} className="px-3 py-2 text-gray-700">
                      {row[col]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-800">
          2. Confirm column mapping
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          We auto-detected these — correct anything that looks wrong before continuing.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {columns.map((col) => {
            const suggestion = suggestions[col];
            const confidence = suggestion?.confidence || 0;
            // A standard field can be assigned to exactly one column. Fields
            // already chosen by another column are hidden here so the user can
            // never double-map (e.g. UnitPrice + Revenue both -> revenue),
            // which previously double-counted financial metrics upstream.
            const chosenByOthers = Object.entries(mapping)
              .filter(([key, value]) => key !== col && value)
              .map(([, value]) => value);
            const availableFields = standardFields.filter(
              (field) => !chosenByOthers.includes(field)
            );
            return (
              <div key={col} className="flex items-center justify-between gap-3 rounded-lg border p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-700">{col}</p>
                  {suggestion?.suggested_field && (
                    <p className="text-xs text-gray-400">{confidence}% confidence</p>
                  )}
                </div>
                <select
                  value={mapping[col] || "(ignore)"}
                  onChange={(e) => handleChange(col, e.target.value)}
                  className="rounded-md border border-gray-300 px-2 py-1 text-sm"
                >
                  <option value="(ignore)">(ignore)</option>
                  {availableFields.map((field) => (
                    <option key={field} value={field}>
                      {field}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      </div>

      <button
        onClick={onConfirm}
        disabled={isLoading}
        className="rounded-lg bg-blue-600 px-5 py-2.5 font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
      >
        {isLoading ? "Processing..." : "Generate Insights"}
      </button>
    </div>
  );
}
