import type { TransferProgress as TransferProgressType } from "../lib/file-transfer";
import { formatFileSize, formatSpeed } from "../lib/file-transfer";

interface TransferProgressProps {
  transfers: TransferProgressType[];
  onCancel: (transferId: string) => void;
  onDownload: (transferId: string) => void;
}

const FILE_ICONS: Record<string, string> = {
  image: "🖼️",
  video: "🎬",
  audio: "🎵",
  text: "📄",
  application: "📦",
};

function getFileIcon(fileName: string): string {
  const ext = fileName.split(".").pop()?.toLowerCase() || "";
  if (["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(ext)) return FILE_ICONS.image;
  if (["mp4", "webm", "mov", "avi"].includes(ext)) return FILE_ICONS.video;
  if (["mp3", "wav", "ogg", "flac"].includes(ext)) return FILE_ICONS.audio;
  if (["env", "txt", "md", "json", "yml", "yaml", "toml", "ini", "cfg"].includes(ext)) return FILE_ICONS.text;
  return FILE_ICONS.application;
}

export function TransferProgressList({
  transfers,
  onCancel,
  onDownload,
}: TransferProgressProps) {
  if (transfers.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        Transfers
      </h3>
      {transfers.map((t) => {
        const percent = t.totalChunks > 0
          ? Math.round((t.completedChunks / t.totalChunks) * 100)
          : 0;
        const elapsed = (Date.now() - t.startTime) / 1000;
        const bytesTransferred = (t.completedChunks / t.totalChunks) * t.fileSize;
        const speed = elapsed > 0 ? bytesTransferred / elapsed : 0;

        return (
          <div
            key={t.transferId}
            className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 space-y-2"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-base">{getFileIcon(t.fileName)}</span>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">{t.fileName}</div>
                  <div className="text-xs text-gray-400">
                    {formatFileSize(t.fileSize)}
                    {t.status === "active" && speed > 0 && ` · ${formatSpeed(speed)}`}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                {t.status === "active" && (
                  <button
                    onClick={() => onCancel(t.transferId)}
                    className="text-xs text-gray-400 hover:text-red-500 p-1"
                    title="Cancel"
                  >
                    ✕
                  </button>
                )}
                {t.status === "complete" && t.direction === "receive" && (
                  <button
                    onClick={() => onDownload(t.transferId)}
                    className="text-xs text-primary-600 hover:text-primary-700 font-medium p-1"
                  >
                    Save
                  </button>
                )}
                {t.status === "complete" && (
                  <span className="text-green-500 text-sm">✓</span>
                )}
                {t.status === "failed" && (
                  <span className="text-red-500 text-xs" title={t.error}>✗</span>
                )}
              </div>
            </div>

            {(t.status === "active" || t.status === "pending") && (
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
                <div
                  className="bg-primary-600 h-1.5 rounded-full transition-all duration-300"
                  style={{ width: `${percent}%` }}
                />
              </div>
            )}

            {t.status === "active" && (
              <div className="text-[10px] text-gray-400 text-right">
                {percent}% · {t.completedChunks}/{t.totalChunks} chunks
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
