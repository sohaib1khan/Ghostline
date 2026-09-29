export default function StreakFlame({ days }) {
  if (!days) {
    return null;
  }
  return (
    <span className="streak-flame" aria-hidden="true">
      🔥
    </span>
  );
}
