import { useState, useCallback, useRef } from "react";
import { formatFileSize } from "../lib/file-transfer";

interface FileDropZoneProps {
  onFilesSelected: (files: File[]) => void;
  disabled: boolean;
  maxFileSize: number;
}

export function FileDropZone({
  onFilesSelected,
  disabled,
  maxFileSize,
}: FileDropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateAndSubmit = useCallback(
    (files: FileList | File[]) => {
      setError(null);
      const valid: File[] = [];
      for (const file of Array.from(files)) {
        if (file.size > maxFileSize) {
          setError(`${file.name} exceeds ${formatFileSize(maxFileSize)} limit`);
          return;
        }
        valid.push(file);
      }
      if (valid.length > 0) onFilesSelected(valid);
    },
    [maxFileSize, onFilesSelected]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    if (e.dataTransfer.files.length > 0) {
      validateAndSubmit(e.dataTransfer.files);
    }
  };

  return (
    <div className="space-y-2">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          disabled
            ? "border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 cursor-not-allowed opacity-50"
            : isDragging
              ? "border-primary-500 bg-primary-50 dark:bg-primary-900/20"
              : "border-gray-300 dark:border-gray-600 hover:border-primary-400 hover:bg-gray-50 dark:hover:bg-gray-800"
        }`}
      >
        <div className="text-2xl mb-2">
          {isDragging ? "📥" : "📁"}
        </div>
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {isDragging
            ? "Drop files here"
            : "Drag & drop files or click to browse"}
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Max {formatFileSize(maxFileSize)} per file
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) validateAndSubmit(e.target.files);
            e.target.value = "";
          }}
          disabled={disabled}
        />
      </div>
      {error && (
        <p className="text-xs text-red-500 text-center">{error}</p>
      )}
    </div>
  );
}
