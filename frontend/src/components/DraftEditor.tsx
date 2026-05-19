"use client";
import { useState, useEffect, useRef } from "react";
import {
  generateDraft,
  refineDraft,
  refineSection,
  regenerateSelection,
  exportDocx,
} from "@/lib/api";
import type { Citation } from "@/lib/api";
import type { DraftParams } from "@/app/page";

interface Props {
  params: DraftParams;
  selectedDocIds: string[];
  initialDraft: string;
  onDraftChange: (draft: string) => void;
  onBack: () => void;
}

// Badge colours cycle through a palette based on ref_num
const BADGE_COLORS = [
  "bg-blue-100 text-blue-700 border-blue-300",
  "bg-emerald-100 text-emerald-700 border-emerald-300",
  "bg-violet-100 text-violet-700 border-violet-300",
  "bg-amber-100 text-amber-700 border-amber-300",
  "bg-rose-100 text-rose-700 border-rose-300",
  "bg-cyan-100 text-cyan-700 border-cyan-300",
  "bg-orange-100 text-orange-700 border-orange-300",
  "bg-pink-100 text-pink-700 border-pink-300",
];

function badgeColor(n: number) {
  return BADGE_COLORS[(n - 1) % BADGE_COLORS.length];
}

/** Strip all [N] citation markers from a string, preserving whitespace/newlines */
function stripCitations(text: string): string {
  return text.replace(/\s*\[\d+\]/g, "");
}

/** Parse inline **bold** and *italic* within a plain-text segment */
function renderInlineMarkdown(segment: string): React.ReactNode[] {
  const tokens = segment.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g);
  return tokens.map((tok, i) => {
    if (tok.startsWith("**") && tok.endsWith("**")) {
      return <strong key={i}>{tok.slice(2, -2)}</strong>;
    }
    if (tok.startsWith("*") && tok.endsWith("*")) {
      return <em key={i}>{tok.slice(1, -1)}</em>;
    }
    return (
      <span key={i}>
        {tok.split("\n").map((line, j, arr) => (
          <span key={j}>
            {line}
            {j < arr.length - 1 && <br />}
          </span>
        ))}
      </span>
    );
  });
}

/** Render draft text with inline [N] citation badges */
function CitedText({
  text,
  citations,
  activeCitation,
  onCitationClick,
}: {
  text: string;
  citations: Citation[];
  activeCitation: number | null;
  onCitationClick: (n: number) => void;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (m) {
          const n = parseInt(m[1]);
          const cit = citations.find((c) => c.ref_num === n);
          const isActive = activeCitation === n;
          return (
            <sup
              key={i}
              className={`citation-badge cursor-pointer text-[0.65rem] font-bold border rounded px-0.5 mx-0.5 select-none transition-all ${badgeColor(n)} ${isActive ? "ring-2 ring-offset-1 ring-current" : ""}`}
              onClick={() => onCitationClick(n)}
              title={cit ? `[${n}] ${cit.source}` : `[${n}]`}
            >
              {n}
            </sup>
          );
        }
        return <span key={i}>{renderInlineMarkdown(part)}</span>;
      })}
    </>
  );
}

