import { useState } from "react";

interface TextMessage {
  id: string;
  from: string;
  text: string;
  timestamp: number;
  direction: "sent" | "received";
}

interface TextShareProps {
  messages: TextMessage[];
  selectedDeviceId: string | null;
  selectedDeviceName: string | null;
  onSend: (text: string) => void;
  disabled: boolean;
}

export function TextShare({
  messages,
  selectedDeviceId,
  selectedDeviceName,
  onSend,
  disabled,
}: TextShareProps) {
  const [text, setText] = useState("");
  const [copied, setCopied] = useState<string | null>(null);

  const handleSend = () => {
    if (!text.trim()) return;
    onSend(text);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  const copyToClipboard = async (msg: TextMessage) => {
    await navigator.clipboard.writeText(msg.text);
    setCopied(msg.id);
    setTimeout(() => setCopied(null), 2000);
  };

  const isEnvContent = (s: string) =>
    s.split("\n").some((line) => /^[A-Z_][A-Z0-9_]*=/.test(line.trim()));

  if (!selectedDeviceId) {
    return (
      <div className="text-center py-8 text-sm text-gray-400 dark:text-gray-500">
        Select a device to start sharing
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        Sharing with <span className="font-medium text-gray-700 dark:text-gray-300">{selectedDeviceName}</span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-2 mb-3 min-h-[120px] max-h-[200px]">
        {messages.length === 0 && (
          <div className="text-center py-6 text-xs text-gray-400">
            No messages yet
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.direction === "sent" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm relative group ${
                msg.direction === "sent"
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100"
              }`}
            >
              <pre
                className={`whitespace-pre-wrap break-words font-sans text-sm ${
                  isEnvContent(msg.text) ? "font-mono text-xs" : ""
                }`}
              >
                {msg.text}
              </pre>
              <button
                onClick={() => copyToClipboard(msg)}
                className={`absolute top-1 right-1 opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded text-xs ${
                  msg.direction === "sent"
                    ? "text-primary-200 hover:text-white"
                    : "text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                }`}
                title="Copy"
              >
                {copied === msg.id ? "Copied!" : "Copy"}
              </button>
              <div
                className={`text-[10px] mt-1 ${
                  msg.direction === "sent" ? "text-primary-200" : "text-gray-400"
                }`}
              >
                {new Date(msg.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message or paste .env variables..."
          rows={3}
          className="w-full px-3 py-2 text-sm border rounded-lg bg-gray-50 dark:bg-gray-800 border-gray-300 dark:border-gray-600 focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none resize-none"
          disabled={disabled}
        />
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-400">Ctrl+Enter to send</span>
          <button
            onClick={handleSend}
            disabled={disabled || !text.trim()}
            className="px-4 py-1.5 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export type { TextMessage };
