"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { clearTokens, getAccessToken } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

export function NavHeader() {
  const router = useRouter();
  const { dark, toggle } = useTheme();
  const [email, setEmail] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) return;

    async function fetchUser() {
      const res = await apiFetch<{ id: string; email: string; role: string; created_at: string }>("/api/auth/me");
      if (res.success && res.data) {
        setEmail(res.data.email);
        setRole(res.data.role);
      } else {
        clearTokens();
        router.push("/login");
      }
    }

    fetchUser();
  }, [router]);

  function handleLogout() {
    clearTokens();
    router.push("/login");
  }

  return (
    <nav className="bg-gray-900 dark:bg-slate-950 text-white px-6 py-3 flex items-center justify-between sticky top-0 z-50 border-b border-gray-800 dark:border-slate-800">
      <div className="flex items-center gap-6">
        <Link href="/dashboard" className="font-bold text-lg tracking-tight">
          <span className="text-blue-400">Zero</span>Path
        </Link>
        <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white transition-colors">
          Dashboard
        </Link>
        {role === "admin" && (
          <Link href="/admin" className="text-sm text-gray-400 hover:text-white transition-colors">
            Admin
          </Link>
        )}
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={toggle}
          className="text-gray-400 hover:text-white transition-colors text-sm"
          title={dark ? "Switch to light mode" : "Switch to dark mode"}
        >
          {dark ? "☀️" : "🌙"}
        </button>
        {email && <span className="text-sm text-gray-400">{email}</span>}
        {email && (
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-white transition-colors"
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
