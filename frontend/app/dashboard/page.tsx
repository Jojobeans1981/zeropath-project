"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { NavHeader } from "@/components/NavHeader";

interface Repo {
  id: string;
  url: string;
  name: string;
  scan_count: number;
  created_at: string;
  updated_at: string;
}

interface DashboardStats {
  total_repos: number;
  total_scans: number;
  total_findings: number;
  severity_breakdown: Record<string, number>;
  triage_breakdown: Record<string, number>;
  top_vulnerability_types: { type: string; count: number }[];
  language_breakdown: Record<string, number>;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-blue-500",
  informational: "bg-gray-400",
};

export default function DashboardPage() {
  const router = useRouter();
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [githubToken, setGithubToken] = useState("");
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    async function fetchData() {
      const [repoRes, statsRes] = await Promise.all([
        apiFetch<Repo[]>("/api/repos/"),
        apiFetch<DashboardStats>("/api/stats/dashboard"),
      ]);
      if (repoRes.success && repoRes.data) setRepos(repoRes.data);
      if (statsRes.success && statsRes.data) setStats(statsRes.data);
      setLoading(false);
    }

    fetchData();
  }, [router]);

  async function handleAddRepo(e: React.FormEvent) {
    e.preventDefault();
    setAddLoading(true);
    setAddError("");

    const body: Record<string, string> = { url };
    if (githubToken) body.github_token = githubToken;

    const res = await apiFetch<Repo>("/api/repos/", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (res.success && res.data) {
      setRepos([res.data, ...repos]);
      setUrl("");
      setGithubToken("");
      setShowAdvanced(false);
    } else {
      setAddError(res.error?.message || "Failed to add repository.");
    }

    setAddLoading(false);
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      <NavHeader />
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 border border-gray-100 dark:border-slate-700">
              <p className="text-2xl font-bold">{stats.total_repos}</p>
              <p className="text-sm text-gray-500 dark:text-slate-400">Repositories</p>
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 border border-gray-100 dark:border-slate-700">
              <p className="text-2xl font-bold">{stats.total_scans}</p>
              <p className="text-sm text-gray-500 dark:text-slate-400">Scans</p>
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 border border-gray-100 dark:border-slate-700">
              <p className="text-2xl font-bold">{stats.total_findings}</p>
              <p className="text-sm text-gray-500 dark:text-slate-400">Findings</p>
            </div>
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 border border-gray-100 dark:border-slate-700">
              <div className="flex gap-1 mb-1">
                {Object.entries(stats.severity_breakdown).map(([sev, count]) => (
                  <div
                    key={sev}
                    className={`h-4 rounded ${SEVERITY_COLORS[sev] || "bg-gray-300"}`}
                    style={{ width: `${Math.max((count / stats.total_findings) * 100, 8)}%` }}
                    title={`${sev}: ${count}`}
                  />
                ))}
              </div>
              <p className="text-sm text-gray-500 dark:text-slate-400">Severity Distribution</p>
            </div>
          </div>
        )}

        {/* Top vulns bar */}
        {stats && stats.top_vulnerability_types.length > 0 && (
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 border border-gray-100 dark:border-slate-700 mb-8">
            <h3 className="text-sm font-medium text-gray-700 dark:text-slate-300 mb-3">Top Vulnerability Types</h3>
            <div className="space-y-2">
              {stats.top_vulnerability_types.slice(0, 5).map((v) => (
                <div key={v.type} className="flex items-center gap-3">
                  <div className="w-32 text-xs text-gray-600 dark:text-slate-400 truncate">{v.type}</div>
                  <div className="flex-1 bg-gray-100 dark:bg-slate-700 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${(v.count / stats.top_vulnerability_types[0].count) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 dark:text-slate-400 w-8 text-right">{v.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <h1 className="text-2xl font-bold mb-6">Your Repositories</h1>

        <form onSubmit={handleAddRepo} className="mb-6">
          <div className="flex gap-3">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo"
              className="border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 rounded-lg px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            <button
              type="submit"
              disabled={addLoading}
              className="bg-blue-600 text-white rounded-lg px-4 py-2 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap transition-colors"
            >
              {addLoading ? "Adding..." : "Add Repository"}
            </button>
          </div>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-xs text-blue-600 dark:text-blue-400 hover:underline mt-2"
          >
            {showAdvanced ? "Hide advanced options" : "Show advanced options"}
          </button>
          {showAdvanced && (
            <div className="mt-2">
              <input
                type="password"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                placeholder="GitHub personal access token"
                className="border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-800 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                Required for private repositories. Encrypted at rest.
              </p>
            </div>
          )}
        </form>
        {addError && <p className="text-red-600 text-sm mb-4">{addError}</p>}

        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse bg-gray-200 dark:bg-slate-700 rounded-xl h-20" />
            ))}
          </div>
        ) : repos.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-400 dark:text-slate-500 text-lg">No repositories yet</p>
            <p className="text-gray-400 dark:text-slate-500 text-sm mt-1">Add a Git repository URL above to get started.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {repos.map((repo, i) => (
              <Link key={repo.id} href={`/repos/${repo.id}`}>
                <div
                  className="bg-white dark:bg-slate-800 rounded-xl shadow-sm p-4 hover:shadow-md dark:hover:bg-slate-750 transition-all cursor-pointer border border-gray-100 dark:border-slate-700 animate-slide-in"
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{repo.name}</p>
                      <p className="text-sm text-gray-500 dark:text-slate-400">{repo.url}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="bg-gray-100 dark:bg-slate-700 text-gray-700 dark:text-slate-300 text-xs px-2 py-1 rounded-full">
                        {repo.scan_count} scans
                      </span>
                      <span className="text-xs text-gray-400 dark:text-slate-500">
                        {new Date(repo.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
