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

export default function DashboardPage() {
  const router = useRouter();
  const [repos, setRepos] = useState<Repo[]>([]);
  const [loading, setLoading] = useState(true);
  const [url, setUrl] = useState("");
  const [addError, setAddError] = useState("");
  const [addLoading, setAddLoading] = useState(false);

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    async function fetchRepos() {
      const res = await apiFetch<Repo[]>("/api/repos");
      if (res.success && res.data) {
        setRepos(res.data);
      }
      setLoading(false);
    }

    fetchRepos();
  }, [router]);

  async function handleAddRepo(e: React.FormEvent) {
    e.preventDefault();
    setAddLoading(true);
    setAddError("");

    const res = await apiFetch<Repo>("/api/repos", {
      method: "POST",
      body: JSON.stringify({ url }),
    });

    if (res.success && res.data) {
      setRepos([res.data, ...repos]);
      setUrl("");
    } else {
      setAddError(res.error?.message || "Failed to add repository.");
    }

    setAddLoading(false);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavHeader />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Your Repositories</h1>

        <form onSubmit={handleAddRepo} className="flex gap-3 mb-6">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="border border-gray-300 rounded-lg px-3 py-2 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
          <button
            type="submit"
            disabled={addLoading}
            className="bg-blue-600 text-white rounded-lg px-4 py-2 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
          >
            {addLoading ? "Adding..." : "Add Repository"}
          </button>
        </form>
        {addError && <p className="text-red-600 text-sm mb-4">{addError}</p>}

        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse bg-gray-200 rounded-lg h-20" />
            ))}
          </div>
        ) : repos.length === 0 ? (
          <p className="text-gray-500 text-center py-12">
            No repositories yet. Add a Git repository URL above to get started.
          </p>
        ) : (
          <div className="space-y-4">
            {repos.map((repo) => (
              <Link key={repo.id} href={`/repos/${repo.id}`}>
                <div className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow cursor-pointer">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{repo.name}</p>
                      <p className="text-sm text-gray-500">{repo.url}</p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="bg-gray-100 text-gray-700 text-xs px-2 py-1 rounded-full">
                        {repo.scan_count} scans
                      </span>
                      <span className="text-xs text-gray-400">
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
