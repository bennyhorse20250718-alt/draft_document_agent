"use client";
import { useState, useEffect, useRef } from "react";
import { listDocuments, uploadDocument, deleteDocument } from "@/lib/api";
import type { DocumentSummary } from "@/lib/api";

const DOC_TYPES = ["Official Reply", "Press Release", "Policy Statement", "Announcement", "Other"];
const TONES = ["Formal", "Neutral", "Urgent"];
const LANGUAGES = ["English", "Chinese", "Bilingual"];

export default function KnowledgeBase() {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [meta, setMeta] = useState({ doc_type: "Official Reply", topic: "", date: "", tone: "Formal", department: "", language: "English" });

  async function refresh() {
    setLoading(true);
    try {
      setDocs(await listDocuments());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      const result = await uploadDocument(file, meta);
      setSuccess(`Ingested "${result.source}" — ${result.chunks} chunks stored.`);
      await refresh();
      if (fileRef.current) fileRef.current.value = "";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(doc_id: string, source: string) {
    if (!confirm(`Delete "${source}" from the knowledge base?`)) return;
    setError("");
    try {
      await deleteDocument(doc_id);
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="p-4 border-b">
        <h2 className="font-semibold text-gray-800">Knowledge Base</h2>
        <p className="text-xs text-gray-500 mt-0.5">Upload and manage reference documents</p>
      </div>

      <div className="p-4 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload form */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">Upload Document</h3>
          <form onSubmit={handleUpload} className="space-y-3">
            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="block w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100" />
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Type</label>
                <select value={meta.doc_type} onChange={e => setMeta(m => ({...m, doc_type: e.target.value}))} className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {DOC_TYPES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Tone</label>
                <select value={meta.tone} onChange={e => setMeta(m => ({...m, tone: e.target.value}))} className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {TONES.map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Language</label>
                <select value={meta.language} onChange={e => setMeta(m => ({...m, language: e.target.value}))} className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {LANGUAGES.map(l => <option key={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Date</label>
                <input type="text" placeholder="2024-01-01" value={meta.date} onChange={e => setMeta(m => ({...m, date: e.target.value}))} className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <input type="text" placeholder="Topic (optional)" value={meta.topic} onChange={e => setMeta(m => ({...m, topic: e.target.value}))} className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <input type="text" placeholder="Department (optional)" value={meta.department} onChange={e => setMeta(m => ({...m, department: e.target.value}))} className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500" />
            {error && <p className="text-xs text-red-600 bg-red-50 px-2 py-1.5 rounded-lg">{error}</p>}
            {success && <p className="text-xs text-green-700 bg-green-50 px-2 py-1.5 rounded-lg">{success}</p>}
            <button type="submit" disabled={uploading} className="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
              {uploading ? "Uploading..." : "Upload & Ingest"}
            </button>
          </form>
        </div>

        {/* Document list */}
        <div>
          <h3 className="text-sm font-medium text-gray-700 mb-3">Ingested Documents ({docs.length})</h3>
          {loading ? (
            <p className="text-sm text-gray-500">Loading...</p>
          ) : docs.length === 0 ? (
            <p className="text-sm text-gray-400 italic">No documents yet. Upload your first document above.</p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {docs.map(doc => (
                <div key={doc.doc_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-800 truncate">{doc.source}</p>
                    <p className="text-xs text-gray-500">{doc.doc_type} · {doc.language} · {doc.total_chunks} chunks</p>
                  </div>
                  <button onClick={() => handleDelete(doc.doc_id, doc.source)} className="ml-3 text-red-400 hover:text-red-600 text-sm shrink-0" title="Delete">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
