const dayInMs = 24 * 60 * 60 * 1000;

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
}

export function formatRelativeDate(value: string, now = Date.now()) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";

  const daysAgo = Math.floor((startOfDay(new Date(now)) - startOfDay(date)) / dayInMs);
  if (daysAgo === 0) return "Today";
  if (daysAgo === 1) return "Yesterday";
  if (daysAgo > 1 && daysAgo < 7) return date.toLocaleDateString(undefined, { weekday: "long" });
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: date.getFullYear() === new Date(now).getFullYear() ? undefined : "numeric" });
}

