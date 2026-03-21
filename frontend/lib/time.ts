export function formatRelativeTime(isoString: string, options?: { maxUnit?: "day" | "month" }): string {
  const date = new Date(isoString);
  const timestamp = date.getTime();
  if (Number.isNaN(timestamp)) {
    return "时间未知";
  }

  const diff = Math.max(0, Date.now() - timestamp);
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "刚刚";

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟前`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;

  const days = Math.floor(hours / 24);
  if (options?.maxUnit !== "month" || days < 30) {
    return `${days} 天前`;
  }

  const months = Math.floor(days / 30);
  return `${months} 个月前`;
}
