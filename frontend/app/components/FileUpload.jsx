"use client";

import { useState, useRef } from "react";

export default function FileUpload({ onFileSelected, isLoading }) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleFile = (file) => {
    if (!file) return;
    const validTypes = [".csv", ".xlsx"];
    const isValid = validTypes.some((ext) => file.name.toLowerCase().endsWith(ext));
    if (!isValid) {
      alert("Please upload a .csv or .xlsx file");
      return;
    }
    onFileSelected(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setIsDragging(false);
        handleFile(e.dataTransfer.files?.[0]);
      }}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-colors
        ${isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-gray-50 hover:bg-gray-100"}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xlsx"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {isLoading ? (
        <p className="text-gray-500">Analyzing your file...</p>
      ) : (
        <>
          <p className="text-lg font-medium text-gray-700">
            Drag & drop your order data here
          </p>
          <p className="mt-1 text-sm text-gray-500">or click to browse (.csv or .xlsx)</p>
        </>
      )}
    </div>
  );
}
