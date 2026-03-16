"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { NavHeader } from "@/components/NavHeader";
import { StatusBadge } from "@/components/StatusBadge";

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

interface RepoDetail {
  id: string;
  url: string;
  name: string;
  scan_count: number;
  scans: Scan[];
  created_at: string;
  updated_at: string;
}

export default function RepoDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const [repo, setRepo] = useState<RepoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scanLoading, setScanLoading] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    async function fetchRepo() {
      const res = await apiFetch<RepoDetail>(`/api/repos/${id}`);
      if (res.success && res.data) {
        setRepo(res.data);
      } else {
        setError(res.error?.message || "Failed to load repository.");
      }
      setLoading(false);
    }

    fetchRepo();
  }, [router, id]);

  async function handleNewScan() {
    setScanLoading(true);
    const res = await apiFetch<Scan>("/api/scans/", {
      method: "POST",
      body: JSON.stringify({ repo_id: id }),
    });
    if (res.success && res.data) {
      router.push(`/scans/${res.data.id}`);
    }
    setScanLoading(false);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavHeader />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Link href="/dashboard" className="text-blue-600 hover:underline text-sm mb-4 inline-block">
          &larr; Back to Dashboard
        </Link>

        {loading ? (
          <div className="space-y-4 mt-4">
            <div className="animate-pulse bg-gray-200 rounded-lg h-8 w-64" />
            <div className="animate-pulse bg-gray-200 rounded-lg h-4 w-96" />
            <div className="animate-pulse bg-gray-200 rounded-lg h-20" />
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-4">
            <p className="text-red-700">{error}</p>
          </div>
        ) : repo ? (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <h1 className="text-2xl font-bold">{repo.name}</h1>
              <button
                onClick={handleNewScan}
                disabled={scanLoading}
                className="bg-blue-600 text-white rounded-lg px-4 py-2 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {scanLoading ? "Starting Scan..." : "New Scan"}
              </button>
            </div>
            <a
              href={repo.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline text-sm"
            >
              {repo.url}
            </a>
            <div className="flex gap-4 mt-3 text-sm text-gray-500">
              <span>Created: {new Date(repo.created_at).toLocaleDateString()}</span>
              <span>{repo.scan_count} scans</span>
            </div>

            {/* Scan History */}
            <div className="mt-8">
              <h2 className="text-lg font-semibold mb-4">Scan History</h2>
              {repo.scans.length === 0 ? (
                <p className="text-gray-500 text-center py-8">
                  No scans yet. Click &quot;New Scan&quot; to analyze this repository.
                </p>
              ) : (
                <div className="space-y-1">
                  {repo.scans.map((scan, index) => (
                    <div key={scan.id}>
                      <Link href={`/scans/${scan.id}`}>
                        <div className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow cursor-pointer">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <StatusBadge status={scan.status} />
                              <span className="text-sm text-gray-700">
                                {new Date(scan.created_at).toLocaleString()}
                              </span>
                            </div>
                            <div className="flex items-center gap-3 text-sm text-gray-500">
                              {scan.commit_sha && <span>{scan.commit_sha.slice(0, 7)}</span>}
                              <span>{scan.files_scanned} files</span>
                            </div>
                          </div>
                        </div>
                      </Link>
                      {/* Compare link between consecutive complete scans */}
                      {index < repo.scans.length - 1 &&
                        scan.status === "complete" &&
                        repo.scans[index + 1].status === "complete" && (
                          <div className="text-center py-1">
                            <Link
                              href={`/scans/${scan.id}?compare=${repo.scans[index + 1].id}`}
                              className="text-xs text-blue-500 hover:underline"
                            >
                              Compare &harr;
                            </Link>
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
