import type { PairedDevice } from "../lib/types";

interface DeviceListProps {
  devices: PairedDevice[];
  selectedDeviceId: string | null;
  onSelect: (deviceId: string) => void;
  onRemove: (deviceId: string) => void;
}

export function DeviceList({
  devices,
  selectedDeviceId,
  onSelect,
  onRemove,
}: DeviceListProps) {
  if (devices.length === 0) {
    return (
      <div className="text-center py-4 text-sm text-gray-400 dark:text-gray-500">
        No paired devices
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        Paired Devices
      </h3>
      {devices.map((device) => (
        <div
          key={device.device_id}
          onClick={() => onSelect(device.device_id)}
          className={`flex items-center justify-between p-2.5 rounded-lg cursor-pointer transition-colors ${
            selectedDeviceId === device.device_id
              ? "bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800"
              : "bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-750 border border-transparent"
          }`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                device.is_online ? "bg-green-500" : "bg-gray-400"
              }`}
            />
            <div className="min-w-0">
              <div className="text-sm font-medium truncate">
                {device.device_name}
              </div>
              <div className="text-xs text-gray-400 font-mono truncate">
                {device.device_id.slice(0, 8)}...
              </div>
            </div>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onRemove(device.device_id);
            }}
            className="text-gray-400 hover:text-red-500 text-xs p-1"
            title="Remove device"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
