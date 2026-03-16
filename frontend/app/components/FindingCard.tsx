"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import { SeverityBadge } from "./SeverityBadge";
import { apiFetch } from "@/lib/api";

interface Finding {
  id: string;
  scan_id: string;
  identity_hash: string;
  severity: string;
  vulnerability_type: string;
  file_path: string;
  line_number: number;
  code_snippet: string;
  description: string;
  explanation: string;
  triage_status: string | null;
  triage_notes: string | null;
  created_at: string;
}

interface FindingCardProps {
  finding: Finding;
  onTriageUpdate?: (findingId: string, status: string, notes: string | null) => void;
}

const TRIAGE_BADGE: Record<string, string> = {
  open: "border-gray-300 text-gray-600",
  false_positive: "border-yellow-400 text-yellow-700",
  resolved: "border-green-400 text-green-700",
};

export function FindingCard({ finding, onTriageUpdate }: FindingCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [triageStatus, setTriageStatus] = useState(finding.triage_status || "");
  const [triageNotes, setTriageNotes] = useState(finding.triage_notes || "");
  const [saving, setSaving] = useState(false);

  async function handleSaveTriage() {
    setSaving(true);
    const res = await apiFetch(`/api/findings/${finding.id}/triage`, {
      method: "PATCH",
      body: JSON.stringify({ status: triageStatus, notes: triageNotes || null }),
    });
    if (res.success && onTriageUpdate) {
      onTriageUpdate(finding.id, triageStatus, triageNotes || null);
    }
    setSaving(false);
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Collapsed header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-gray-50"
      >
        {expanded ? (
          <ChevronDownIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
        <SeverityBadge severity={finding.severity} />
        {finding.triage_status && (
          <span className={`px-2 py-0.5 rounded text-xs font-medium border ${TRIAGE_BADGE[finding.triage_status] || ""}`}>
            {finding.triage_status === "false_positive" ? "FP" : finding.triage_status === "resolved" ? "Resolved" : "Open"}
          </span>
        )}
        <span className="font-medium text-sm text-gray-900">{finding.vulnerability_type}</span>
        <span className="text-xs text-gray-500 ml-auto">
          {finding.file_path}:{finding.line_number}
        </span>
      </button>

      {/* Collapsed description */}
      {!expanded && (
        <p className="px-4 pb-3 text-sm text-gray-600 line-clamp-2 pl-11">
          {finding.description}
        </p>
      )}

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-4 pl-11 space-y-3 border-t border-gray-100 pt-3">
          <div>
            <p className="text-sm font-medium text-gray-700 mb-1">Description</p>
            <p className="text-sm text-gray-600">{finding.description}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-1">Explanation</p>
            <p className="text-sm text-gray-600">{finding.explanation}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-700 mb-1">Code</p>
            <pre className="bg-gray-900 text-gray-100 text-xs p-3 rounded-lg overflow-x-auto">
              <code>{finding.code_snippet}</code>
            </pre>
          </div>

          {/* Triage controls */}
          <div className="border-t border-gray-100 pt-3 mt-3">
            <p className="text-sm font-medium text-gray-700 mb-2">Triage</p>
            <div className="flex gap-2 mb-2">
              {["open", "false_positive", "resolved"].map((s) => (
                <button
                  key={s}
                  onClick={() => setTriageStatus(s)}
                  className={`px-3 py-1 rounded text-xs font-medium border ${
                    triageStatus === s
                      ? "bg-gray-900 text-white border-gray-900"
                      : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
                  }`}
                >
                  {s === "false_positive" ? "False Positive" : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            <textarea
              value={triageNotes}
              onChange={(e) => setTriageNotes(e.target.value)}
              placeholder="Optional notes..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none"
              rows={2}
            />
            <button
              onClick={handleSaveTriage}
              disabled={saving || !triageStatus}
              className="mt-2 px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Triage"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
