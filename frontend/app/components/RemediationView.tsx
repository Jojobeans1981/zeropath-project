"use client";

interface RemediationViewProps {
  original: string;
  fixed: string;
  explanation: string;
  confidence: string;
}

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

export function RemediationView({ original, fixed, explanation, confidence }: RemediationViewProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-700">Suggested Fix</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${CONFIDENCE_COLORS[confidence] || CONFIDENCE_COLORS.medium}`}>
          {confidence} confidence
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <div>
          <p className="text-xs text-red-600 font-medium mb-1">Original (vulnerable)</p>
          <pre className="bg-red-950 text-red-200 text-xs p-3 rounded-lg overflow-x-auto">
            <code>{original}</code>
          </pre>
        </div>
        <div>
          <p className="text-xs text-green-600 font-medium mb-1">Fixed</p>
          <pre className="bg-green-950 text-green-200 text-xs p-3 rounded-lg overflow-x-auto">
            <code>{fixed}</code>
          </pre>
        </div>
      </div>

      <p className="text-sm text-gray-600">{explanation}</p>
    </div>
  );
}
