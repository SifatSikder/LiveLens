import { Camera } from 'lucide-react';

/**
 * CameraStream — renders the live video element with status overlay.
 * Props:
 *   videoRef   (React ref) — forwarded to the <video> element
 *   inspecting (bool)      — whether an inspection session is active
 */
export default function CameraStream({ videoRef, inspecting }) {
  return (
    <div className="relative w-full h-full bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {/* Live video feed */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-cover ${inspecting ? '' : 'hidden'}`}
      />

      {/* Inactive placeholder */}
      {!inspecting && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <Camera className="w-16 h-16 text-gray-700 mx-auto mb-4" />
            <p className="text-gray-500 text-sm">Camera inactive</p>
            <p className="text-gray-600 text-xs mt-1">
              Start inspection to activate camera + mic
            </p>
          </div>
        </div>
      )}

      {/* INSPECTING badge */}
      {inspecting && (
        <div className="absolute top-3 left-3 flex items-center gap-2 bg-red-600/80 backdrop-blur px-3 py-1.5 rounded-full">
          <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
          <span className="text-white text-xs font-medium tracking-wide">INSPECTING</span>
        </div>
      )}
    </div>
  );
}

