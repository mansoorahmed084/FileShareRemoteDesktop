import { useState, useEffect, useCallback } from "react";
import type { TransferProgress } from "../lib/file-transfer";
import { chunkFile, createFileMetadata, hashFile } from "../lib/file-transfer";

export function useFileTransfer() {
  const [transfers, setTransfers] = useState<TransferProgress[]>([]);

  useEffect(() => {
    chrome.runtime.sendMessage({ type: "get_transfers" }, (res) => {
      if (res?.transfers) setTransfers(res.transfers);
    });

    const listener = (message: Record<string, unknown>) => {
      if (message.type === "transfer_update") {
        const t = message.transfer as TransferProgress;
        setTransfers((prev) => {
          const idx = prev.findIndex((x) => x.transferId === t.transferId);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = t;
            return next;
          }
          return [...prev, t];
        });
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const sendFiles = useCallback(
    async (files: File[], targetDeviceId: string) => {
      for (const file of files) {
        const meta = createFileMetadata(file);
        const arrayBuffer = await file.arrayBuffer();
        const sha256 = await hashFile(arrayBuffer);
        const fullMeta = { ...meta, sha256 };

        const transfer: TransferProgress = {
          transferId: meta.transferId,
          fileName: file.name,
          fileSize: file.size,
          totalChunks: meta.totalChunks,
          completedChunks: 0,
          direction: "send",
          status: "active",
          startTime: Date.now(),
        };
        setTransfers((prev) => [...prev, transfer]);

        const allChunks: {
          index: number;
          total: number;
          data: string;
          nonce: string;
        }[] = [];
        for await (const chunk of chunkFile(file, null)) {
          allChunks.push(chunk);
          setTransfers((prev) =>
            prev.map((t) =>
              t.transferId === meta.transferId
                ? { ...t, completedChunks: chunk.index + 1 }
                : t
            )
          );
        }

        chrome.runtime.sendMessage({
          type: "send_file",
          to_device: targetDeviceId,
          meta: fullMeta,
          chunks: allChunks,
        });

        setTransfers((prev) =>
          prev.map((t) =>
            t.transferId === meta.transferId
              ? { ...t, status: "complete" }
              : t
          )
        );
      }
    },
    []
  );

  const cancelTransfer = useCallback(
    (transferId: string, targetDeviceId: string) => {
      chrome.runtime.sendMessage({
        type: "cancel_transfer",
        transferId,
        to_device: targetDeviceId,
      });
      setTransfers((prev) =>
        prev.map((t) =>
          t.transferId === transferId
            ? { ...t, status: "cancelled" as const }
            : t
        )
      );
    },
    []
  );

  const downloadFile = useCallback((transferId: string, fileName: string) => {
    chrome.runtime.sendMessage({
      type: "download_received",
      transferId,
      fileName,
    });
  }, []);

  return { transfers, sendFiles, cancelTransfer, downloadFile };
}
