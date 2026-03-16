"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { clearTokens, getAccessToken } from "@/lib/auth";

export function NavHeader() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!getAccessToken()) return;

    async function fetchUser() {
      const res = await apiFetch<{ id: string; email: string; created_at: string }>("/api/auth/me");
      if (res.success && res.data) {
        setEmail(res.data.email);
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
    <nav className="bg-gray-900 text-white px-6 py-3 flex items-center justify-between sticky top-0 z-50">
      <Link href="/dashboard" className="font-bold text-lg">
        ZeroPath
      </Link>
      <div className="flex items-center gap-4">
        {email && <span className="text-sm text-gray-300">{email}</span>}
        {email && (
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-white"
          >
            Logout
          </button>
        )}
      </div>
    </nav>
  );
}
