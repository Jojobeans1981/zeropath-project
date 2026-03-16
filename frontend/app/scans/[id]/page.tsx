"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { NavHeader } from "@/components/NavHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { SeverityBadge } from "@/components/SeverityBadge";
import { FindingCard } from "@/components/FindingCard";
import { ComparisonTable } from "@/components/ComparisonTable";

interface Scan {
  id: string;
  repo_id: string;
  status: string;
  commit_sha: string | null;
  error_message: string | null;
  files_scanned: number;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

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

interface ComparisonData {
  base_scan_id: string;
  head_scan_id: string;
  counts: { new: number; fixed: number; persisting: number };
  new: Finding[];
  fixed: Finding[];
  persisting: Finding[];
}

interface RepoDetail {
  id: string;
  url: string;
  name: string;
  scan_count: number;
  scans: Scan[];
  created_at: string;
  updated_at: string;
}

export default function ScanDetailPage() {
  const router = useRouter();
  const params = useParams();
  const searchParams = useSearchParams();
  const id = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const scanRef = useRef<Scan | null>(null);
  const [triageFilter, setTriageFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  // Comparison state
  const [otherScans, setOtherScans] = useState<Scan[]>([]);
  const [compareWith, setCompareWith] = useState<string | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
  const [comparingLoading, setComparingLoading] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    const fetchScan = async () => {
      const res = await apiFetch<Scan>(`/api/scans/${id}`);
      if (res.success && res.data) {
        setScan(res.data);
        scanRef.current = res.data;
        if (res.data.status === "complete") {
          const findingsRes = await apiFetch<Finding[]>(`/api/scans/${id}/findings`);
          if (findingsRes.success && findingsRes.data) {
            setFindings(findingsRes.data);
          }

          // Fetch other scans for comparison dropdown
          const repoRes = await apiFetch<RepoDetail>(`/api/repos/${res.data.repo_id}`);
          if (repoRes.success && repoRes.data) {
            setOtherScans(repoRes.data.scans.filter(s => s.id !== id && s.status === "complete"));
          }
        }
      } else {
        setError(res.error?.message || "Failed to load scan.");
      }
      setLoading(false);
    };

    fetchScan();
    const interval = setInterval(() => {
      if (!scanRef.current || scanRef.current.status === "queued" || scanRef.current.status === "running") {
        fetchScan();
      } else {
        clearInterval(interval);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [id, router]);

  // Auto-trigger comparison from URL query param
  useEffect(() => {
    const compareParam = searchParams.get("compare");
    if (compareParam && scan?.status === "complete" && !comparisonData && !comparingLoading) {
      handleCompare(compareParam);
    }
  }, [searchParams, scan]);

  const handleCompare = async (baseScanId: string) => {
    setComparingLoading(true);
    setCompareWith(baseScanId);
    const res = await apiFetch<ComparisonData>(`/api/scans/compare?base=${baseScanId}&head=${id}`);
    if (res.success && res.data) setComparisonData(res.data);
    setComparingLoading(false);
  };

  const clearComparison = () => {
    setCompareWith(null);
    setComparisonData(null);
  };

  const handleTriageUpdate = (findingId: string, status: string, notes: string | null) => {
    setFindings((prev) =>
      prev.map((f) =>
        f.id === findingId ? { ...f, triage_status: status, triage_notes: notes } : f
      )
    );
    // Also update comparison data if active
    if (comparisonData) {
      setComparisonData((prev) => {
        if (!prev) return prev;
        const updateList = (list: Finding[]) =>
          list.map((f) => (f.id === findingId ? { ...f, triage_status: status, triage_notes: notes } : f));
        return {
          ...prev,
          new: updateList(prev.new),
          fixed: updateList(prev.fixed),
          persisting: updateList(prev.persisting),
        };
      });
    }
  };

  const filteredFindings = findings.filter((f) => {
    if (triageFilter !== "all" && (f.triage_status || "open") !== triageFilter) return false;
    if (severityFilter !== "all" && f.severity !== severityFilter) return false;
    return true;
  });

  const severityCounts = findings.reduce<Record<string, number>>((acc, f) => {
    acc[f.severity] = (acc[f.severity] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gray-50">
      <NavHeader />
      <div className="max-w-4xl mx-auto px-4 py-8">
        {scan && (
          <Link href={`/repos/${scan.repo_id}`} className="text-blue-600 hover:underline text-sm mb-4 inline-block">
            &larr; Back
          </Link>
        )}

        {loading ? (
          <div className="space-y-4 mt-4">
            <div className="animate-pulse bg-gray-200 rounded-lg h-24" />
            <div className="animate-pulse bg-gray-200 rounded-lg h-16" />
            <div className="animate-pulse bg-gray-200 rounded-lg h-16" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-4">
            <p className="text-red-700">{error}</p>
          </div>
        ) : scan ? (
          <>
            {/* Scan header card */}
            <div className="bg-white rounded-lg shadow p-4 mt-4 mb-6">
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-xl font-bold">Scan</h1>
                <StatusBadge status={scan.status} />
              </div>
              <div className="flex gap-4 text-sm text-gray-500">
                {scan.commit_sha && <span>Commit: {scan.commit_sha.slice(0, 7)}</span>}
                <span>{scan.files_scanned} files scanned</span>
                {scan.started_at && <span>Started: {new Date(scan.started_at).toLocaleString()}</span>}
                {scan.completed_at && <span>Completed: {new Date(scan.completed_at).toLocaleString()}</span>}
              </div>
            </div>

            {/* Queued/Running state */}
            {(scan.status === "queued" || scan.status === "running") && (
              <div className="text-center py-12">
                <p className="text-blue-600 animate-pulse text-lg">
                  Scan in progress... Analyzing repository for security vulnerabilities.
                </p>
              </div>
            )}

            {/* Failed state */}
            {scan.status === "failed" && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-700 font-medium">Scan failed</p>
                {scan.error_message && <p className="text-red-600 text-sm mt-1">{scan.error_message}</p>}
              </div>
            )}

            {/* Complete state */}
            {scan.status === "complete" && (
              <div className="space-y-4">
                {/* Comparison controls */}
                {otherScans.length > 0 && (
                  <div className="flex items-center gap-3">
                    {!comparisonData ? (
                      <>
                        <span className="text-sm text-gray-600">Compare with:</span>
                        <select
                          onChange={(e) => e.target.value && handleCompare(e.target.value)}
                          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                          defaultValue=""
                        >
                          <option value="" disabled>Select a scan...</option>
                          {otherScans.map((s) => (
                            <option key={s.id} value={s.id}>
                              {new Date(s.created_at).toLocaleString()} — {s.commit_sha?.slice(0, 7) || "no SHA"}
                            </option>
                          ))}
                        </select>
                        {comparingLoading && <span className="text-sm text-blue-600 animate-pulse">Loading...</span>}
                      </>
                    ) : (
                      <button
                        onClick={clearComparison}
                        className="text-sm text-blue-600 hover:underline"
                      >
                        Clear comparison
                      </button>
                    )}
                  </div>
                )}

                {/* Comparison view */}
                {comparisonData ? (
                  <ComparisonTable data={comparisonData} onTriageUpdate={handleTriageUpdate} />
                ) : (
                  <>
                    {/* Severity summary */}
                    {findings.length > 0 && (
                      <>
                        <div className="flex items-center justify-between">
                          <h2 className="text-lg font-semibold">
                            {findings.length} {findings.length === 1 ? "Finding" : "Findings"}
                          </h2>
                          <div className="flex gap-2">
                            {["critical", "high", "medium", "low", "informational"]
                              .filter((s) => severityCounts[s])
                              .map((s) => (
                                <span key={s} className="flex items-center gap-1">
                                  <SeverityBadge severity={s} />
                                  <span className="text-xs text-gray-500">{severityCounts[s]}</span>
                                </span>
                              ))}
                          </div>
                        </div>

                        {/* Filter bar */}
                        <div className="flex items-center gap-4 flex-wrap">
                          <div className="flex gap-1">
                            {[
                              { key: "all", label: `All (${findings.length})` },
                              { key: "open", label: "Open" },
                              { key: "false_positive", label: "False Positive" },
                              { key: "resolved", label: "Resolved" },
                            ].map((f) => (
                              <button
                                key={f.key}
                                onClick={() => setTriageFilter(f.key)}
                                className={`px-3 py-1 rounded-full text-xs font-medium ${
                                  triageFilter === f.key
                                    ? "bg-gray-900 text-white"
                                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                                }`}
                              >
                                {f.label}
                              </button>
                            ))}
                          </div>
                          <span className="text-gray-300">|</span>
                          <div className="flex gap-1">
                            {[
                              { key: "all", label: "All" },
                              { key: "critical", label: "Critical" },
                              { key: "high", label: "High" },
                              { key: "medium", label: "Medium" },
                              { key: "low", label: "Low" },
                              { key: "informational", label: "Info" },
                            ].map((f) => (
                              <button
                                key={f.key}
                                onClick={() => setSeverityFilter(f.key)}
                                className={`px-3 py-1 rounded-full text-xs font-medium ${
                                  severityFilter === f.key
                                    ? "bg-gray-900 text-white"
                                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                                }`}
                              >
                                {f.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Filtered findings */}
                        {filteredFindings.length === 0 ? (
                          <p className="text-gray-500 text-center py-8">No findings match the selected filters.</p>
                        ) : (
                          filteredFindings.map((f) => (
                            <FindingCard key={f.id} finding={f} onTriageUpdate={handleTriageUpdate} />
                          ))
                        )}
                      </>
                    )}

                    {/* No findings */}
                    {findings.length === 0 && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
                        <p className="text-green-700 font-medium text-lg">No vulnerabilities found</p>
                        <p className="text-green-600 text-sm mt-1">This scan completed without detecting any security issues.</p>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
