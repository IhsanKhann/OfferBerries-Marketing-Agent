import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ContentCalendar from '../../../app/(app)/analytics/ContentCalendar';

const JUNE_POSTS = [
  {
    postiz_id: 'p1',
    platform: 'linkedin',
    scheduled_at: '2026-06-16T09:00:00Z',
    status: 'approved',
    copy: 'Post one',
    hashtags: [],
    caption: 'Post one',
  },
  {
    postiz_id: 'p2',
    platform: 'instagram',
    scheduled_at: '2026-06-16T12:00:00Z',
    status: 'queued',
    copy: 'Post two',
    hashtags: [],
    caption: 'Post two',
  },
  {
    postiz_id: 'p3',
    platform: 'twitter',
    scheduled_at: '2026-06-18T10:00:00Z',
    status: 'queued',
    copy: 'Post three',
    hashtags: [],
    caption: 'Post three',
  },
];

describe('ContentCalendar', () => {
  it('renders without crashing', () => {
    const { container } = render(
      <ContentCalendar posts={[]} year={2026} month={6} onPostClick={vi.fn()} />
    );
    expect(container.querySelector('.content-calendar')).toBeInTheDocument();
  });

  it('renders 7 day-of-week headers', () => {
    render(<ContentCalendar posts={[]} year={2026} month={6} onPostClick={vi.fn()} />);
    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Sun')).toBeInTheDocument();
  });

  it('renders the correct number of calendar day cells for June 2026', () => {
    const { container } = render(
      <ContentCalendar posts={[]} year={2026} month={6} onPostClick={vi.fn()} />
    );
    // June 2026 has 30 days
    const dayCells = container.querySelectorAll('.calendar-day');
    expect(dayCells.length).toBeGreaterThanOrEqual(30);
  });

  it('shows posts on the correct calendar date', () => {
    const { container } = render(
      <ContentCalendar posts={JUNE_POSTS} year={2026} month={6} onPostClick={vi.fn()} />
    );
    // Two posts on June 16
    const day16 = container.querySelector('[data-day="16"]');
    expect(day16).not.toBeNull();
    const pills = day16!.querySelectorAll('.calendar-post-pill');
    expect(pills.length).toBe(2);
  });

  it('renders each post with its platform as CSS class', () => {
    const { container } = render(
      <ContentCalendar posts={JUNE_POSTS} year={2026} month={6} onPostClick={vi.fn()} />
    );
    expect(container.querySelector('.calendar-post-pill.linkedin')).toBeInTheDocument();
    expect(container.querySelector('.calendar-post-pill.instagram')).toBeInTheDocument();
  });

  it('shows gap warning for days with no scheduled posts', () => {
    render(<ContentCalendar posts={JUNE_POSTS} year={2026} month={6} onPostClick={vi.fn()} />);
    // With only 2 days covered out of 30, there should be gap days
    expect(screen.getByText(/gap/i)).toBeInTheDocument();
  });

  it('highlights days with no content using gap-day class', () => {
    const { container } = render(
      <ContentCalendar posts={JUNE_POSTS} year={2026} month={6} onPostClick={vi.fn()} />
    );
    const gapDays = container.querySelectorAll('.calendar-day.gap-day');
    expect(gapDays.length).toBeGreaterThan(0);
  });

  it('shows month name in calendar header', () => {
    render(<ContentCalendar posts={[]} year={2026} month={6} onPostClick={vi.fn()} />);
    expect(screen.getByText(/June/i)).toBeInTheDocument();
  });

  it('shows year in calendar header', () => {
    render(<ContentCalendar posts={[]} year={2026} month={6} onPostClick={vi.fn()} />);
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it('calls onPostClick when a post pill is clicked', async () => {
    const { userEvent: ue } = await import('@testing-library/user-event');
    const onPostClick = vi.fn();
    const { container } = render(
      <ContentCalendar posts={JUNE_POSTS} year={2026} month={6} onPostClick={onPostClick} />
    );
    const pill = container.querySelector('.calendar-post-pill') as HTMLElement;
    pill.click();
    expect(onPostClick).toHaveBeenCalled();
  });
});
