"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { setTokens } from "@/lib/auth";

interface SignupForm {
  email: string;
  password: string;
  confirmPassword: string;
}

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState<SignupForm>({ email: "", password: "", confirmPassword: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      setLoading(false);
      return;
    }

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      setLoading(false);
      return;
    }

    try {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>(
        "/api/auth/signup",
        { method: "POST", body: JSON.stringify({ email: form.email, password: form.password }) }
      );

      if (res.success && res.data) {
        setTokens(res.data.access_token, res.data.refresh_token);
        router.push("/dashboard");
      } else {
        setError(res.error?.message || "Signup failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-gray-50 dark:bg-slate-900 min-h-screen flex items-center justify-center">
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-8 w-full max-w-md border border-gray-100 dark:border-slate-700">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold"><span className="text-blue-500">Zero</span>Path</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Create your account</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="text-sm font-medium text-gray-700 dark:text-slate-300">Email</label>
            <input id="email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          </div>
          <div>
            <label htmlFor="password" className="text-sm font-medium text-gray-700 dark:text-slate-300">Password</label>
            <input id="password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          </div>
          <div>
            <label htmlFor="confirmPassword" className="text-sm font-medium text-gray-700 dark:text-slate-300">Confirm Password</label>
            <input id="confirmPassword" type="password" value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} className="border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-700 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500" required />
          </div>
          {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
          <button type="submit" disabled={loading} className="bg-blue-600 text-white rounded-lg px-4 py-2 w-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="text-sm text-center mt-4 text-gray-600 dark:text-slate-400">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-500 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
