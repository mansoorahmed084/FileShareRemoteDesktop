import type { ConnectionStatus } from "../lib/types";

const STATUS_CONFIG: Record<ConnectionStatus, { color: string; label: string }> = {
  connected: { color: "bg-green-500", label: "Connected" },
  connecting: { color: "bg-yellow-500", label: "Connecting" },
  disconnected: { color: "bg-gray-400", label: "Offline" },
  error: { color: "bg-red-500", label: "Error" },
};

export function StatusBadge({ status }: { status: ConnectionStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <div className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${config.color} ${status === "connecting" ? "animate-pulse" : ""}`} />
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
        {config.label}
      </span>
    </div>
  );
}
