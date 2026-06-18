'use client';
import type { PreviewPost } from '../../../hooks/usePostPreview';

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];
const DAY_HEADERS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface Props {
  posts: PreviewPost[];
  year: number;
  month: number; // 1-based
  onPostClick: (post: PreviewPost) => void;
}

export default function ContentCalendar({ posts, year, month, onPostClick }: Props) {
  // Build a map of day → posts
  const postsByDay = new Map<number, PreviewPost[]>();
  for (const post of posts) {
    const d = new Date(post.scheduled_at);
    if (d.getUTCFullYear() === year && d.getUTCMonth() + 1 === month) {
      const day = d.getUTCDate();
      const arr = postsByDay.get(day) ?? [];
      arr.push(post);
      postsByDay.set(day, arr);
    }
  }

  const daysInMonth = new Date(year, month, 0).getDate();
  // getDay() returns 0=Sunday; offset to Mon=0 ... Sun=6
  const firstDow = new Date(year, month - 1, 1).getDay(); // 0=Sun
  const offset = (firstDow + 6) % 7; // Mon-based offset

  const cells: Array<{ day: number | null }> = [
    ...Array(offset).fill({ day: null }),
    ...Array.from({ length: daysInMonth }, (_, i) => ({ day: i + 1 })),
  ];

  const coveredDays = postsByDay.size;
  const weekdays = Array.from({ length: daysInMonth }, (_, i) => {
    const dow = new Date(year, month - 1, i + 1).getDay();
    return dow !== 0 && dow !== 6;
  }).filter(Boolean).length;
  const hasGaps = coveredDays < weekdays;

  return (
    <div className="content-calendar">
      {/* Header */}
      <div className="calendar-header">
        <span className="calendar-month-title">{MONTH_NAMES[month - 1]} {year}</span>
        {hasGaps && (
          <span className="calendar-gap-warning">
            ⚠️ {weekdays - coveredDays} gap day{weekdays - coveredDays !== 1 ? 's' : ''} with no content scheduled
          </span>
        )}
      </div>

      {/* Day-of-week row */}
      <div className="calendar-dow-row">
        {DAY_HEADERS.map(d => (
          <div key={d} className="calendar-dow">{d}</div>
        ))}
      </div>

      {/* Day grid */}
      <div className="calendar-grid">
        {cells.map((cell, idx) => {
          if (!cell.day) {
            return <div key={`empty-${idx}`} className="calendar-day calendar-day--empty" />;
          }
          const dayPosts = postsByDay.get(cell.day) ?? [];
          const isWeekday = [1, 2, 3, 4, 5].includes(new Date(year, month - 1, cell.day).getDay());
          const isGap = isWeekday && dayPosts.length === 0;
          return (
            <div
              key={cell.day}
              className={`calendar-day${isGap ? ' gap-day' : ''}`}
              data-day={cell.day}
            >
              <span className="calendar-day-number">{cell.day}</span>
              {dayPosts.map(post => (
                <button
                  key={post.postiz_id}
                  type="button"
                  className={`calendar-post-pill ${post.platform}`}
                  onClick={() => onPostClick(post)}
                  title={post.copy ?? post.caption}
                >
                  {post.platform.slice(0, 2).toUpperCase()}
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
