"use client";

interface StatusBadgeProps {
  status: string;
}

const STATUS_COLORS: Record<string, string> = {
  queued: "bg-gray-100 text-gray-700",
  running: "bg-blue-100 text-blue-700 animate-pulse",
  complete: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.queued;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {status}
    </span>
  );
}