/** Render a full draft with Markdown tables, headings, and inline citation badges */
function renderDraftContent(
  text: string,
  citations: Citation[],
  activeCitation: number | null,
  onCitationClick: (n: number) => void,
): React.ReactNode[] {
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    // ── Markdown table block ──────────────────────────────────────
    if (lines[i].trimStart().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trimStart().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      const isValidTable =
        tableLines.length >= 2 && /^\|[-| :]+\|/.test(tableLines[1]);
      if (isValidTable) {
        const parseRow = (line: string) =>
          line.split("|").slice(1, -1).map((c) => c.trim());
        const headers = parseRow(tableLines[0]);
        const rows = tableLines.slice(2).map(parseRow);
        blocks.push(
          <div key={key++} className="overflow-x-auto my-4">
            <table className="min-w-full text-sm border-collapse">
              <thead>
                <tr>
                  {headers.map((h, j) => (
                    <th key={j} className="border border-gray-300 bg-gray-100 px-3 py-2 text-left font-semibold whitespace-nowrap">
                      <CitedText text={h} citations={citations} activeCitation={activeCitation} onCitationClick={onCitationClick} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, r) => (
                  <tr key={r} className={r % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                    {row.map((cell, j) => (
                      <td key={j} className="border border-gray-300 px-3 py-2">
                        <CitedText text={cell} citations={citations} activeCitation={activeCitation} onCitationClick={onCitationClick} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      } else {
        blocks.push(
          <p key={key++} className="mb-3 leading-relaxed">
            <CitedText text={tableLines.join("\n")} citations={citations} activeCitation={activeCitation} onCitationClick={onCitationClick} />
          </p>
        );
      }
      continue;
    }

    // ── Non-table block: collect until next table or end ──────────
    const paraLines: string[] = [];
    while (i < lines.length && !lines[i].trimStart().startsWith("|")) {
      paraLines.push(lines[i]);
      i++;
    }
    const para = paraLines.join("\n");

    // Split further on blank lines to get paragraphs
    const subParas = para.split(/\n\s*\n/);
    for (const sub of subParas) {
      const trimmed = sub.trim();
      if (!trimmed) continue;

      // Heading detection (## Heading)
      const headingMatch = trimmed.match(/^(#{1,4})\s+(.*)/);
      if (headingMatch) {
        const level = headingMatch[1].length;
        const headingClasses = [
          "text-2xl font-bold text-gray-900 mt-6 mb-2",
          "text-xl font-bold text-gray-900 mt-5 mb-2",
          "text-lg font-semibold text-gray-800 mt-4 mb-1",
          "text-base font-semibold text-gray-800 mt-3 mb-1",
        ];
        blocks.push(
          <div key={key++} className={headingClasses[level - 1] ?? headingClasses[3]}>
            <CitedText text={headingMatch[2]} citations={citations} activeCitation={activeCitation} onCitationClick={onCitationClick} />
          </div>
        );
      } else {
        blocks.push(
          <p key={key++} className="mb-3 leading-relaxed">
            <CitedText text={trimmed} citations={citations} activeCitation={activeCitation} onCitationClick={onCitationClick} />
          </p>
        );
      }
    }
  }

  return blocks;
}

/** Extract all sentences/lines from draft text that cite reference [n] */
function getSentencesForRef(text: string, n: number): string[] {
  const marker = `[${n}]`;
  const results: string[] = [];
  const lines = text.split("\n");
  for (const line of lines) {
    if (!line.includes(marker)) continue;
    // Split on sentence-ending punctuation then whitespace
    const sentences = line.split(/(?<=[.!?])\s+/);
    const matched = sentences.filter((s) => s.includes(marker));
    if (matched.length > 0) {
      for (const s of matched) {
        const cleaned = s.replace(/\[\d+\]/g, "").trim();
        if (cleaned) results.push(cleaned);
      }
    } else {
      // Table cell or short line — use whole line
      const cleaned = line.replace(/\[\d+\]/g, "").replace(/^\||\|$/g, "").trim();
      if (cleaned) results.push(cleaned);
    }
  }
  return results;
}

export default function DraftEditor({
  params,
  selectedDocIds,
  initialDraft,
  onDraftChange,
  onBack,
}: Props) {
  const [draft, setDraft] = useState(initialDraft);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [exportUrl, setExportUrl] = useState("");
  const [exporting, setExporting] = useState(false);

  // View / Edit mode
  const [mode, setMode] = useState<"view" | "edit">("view");

  // Citation panel
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  // AI Chat sidebar
  const [chatMsg, setChatMsg] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<{ role: "user" | "ai"; text: string }[]>([]);

  // Selection-based regeneration (edit mode)
  const [selectionInfo, setSelectionInfo] = useState<{
    text: string;
    start: number;
    end: number;
  } | null>(null);
  const [floatingPos, setFloatingPos] = useState<{ top: number; left: number } | null>(null);
  const [regenInstruction, setRegenInstruction] = useState("");
  const [regenLoading, setRegenLoading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const floatingRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const hasGenerated = useRef(false);

  useEffect(() => {
    if (!initialDraft && !hasGenerated.current) {
      hasGenerated.current = true;
      handleGenerate();
    }
  }, []);

  // Close floating toolbar when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (floatingRef.current && !floatingRef.current.contains(e.target as Node)) {
        setFloatingPos(null);
        setSelectionInfo(null);
        setRegenInstruction("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Auto-scroll chat to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  async function handleGenerate() {
    setLoading(true);
    setError("");
    setExportUrl("");
    setActiveCitation(null);
    try {
      const result = await generateDraft({
        topic: params.topic,
        doc_type: params.doc_type,
        tone: params.tone,
        language: params.language,
        extra_instructions: params.extra_instructions,
        selected_doc_ids: selectedDocIds,
      });
      setDraft(result.draft);
      setCitations(result.citations);
      onDraftChange(result.draft);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Generation failed. Is LM Studio running?");
    } finally {
      setLoading(false);
    }
  }

  function handleDraftEdit(value: string) {
    setDraft(value);
    onDraftChange(value);
  }

  async function handleChat(e: React.FormEvent) {
    e.preventDefault();
    if (!chatMsg.trim() || !draft) return;
    const instruction = chatMsg;
    setChatMsg("");
    setChatLoading(true);
    setChatHistory((h) => [...h, { role: "user", text: instruction }]);
    try {
      const refined = await refineDraft(draft, instruction, citations);
      setDraft(refined);
      onDraftChange(refined);
      setChatHistory((h) => [...h, { role: "ai", text: "Draft updated." }]);
    } catch (err: unknown) {
      setChatHistory((h) => [
        ...h,
        { role: "ai", text: "Error: " + (err instanceof Error ? err.message : "Unknown") },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function handleRemoveCitations() {
    const cleaned = stripCitations(draft);
    setDraft(cleaned);
    setCitations([]);
    onDraftChange(cleaned);
    setActiveCitation(null);
  }

  // ── Selection handling in edit mode ──────────────────────────────────────

  function handleTextareaSelect() {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    if (end - start < 5) {
      setFloatingPos(null);
      setSelectionInfo(null);
      return;
    }
    const selectedText = draft.slice(start, end);
    setSelectionInfo({ text: selectedText, start, end });

    // Position the floating toolbar near the selection using caret coordinates
    // Approximate: position near the textarea top + estimated line offset
    const taRect = ta.getBoundingClientRect();
    const scrollTop = window.scrollY || document.documentElement.scrollTop;
    setFloatingPos({ top: taRect.top + scrollTop - 60, left: taRect.left + 16 });
  }

  async function handleRegenerateSelection(e: React.FormEvent) {
    e.preventDefault();
    if (!selectionInfo) return;
    setRegenLoading(true);
    try {
      const replacement = await regenerateSelection({
        selected_text: selectionInfo.text,
        instruction: regenInstruction || "Rewrite this selection maintaining the same style, tone, and format.",
        full_draft: draft,
        topic: params.topic,
        doc_type: params.doc_type,
        tone: params.tone,
        language: params.language,
        citations,
      });
      const newDraft =
        draft.slice(0, selectionInfo.start) + replacement + draft.slice(selectionInfo.end);
      setDraft(newDraft);
      onDraftChange(newDraft);
      setFloatingPos(null);
      setSelectionInfo(null);
      setRegenInstruction("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Regeneration failed");
    } finally {
      setRegenLoading(false);
    }
  }

  async function handleExport() {
    if (!draft) return;
    setExporting(true);
    try {
      const url = await exportDocx(
        stripCitations(draft),
        params.topic.slice(0, 40).replace(/[^a-zA-Z0-9]/g, "_") || "draft"
      );
      setExportUrl(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* ── Main editor ── */}
      <div className="lg:col-span-2 space-y-4">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          {/* Header toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2 p-4 border-b">
            <div>
              <h2 className="font-semibold text-gray-800">Draft Editor</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                {params.doc_type} · {params.tone} · {params.language}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              {/* View / Edit toggle */}
              <div className="flex rounded-lg border border-gray-300 overflow-hidden text-sm">
                <button
                  onClick={() => setMode("view")}
                  className={`px-3 py-1.5 transition-colors ${mode === "view" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                >
                  View
                </button>
                <button
                  onClick={() => setMode("edit")}
                  className={`px-3 py-1.5 transition-colors ${mode === "edit" ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-50"}`}
                >
                  Edit
                </button>
              </div>

              {citations.length > 0 && (
                <button
                  onClick={handleRemoveCitations}
                  className="px-3 py-1.5 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50"
                  title="Strip all [N] citation markers from the draft"
                >
                  Remove Citations
                </button>
              )}

              <button
                onClick={onBack}
                className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                ← Back
              </button>
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
              >
                {loading ? "Generating…" : "Regenerate"}
              </button>
              <button
                onClick={handleExport}
                disabled={!draft || exporting}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {exporting ? "Exporting…" : "Export DOCX"}
              </button>
            </div>
          </div>

          {/* Status banners */}
          {error && (
            <div className="mx-4 mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}
          {exportUrl && (
            <div className="mx-4 mt-4 p-3 bg-green-50 border border-green-200 rounded-lg flex items-center justify-between">
              <span className="text-green-700 text-sm">Export ready!</span>
              <a href={exportUrl} download className="text-sm font-medium text-green-700 underline">
                Download
              </a>
            </div>
          )}

          {loading ? (
            <div className="p-8 text-center">
              <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-gray-500 text-sm">Generating draft from LM Studio…</p>
            </div>
          ) : mode === "view" ? (
            /* ── VIEW MODE: rendered with citation badges + tables ── */
            <div className="p-6 min-h-[500px] text-sm text-gray-800">
              {draft ? (
                renderDraftContent(draft, citations, activeCitation, (n) =>
                  setActiveCitation((prev) => (prev === n ? null : n))
                )
              ) : (
                <span className="text-gray-400 italic">Your draft will appear here…</span>
              )}
            </div>
          ) : (
            /* ── EDIT MODE: textarea with selection toolbar ── */
            <div className="relative p-4">
              {mode === "edit" && (
                <p className="text-xs text-blue-600 mb-2 flex items-center gap-1">
                  <span className="inline-block w-2 h-2 rounded-full bg-blue-600" />
                  Highlight any text and a toolbar will appear to regenerate just that part.
                </p>
              )}
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(e) => handleDraftEdit(e.target.value)}
                onMouseUp={handleTextareaSelect}
                onKeyUp={handleTextareaSelect}
                className="w-full min-h-[500px] text-sm text-gray-800 leading-relaxed border border-gray-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-300 resize-y font-mono"
                placeholder="Your draft will appear here…"
              />
            </div>
          )}
        </div>

        {/* ── Edit-mode hint bar ── */}
        {mode === "edit" && (
          <div className="text-xs text-gray-500 px-1">
            Tip: Select text in the editor above, then use the floating toolbar to regenerate only that selection.
          </div>
        )}
      </div>

      {/* ── Right sidebar ── */}
      <div className="space-y-4">
        {/* Citations panel */}
        {citations.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-4 border-b flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-gray-800 text-sm">References</h3>
                <p className="text-xs text-gray-500 mt-0.5">Click to see cited sentences</p>
              </div>
              <span className="text-xs bg-gray-100 text-gray-500 rounded-full px-2 py-0.5">
                {citations.length}
              </span>
            </div>
            <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
              {citations.map((cit) => {
                const isActive = activeCitation === cit.ref_num;
                const usedSentences = isActive ? getSentencesForRef(draft, cit.ref_num) : [];
                return (
                  <div key={cit.ref_num}>
                    <button
                      onClick={() =>
                        setActiveCitation((prev) => (prev === cit.ref_num ? null : cit.ref_num))
                      }
                      className={`w-full text-left p-3 hover:bg-gray-50 transition-colors ${isActive ? "bg-blue-50" : ""}`}
                    >
                      <div className="flex items-start gap-2">
                        <span
                          className={`shrink-0 text-[0.65rem] font-bold border rounded px-1 py-0.5 mt-0.5 ${badgeColor(cit.ref_num)}`}
                        >
                          {cit.ref_num}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-gray-800 truncate">{cit.source}</p>
                          <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{cit.excerpt}</p>
                        </div>
                        <span className="text-gray-400 text-[0.6rem] shrink-0 mt-0.5">{isActive ? "▲" : "▼"}</span>
                      </div>
                    </button>
                    {isActive && (
                      <div className="px-3 pb-3 bg-blue-50 border-t border-blue-100">
                        <p className="text-[0.65rem] font-semibold text-blue-600 mb-1.5 mt-2 uppercase tracking-wide">Used in draft:</p>
                        {usedSentences.length > 0 ? (
                          <div className="space-y-1.5">
                            {usedSentences.map((s, idx) => (
                              <p key={idx} className="text-xs text-gray-700 bg-white rounded-lg p-2 border border-blue-200 leading-relaxed italic">
                                &ldquo;{s}&rdquo;
                              </p>
                            ))}
                          </div>
                        ) : (
                          <p className="text-xs text-gray-400 italic">No explicit sentence match found.</p>
                        )}
                        {cit.highlighted_text && (
                          <div className="mt-2.5 pt-2 border-t border-blue-100">
                            <p className="text-[0.65rem] font-semibold text-indigo-600 mb-1 uppercase tracking-wide">From reference:</p>
                            <p className="text-xs text-gray-700 bg-indigo-50 rounded-lg p-2 border border-indigo-200 leading-relaxed italic">
                              &ldquo;{cit.highlighted_text}&rdquo;
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* AI Assistant chat */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden">
          {/* Chat header */}
          <div className="p-3 border-b bg-gradient-to-r from-blue-600 to-indigo-600 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-white text-sm font-bold shrink-0">
              ✨
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-white text-sm">AI Assistant</h3>
              <p className="text-blue-100 text-[0.65rem]">Ask me to refine the draft</p>
            </div>
            {chatHistory.length > 0 && (
              <button
                onClick={() => setChatHistory([])}
                className="text-white/60 hover:text-white text-[0.65rem] transition-colors"
                title="Clear conversation"
              >
                Clear
              </button>
            )}
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2 min-h-[160px] max-h-64 bg-gray-50">
            {chatHistory.length === 0 ? (
              <div className="space-y-1.5">
                <p className="text-[0.6rem] text-gray-400 text-center uppercase tracking-widest mb-2">Quick actions</p>
                {[
                  { icon: "✂️", label: "Make it shorter" },
                  { icon: "🏛️", label: "Use more formal language" },
                  { icon: "✏️", label: "Add a strong opening paragraph" },
                  { icon: "📌", label: "Summarize key points in bullets" },
                ].map(({ icon, label }) => (
                  <button
                    key={label}
                    onClick={() => setChatMsg(label)}
                    className="w-full text-left text-xs px-3 py-2 bg-white hover:bg-blue-50 border border-gray-200 hover:border-blue-300 rounded-xl text-gray-600 transition-all shadow-sm flex items-center gap-2"
                  >
                    <span>{icon}</span>
                    <span>{label}</span>
                  </button>
                ))}
              </div>
            ) : (
              chatHistory.map((msg, i) => (
                <div
                  key={i}
                  className={"flex items-end gap-1.5 " + (msg.role === "user" ? "justify-end" : "justify-start")}
                >
                  {msg.role === "ai" && (
                    <div className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 text-[0.55rem] font-bold flex items-center justify-center shrink-0 mb-0.5">
                      AI
                    </div>
                  )}
                  <div
                    className={
                      "max-w-[82%] text-xs rounded-2xl px-3 py-2 leading-relaxed " +
                      (msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-none shadow-sm"
                        : "bg-white text-gray-700 border border-gray-200 rounded-bl-none shadow-sm")
                    }
                  >
                    {msg.text}
                  </div>
                  {msg.role === "user" && (
                    <div className="w-5 h-5 rounded-full bg-blue-600 text-white text-[0.55rem] font-bold flex items-center justify-center shrink-0 mb-0.5">
                      U
                    </div>
                  )}
                </div>
              ))
            )}
            {chatLoading && (
              <div className="flex items-end gap-1.5 justify-start">
                <div className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 text-[0.55rem] font-bold flex items-center justify-center shrink-0">
                  AI
                </div>
                <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-none px-3 py-2 shadow-sm">
                  <div className="flex gap-1 items-center h-3.5">
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          <div className="p-3 border-t bg-white">
            <form onSubmit={handleChat} className="flex gap-2 items-end">
              <textarea
                value={chatMsg}
                onChange={(e) => setChatMsg(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (chatMsg.trim() && !chatLoading) handleChat(e as unknown as React.FormEvent);
                  }
                }}
                rows={2}
                placeholder="Type an instruction… (Enter to send)"
                className="flex-1 border border-gray-300 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300 resize-none leading-relaxed"
              />
              <button
                type="submit"
                disabled={chatLoading || !chatMsg.trim()}
                className="px-3 py-2.5 bg-blue-600 text-white text-sm rounded-xl hover:bg-blue-700 disabled:opacity-40 transition-colors shrink-0"
                title="Send (Enter)"
              >
                ↑
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* ── Floating regenerate toolbar (edit mode, shown on selection) ── */}
      {mode === "edit" && floatingPos && selectionInfo && (
        <div
          ref={floatingRef}
          style={{ position: "absolute", top: floatingPos.top, left: floatingPos.left, zIndex: 50 }}
          className="bg-white border border-blue-300 rounded-xl shadow-xl p-3 w-80"
        >
          <p className="text-xs font-medium text-gray-700 mb-2">
            Selected: <span className="text-blue-600">{selectionInfo.text.slice(0, 60)}{selectionInfo.text.length > 60 ? "…" : ""}</span>
          </p>
          <form onSubmit={handleRegenerateSelection} className="space-y-2">
            <input
              value={regenInstruction}
              onChange={(e) => setRegenInstruction(e.target.value)}
              placeholder="Instruction (optional) — e.g. make it shorter"
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-300"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={regenLoading}
                className="flex-1 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {regenLoading ? "Regenerating…" : "Regenerate Selection"}
              </button>
              <button
                type="button"
                onClick={() => { setFloatingPos(null); setSelectionInfo(null); setRegenInstruction(""); }}
                className="px-2 py-1.5 text-gray-500 hover:text-gray-700 text-xs"
              >
                ✕
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
