"use client";

interface SeverityBadgeProps {
  severity: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-800 border-red-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-blue-100 text-blue-800 border-blue-200",
  informational: "bg-gray-100 text-gray-800 border-gray-200",
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const colors = SEVERITY_COLORS[severity] || SEVERITY_COLORS.informational;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium border ${colors}`}>
      {severity}
    </span>
  );
}
