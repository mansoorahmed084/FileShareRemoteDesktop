import { useState } from "react";

interface PairingDialogProps {
  onCreateCode: () => void;
  onJoinCode: (code: string) => void;
  pairingCode: string | null;
  verificationEmojis: string | null;
  error: string | null;
  onConfirmVerification: () => void;
  onCancelVerification: () => void;
}

export function PairingDialog({
  onCreateCode,
  onJoinCode,
  pairingCode,
  verificationEmojis,
  error,
  onConfirmVerification,
  onCancelVerification,
}: PairingDialogProps) {
  const [joinCode, setJoinCode] = useState("");
  const [mode, setMode] = useState<"choose" | "create" | "join">("choose");

  if (verificationEmojis) {
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-semibold">Verify Pairing</h3>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Confirm these emojis match on both devices:
        </p>
        <div className="text-4xl text-center py-4 bg-gray-50 dark:bg-gray-800 rounded-lg tracking-widest">
          {verificationEmojis}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onConfirmVerification}
            className="flex-1 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg"
          >
            They Match
          </button>
          <button
            onClick={onCancelVerification}
            className="flex-1 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-lg"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (mode === "create") {
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-semibold">Pair New Device</h3>
        {pairingCode ? (
          <>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Enter this code on the other device:
            </p>
            <div className="text-3xl font-mono text-center py-4 bg-gray-50 dark:bg-gray-800 rounded-lg tracking-[0.5em]">
              {pairingCode}
            </div>
            <p className="text-xs text-gray-400 text-center">Expires in 60 seconds</p>
          </>
        ) : (
          <button
            onClick={onCreateCode}
            className="w-full py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg"
          >
            Generate Code
          </button>
        )}
        <button
          onClick={() => { setMode("choose"); }}
          className="w-full py-1.5 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          Back
        </button>
      </div>
    );
  }

  if (mode === "join") {
    return (
      <div className="space-y-4">
        <h3 className="text-sm font-semibold">Join a Device</h3>
        <input
          type="text"
          maxLength={6}
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value.replace(/\D/g, ""))}
          placeholder="Enter 6-digit code"
          className="w-full px-3 py-3 text-2xl text-center font-mono border rounded-lg bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none tracking-[0.5em]"
        />
        {error && (
          <p className="text-xs text-red-500 text-center">{error}</p>
        )}
        <button
          onClick={() => { if (joinCode.length === 6) onJoinCode(joinCode); }}
          disabled={joinCode.length !== 6}
          className="w-full py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50"
        >
          Connect
        </button>
        <button
          onClick={() => { setMode("choose"); setJoinCode(""); }}
          className="w-full py-1.5 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        >
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Pair Devices</h3>
      <button
        onClick={() => { setMode("create"); onCreateCode(); }}
        className="w-full py-3 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg"
      >
        Show Pairing Code
      </button>
      <button
        onClick={() => setMode("join")}
        className="w-full py-3 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg"
      >
        Enter a Code
      </button>
    </div>
  );
}
