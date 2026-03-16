"use client";

import { useState } from "react";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
import { FindingCard } from "./FindingCard";

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
  created_at: string;
  triage_status: string | null;
  triage_notes: string | null;
}

interface ComparisonData {
  base_scan_id: string;
  head_scan_id: string;
  counts: { new: number; fixed: number; persisting: number };
  new: Finding[];
  fixed: Finding[];
  persisting: Finding[];
}

interface ComparisonTableProps {
  data: ComparisonData;
  onTriageUpdate?: (findingId: string, status: string, notes: string | null) => void;
}

interface SectionProps {
  title: string;
  subtitle: string;
  count: number;
  findings: Finding[];
  borderColor: string;
  textColor: string;
  defaultExpanded: boolean;
  onTriageUpdate?: (findingId: string, status: string, notes: string | null) => void;
}

function ComparisonSection({ title, subtitle, count, findings, borderColor, textColor, defaultExpanded, onTriageUpdate }: SectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className={`border-l-4 ${borderColor} bg-white rounded-r-lg shadow-sm`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-2 text-left hover:bg-gray-50"
      >
        {expanded ? <ChevronDownIcon className="w-4 h-4" /> : <ChevronRightIcon className="w-4 h-4" />}
        <span className={`font-medium ${textColor}`}>{title} ({count})</span>
      </button>
      {!expanded && <p className="px-4 pb-2 text-xs text-gray-500 pl-10">{subtitle}</p>}
      {expanded && (
        <div className="px-4 pb-4 space-y-2">
          <p className="text-xs text-gray-500 mb-2">{subtitle}</p>
          {findings.map((f) => (
            <FindingCard key={f.id} finding={f} onTriageUpdate={onTriageUpdate} />
          ))}
          {findings.length === 0 && (
            <p className="text-sm text-gray-400 italic">None</p>
          )}
        </div>
      )}
    </div>
  );
}

export function ComparisonTable({ data, onTriageUpdate }: ComparisonTableProps) {
  return (
    <div className="space-y-4">
      <ComparisonSection
        title="New Findings"
        subtitle="Vulnerabilities found in the latest scan that weren't in the previous scan"
        count={data.counts.new}
        findings={data.new}
        borderColor="border-red-500"
        textColor="text-red-700"
        defaultExpanded={data.counts.new > 0}
        onTriageUpdate={onTriageUpdate}
      />
      <ComparisonSection
        title="Fixed Findings"
        subtitle="Vulnerabilities from the previous scan that are no longer present"
        count={data.counts.fixed}
        findings={data.fixed}
        borderColor="border-green-500"
        textColor="text-green-700"
        defaultExpanded={data.counts.fixed > 0}
        onTriageUpdate={onTriageUpdate}
      />
      <ComparisonSection
        title="Persisting Findings"
        subtitle="Vulnerabilities present in both scans"
        count={data.counts.persisting}
        findings={data.persisting}
        borderColor="border-gray-400"
        textColor="text-gray-700"
        defaultExpanded={data.counts.persisting > 0}
        onTriageUpdate={onTriageUpdate}
      />
    </div>
  );
}
