"use client";
import { useState } from "react";
import InputPanel from "@/components/InputPanel";
import ReferencePanel from "@/components/ReferencePanel";
import DraftEditor from "@/components/DraftEditor";
import KnowledgeBase from "@/components/KnowledgeBase";
import type { SearchResult } from "@/lib/api";

type Step = "input" | "references" | "draft";

export interface DraftParams {
  topic: string;
  doc_type: string;
  tone: string;
  language: string;
  extra_instructions: string;
}

export default function HomePage() {
  const [step, setStep] = useState<Step>("input");
  const [showKB, setShowKB] = useState(false);
  const [params, setParams] = useState<DraftParams | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<SearchResult[]>([]);
  const [draft, setDraft] = useState("");

  const steps = [
    { id: "input" as Step, label: "Input", num: 1 },
    { id: "references" as Step, label: "References", num: 2 },
    { id: "draft" as Step, label: "Draft", num: 3 },
  ];

  return (
    <div>
      <div className="flex items-center gap-0 mb-8">
        {steps.map((s, i) => (
          <div key={s.id} className="flex items-center">
            <button
              onClick={() => setStep(s.id)}
              className={
                "flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-colors " +
                (step === s.id ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-400")
              }
            >
              <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-xs font-bold">
                {s.num}
              </span>
              {s.label}
            </button>
            {i < steps.length - 1 && <div className="w-8 h-0.5 bg-gray-200 mx-1" />}
          </div>
        ))}
        <div className="ml-auto">
          <button
            onClick={() => setShowKB(!showKB)}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-600"
          >
            {showKB ? "Hide" : "Manage"} Knowledge Base
          </button>
        </div>
      </div>

      {showKB && (
        <div className="mb-6">
          <KnowledgeBase />
        </div>
      )}

      {step === "input" && (
        <InputPanel
          onSearch={(p, results) => {
            setParams(p);
            setSearchResults(results);
            setSelectedDocs([]);
            setStep("references");
          }}
        />
      )}

      {step === "references" && params && (
        <ReferencePanel
          results={searchResults}
          selected={selectedDocs}
          onSelectionChange={setSelectedDocs}
          onGenerate={(docs) => {
            setSelectedDocs(docs);
            setStep("draft");
          }}
          onBack={() => setStep("input")}
        />
      )}

      {step === "draft" && params && (
        <DraftEditor
          params={params}
          selectedDocIds={selectedDocs.map((d) => d.doc_id)}
          initialDraft={draft}
          onDraftChange={setDraft}
          onBack={() => setStep("references")}
        />
      )}
    </div>
  );
}
