"use client";
import { useState } from "react";
import { searchDocuments } from "@/lib/api";
import type { SearchResult } from "@/lib/api";
import type { DraftParams } from "@/app/page";

interface Props {
  onSearch: (params: DraftParams, results: SearchResult[]) => void;
}

const DOC_TYPES = ["Official Reply", "Press Release", "Policy Statement", "Announcement", "Other"];
const TONES = ["Formal", "Neutral", "Urgent"];
const LANGUAGES = ["English", "Chinese", "Bilingual"];

export default function InputPanel({ onSearch }: Props) {
  const [topic, setTopic] = useState("");
  const [docType, setDocType] = useState("Official Reply");
  const [tone, setTone] = useState("Formal");
  const [language, setLanguage] = useState("English");
  const [extra, setExtra] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const results = await searchDocuments(topic, 20, { doc_type: docType, language });
      onSearch({ topic, doc_type: docType, tone, language, extra_instructions: extra }, results);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <h2 className="text-xl font-semibold mb-6 text-gray-800">Document Parameters</h2>
        <form onSubmit={handleSearch} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
            <select value={docType} onChange={e => setDocType(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              {DOC_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Topic / Subject <span className="text-red-500">*</span></label>
            <textarea
              value={topic}
              onChange={e => setTopic(e.target.value)}
              rows={3}
              placeholder="Describe the topic or subject of the document..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Tone</label>
              <select value={tone} onChange={e => setTone(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                {TONES.map(t => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
              <select value={language} onChange={e => setLanguage(e.target.value)} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                {LANGUAGES.map(l => <option key={l}>{l}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Additional Instructions <span className="text-gray-400 font-normal">(optional)</span></label>
            <textarea
              value={extra}
              onChange={e => setExtra(e.target.value)}
              rows={2}
              placeholder="e.g. Include statistics from 2024, keep under 500 words..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
          </div>
          {error && <p className="text-red-600 text-sm bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <button
            type="submit"
            disabled={loading || !topic.trim()}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Searching references..." : "Search References"}
          </button>
        </form>
      </div>
    </div>
  );
}
