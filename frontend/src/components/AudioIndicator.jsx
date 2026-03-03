/**
 * AudioIndicator — animated 5-bar waveform.
 * Props:
 *   active   (bool) — mic is capturing (user speaking / listening)
 *   speaking (bool) — agent is playing audio back (agent speaking)
 */
export default function AudioIndicator({ active = false, speaking = false }) {
  const heights = [40, 70, 55, 85, 45]; // % base heights for variety

  const barColor = speaking
    ? 'bg-blue-400'
    : active
    ? 'bg-green-400'
    : 'bg-gray-600';

  return (
    <div className="flex items-center justify-center gap-1 h-8">
      {heights.map((h, i) => (
        <div
          key={i}
          className={`w-1 rounded-full transition-colors duration-200 ${barColor}`}
          style={{
            height: active || speaking ? `${h}%` : '15%',
            animation:
              speaking
                ? `pulse-bar 0.${5 + i}s ease-in-out infinite alternate`
                : active
                ? `pulse-bar 0.${8 + i}s ease-in-out infinite alternate`
                : 'none',
            animationDelay: `${i * 0.08}s`,
            transition: 'height 0.25s ease',
          }}
        />
      ))}
      <style>{`
        @keyframes pulse-bar {
          from { transform: scaleY(0.5); }
          to   { transform: scaleY(1.4); }
        }
      `}</style>
    </div>
  );
}

