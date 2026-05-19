"use client";
import { useState } from "react";
import { previewDocument, getPdfUrl } from "@/lib/api";
import type { SearchResult } from "@/lib/api";

const MAX_SELECTED = 10;

interface Props {
  results: SearchResult[];
  selected: SearchResult[];
  onSelectionChange: (docs: SearchResult[]) => void;
  onGenerate: (docs: SearchResult[]) => void;
  onBack: () => void;
}

interface PreviewState {
  source: string;
  doc_id: string;
  pdfUrl: string;
  text: string | null;
  mode: "pdf" | "text";
}

export default function ReferencePanel({ results, selected, onSelectionChange, onGenerate, onBack }: Props) {
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [pdfError, setPdfError] = useState(false);

  function toggle(doc: SearchResult) {
    const isSelected = selected.some(d => d.doc_id === doc.doc_id);
    if (isSelected) {
      onSelectionChange(selected.filter(d => d.doc_id !== doc.doc_id));
    } else if (selected.length < MAX_SELECTED) {
      onSelectionChange([...selected, doc]);
    }
  }

  function openPreview(doc: SearchResult) {
    if (preview?.doc_id === doc.doc_id) return;
    setPdfError(false);
    // Append a cache-busting timestamp so the browser never serves a stale PDF
    const pdfUrl = `${getPdfUrl(doc.doc_id)}?t=${Date.now()}`;
    setPreview({ source: doc.source, doc_id: doc.doc_id, pdfUrl, text: null, mode: "pdf" });
    previewDocument(doc.doc_id)
      .then(data => setPreview(p => p && p.doc_id === doc.doc_id ? { ...p, text: data.text } : p))
      .catch(() => {});
  }

  function switchMode(mode: "pdf" | "text") {
    setPdfError(false);
    setPreview(p => p ? { ...p, mode } : null);
  }

  return (
    <div className="flex flex-col" style={{ height: "calc(100vh - 210px)", minHeight: "500px" }}>

      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Select Reference Documents</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Click a document to preview · Select up to {MAX_SELECTED} for generation ·{" "}
            <span className={selected.length >= MAX_SELECTED ? "text-blue-600 font-medium" : "text-gray-500"}>
              {selected.length}/{MAX_SELECTED} selected
            </span>
          </p>
        </div>
        <button onClick={onBack} className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">
          ← Back
        </button>
      </div>

      {/* ── Split pane ── */}
      <div className="flex flex-1 gap-4 min-h-0">

        {/* Left: document list */}
        <div className="w-80 shrink-0 flex flex-col min-h-0">
          {results.length === 0 ? (
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 text-center">
              <p className="text-yellow-800 font-medium text-sm">No documents found</p>
              <p className="text-yellow-600 text-xs mt-1">Upload documents via Manage Knowledge Base, then search again.</p>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {results.map(doc => {
                const isSelected = selected.some(d => d.doc_id === doc.doc_id);
                const isActive = preview?.doc_id === doc.doc_id;
                const atLimit = !isSelected && selected.length >= MAX_SELECTED;
                return (
                  <div
                    key={doc.doc_id}
                    onClick={() => openPreview(doc)}
                    className={
                      "rounded-xl border-2 transition-all cursor-pointer " +
                      (isActive
                        ? "border-blue-500 bg-blue-50 shadow-md"
                        : isSelected
                        ? "border-blue-300 bg-white hover:border-blue-400"
                        : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm")
                    }
                  >
                    <div className="p-3">
                      {/* Title row */}
                      <div className="flex items-start justify-between gap-2 mb-1.5">
                        <p className="text-xs font-medium text-gray-800 truncate flex-1" title={doc.source}>
                          {doc.source}
                        </p>
                        {isSelected && (
                          <span className="shrink-0 bg-blue-600 text-white text-xs px-1.5 py-0.5 rounded-full leading-none">✓</span>
                        )}
                      </div>
                      {/* Tags */}
                      <div className="flex flex-wrap gap-1 mb-1.5">
                        {doc.metadata.date && (
                          <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{doc.metadata.date}</span>
                        )}
                        <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">
                          {(doc.score * 100).toFixed(0)}% match
                        </span>
                      </div>
                      {/* Excerpt */}
                      <p className="text-xs text-gray-500 line-clamp-2 mb-2">{doc.excerpt}</p>
                      {/* Select button */}
                      <button
                        onClick={e => { e.stopPropagation(); toggle(doc); }}
                        disabled={atLimit}
                        className={
                          "w-full text-xs py-1.5 rounded-lg font-medium transition-colors disabled:opacity-40 " +
                          (isSelected
                            ? "bg-blue-600 text-white hover:bg-blue-700"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200")
                        }
                      >
                        {isSelected ? "Deselect" : atLimit ? "Limit reached" : "Select for draft"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: inline preview */}
        <div className="flex-1 min-h-0 flex flex-col rounded-xl border-2 border-gray-200 overflow-hidden bg-white">
          {preview ? (
            <>
              {/* Preview header */}
              <div className="flex items-center justify-between px-4 py-2.5 border-b bg-gray-50 shrink-0">
                <p className="text-sm font-medium text-gray-800 truncate flex-1 mr-3" title={preview.source}>
                  {preview.source}
                </p>
                <div className="flex rounded-lg border border-gray-300 overflow-hidden text-xs shrink-0">
                  <button
                    onClick={() => switchMode("pdf")}
                    className={"px-3 py-1.5 " + (preview.mode === "pdf" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50")}
                  >
                    PDF
                  </button>
                  <button
                    onClick={() => switchMode("text")}
                    className={"px-3 py-1.5 " + (preview.mode === "text" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50")}
                  >
                    Text
                  </button>
                </div>
              </div>

              {/* Preview body */}
              <div className="flex-1 overflow-hidden">
                {preview.mode === "pdf" ? (
                  pdfError ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-500">
                      <p className="text-sm">PDF not available on disk.</p>
                      {preview.text !== null && (
                        <button onClick={() => switchMode("text")} className="text-sm text-blue-600 underline">
                          Show extracted text instead
                        </button>
                      )}
                    </div>
                  ) : (
                    <iframe
                      key={preview.doc_id}
                      src={preview.pdfUrl}
                      className="w-full h-full border-0"
                      title={preview.source}
                      onError={() => setPdfError(true)}
                    />
                  )
                ) : (
                  <div className="p-4 overflow-y-auto h-full">
                    {preview.text === null ? (
                      <p className="text-sm text-gray-400 italic">Loading text…</p>
                    ) : (
                      <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">{preview.text}</pre>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Empty state */
            <div className="flex flex-col items-center justify-center h-full gap-3 text-gray-400">
              <svg className="w-14 h-14 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="text-sm">Click a document on the left to preview it here</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Footer ── */}
      <div className="flex justify-between items-center mt-3 pt-3 border-t shrink-0">
        <p className="text-sm text-gray-500">
          {selected.length > 0
            ? `${selected.length} document(s) selected for generation`
            : "No documents selected — AI will use general style"}
        </p>
        <button
          onClick={() => onGenerate(selected)}
          className="bg-blue-600 text-white px-6 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          Generate Draft →
        </button>
      </div>
    </div>
  );
}
