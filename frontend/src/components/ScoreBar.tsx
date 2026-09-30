interface ScoreBarProps {
  label: string;
  value: number;
}

export function ScoreBar({ label, value }: ScoreBarProps) {
  const percentage = Math.round(Math.max(0, Math.min(1, value)) * 100);

  return (
    <div className="score-row">
      <div className="score-label">
        <span>{label}</span>
        <strong>{percentage}%</strong>
      </div>
      <div className="score-track" aria-label={`${label}: yüzde ${percentage}`}>
        <span style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}
