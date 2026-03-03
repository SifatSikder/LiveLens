/**
 * FindingsSidebar — live findings list with severity colour badges.
 * Props:
 *   findings (array) — from useInspection hook
 */

const SEV_LABEL = { 1: 'Low', 2: 'Med', 3: 'Mod', 4: 'High', 5: 'Crit' };

export default function FindingsSidebar({ findings = [] }) {
  if (findings.length === 0) {
    return (
      <p className="text-gray-600 text-xs text-center mt-4">
        No findings logged yet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {findings.map((f, i) => {
        const sev = f.severity ?? 1;
        return (
          <div
            key={f.id ?? i}
            className={`p-2.5 rounded-lg border text-xs severity-${sev}`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-semibold truncate max-w-[60%]">
                {f.finding_type || f.type || 'Finding'}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold border severity-${sev}`}
              >
                {SEV_LABEL[sev] ?? `Sev ${sev}`}
              </span>
            </div>
            <p className="opacity-90 leading-snug line-clamp-2">{f.description}</p>
            {f.location_note && (
              <p className="opacity-60 mt-1 truncate">📍 {f.location_note}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

