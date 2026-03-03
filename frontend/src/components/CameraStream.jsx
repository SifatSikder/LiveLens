import { Camera, ScanLine } from 'lucide-react';

/**
 * CameraStream — live video element with status overlay and onboarding card.
 * Props:
 *   videoRef   (React ref) — forwarded to the <video> element
 *   inspecting (bool)      — whether an inspection session is active
 *   connected  (bool)      — WebSocket connected (drives onboarding hint copy)
 */
export default function CameraStream({ videoRef, inspecting, connected = false }) {
  return (
    <div className="relative w-full h-full bg-gray-950 rounded-xl border border-gray-800 overflow-hidden">
      {/* Live video feed */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className={`w-full h-full object-cover transition-opacity duration-300 ${inspecting ? 'opacity-100' : 'opacity-0 absolute inset-0'}`}
      />

      {/* Onboarding / inactive placeholder */}
      {!inspecting && (
        <div className="absolute inset-0 flex items-center justify-center p-6 animate-fadeIn">
          <div className="text-center max-w-xs">
            <div className="w-20 h-20 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center mx-auto mb-5 transition-colors">
              <Camera className="w-10 h-10 text-blue-400" />
            </div>
            <h3 className="text-white font-semibold text-base mb-2">AI Infrastructure Inspector</h3>
            <p className="text-gray-400 text-sm leading-relaxed">
              Point your camera at any infrastructure — I'll help you inspect it in real time.
            </p>
            <p className="text-gray-600 text-xs mt-4">
              {connected
                ? 'Tap "Start Inspection" to activate camera + mic'
                : 'Connect first, then start an inspection'}
            </p>
          </div>
        </div>
      )}

      {/* INSPECTING live badge */}
      {inspecting && (
        <div className="absolute top-3 left-3 flex items-center gap-2 bg-red-600/80 backdrop-blur-sm px-3 py-1.5 rounded-full transition-opacity duration-200">
          <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
          <span className="text-white text-xs font-medium tracking-wide">LIVE</span>
        </div>
      )}

      {/* Scan line animation while inspecting */}
      {inspecting && (
        <div className="absolute bottom-3 right-3 flex items-center gap-1.5 text-green-400/70 text-[10px]">
          <ScanLine className="w-3.5 h-3.5 animate-pulse" />
          <span className="font-mono">Scanning…</span>
        </div>
      )}
    </div>
  );
}

