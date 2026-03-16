"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";
import { NavHeader } from "@/components/NavHeader";

interface UserRow {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    async function init() {
      // Check if admin
      const meRes = await apiFetch<{ id: string; email: string; role: string }>("/api/auth/me");
      if (!meRes.success || !meRes.data || meRes.data.role !== "admin") {
        router.replace("/dashboard");
        return;
      }
      setCurrentUserId(meRes.data.id);

      // Fetch users
      const usersRes = await apiFetch<UserRow[]>("/api/admin/users");
      if (usersRes.success && usersRes.data) {
        setUsers(usersRes.data);
      }
      setLoading(false);
    }

    init();
  }, [router]);

  async function handleRoleChange(userId: string, newRole: string) {
    const res = await apiFetch<{ id: string; email: string; role: string }>(
      `/api/admin/users/${userId}`,
      { method: "PATCH", body: JSON.stringify({ role: newRole }) }
    );
    if (res.success && res.data) {
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: res.data!.role } : u))
      );
      setError("");
    } else {
      setError(res.error?.message || "Failed to update role.");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavHeader />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">User Management</h1>

        {error && <p className="text-red-600 text-sm mb-4">{error}</p>}

        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse bg-gray-200 rounded-lg h-12" />
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-700">Email</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-700">Role</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-700">Created</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b last:border-b-0">
                    <td className="px-4 py-3 text-sm">{user.email}</td>
                    <td className="px-4 py-3">
                      <select
                        value={user.role}
                        onChange={(e) => handleRoleChange(user.id, e.target.value)}
                        disabled={user.id === currentUserId}
                        className="border border-gray-300 rounded px-2 py-1 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <option value="admin">admin</option>
                        <option value="member">member</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
