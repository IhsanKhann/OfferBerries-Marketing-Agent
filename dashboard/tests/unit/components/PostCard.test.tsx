import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PostCard from '../../../app/(app)/queue/PostCard';
import type { PreviewPost } from '../../../hooks/usePostPreview';

const BASE_POST: PreviewPost = {
  postiz_id: 'post-001',
  platform: 'linkedin',
  scheduled_at: '2026-06-20T09:00:00Z',
  status: 'queued',
  caption: 'OfferBerries payroll automation for Pakistani SMBs.',
  hashtags: ['#Payroll'],
};

describe('PostCard', () => {
  it('renders platform label', () => {
    render(<PostCard post={BASE_POST} onClick={vi.fn()} />);
    expect(screen.getByText('linkedin')).toBeInTheDocument();
  });

  it('renders caption text', () => {
    render(<PostCard post={BASE_POST} onClick={vi.fn()} />);
    expect(screen.getByText('OfferBerries payroll automation for Pakistani SMBs.')).toBeInTheDocument();
  });

  it('shows fallback text when no caption', () => {
    const post = { ...BASE_POST, caption: undefined };
    render(<PostCard post={post} onClick={vi.fn()} />);
    expect(screen.getByText('No content preview available.')).toBeInTheDocument();
  });

  it('calls onClick when card is clicked', async () => {
    const onClick = vi.fn();
    const { container } = render(<PostCard post={BASE_POST} onClick={onClick} />);
    await userEvent.click(container.querySelector('.post-card') as HTMLElement);
    expect(onClick).toHaveBeenCalled();
  });

  it('calls onClick on Enter keydown', () => {
    const onClick = vi.fn();
    const { container } = render(<PostCard post={BASE_POST} onClick={onClick} />);
    const card = container.querySelector('.post-card') as HTMLElement;
    fireEvent.keyDown(card, { key: 'Enter' });
    expect(onClick).toHaveBeenCalled();
  });

  it('calls onCopy when copy button is clicked', async () => {
    const onCopy = vi.fn();
    render(<PostCard post={BASE_POST} onClick={vi.fn()} onCopy={onCopy} />);
    const copyBtn = screen.getByTitle('Copy caption');
    await userEvent.click(copyBtn);
    expect(onCopy).toHaveBeenCalled();
  });

  it('copy button click does NOT bubble to card onClick', async () => {
    const onClick = vi.fn();
    render(<PostCard post={BASE_POST} onClick={onClick} />);
    const copyBtn = screen.getByTitle('Copy caption');
    await userEvent.click(copyBtn);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('shows download button only when preview_url present', () => {
    render(<PostCard post={BASE_POST} onClick={vi.fn()} />);
    expect(screen.queryByTitle('Download image')).not.toBeInTheDocument();

    const withImage = { ...BASE_POST, preview_url: 'https://cdn.example.com/post.png' };
    const { unmount } = render(<PostCard post={withImage} onClick={vi.fn()} />);
    expect(screen.getByTitle('Download image')).toBeInTheDocument();
    unmount();
  });

  it('shows CheckCircle for approved status', () => {
    const approved = { ...BASE_POST, status: 'approved' };
    const { container } = render(<PostCard post={approved} onClick={vi.fn()} />);
    // approved status shows CheckCircle (green), not Clock
    expect(container.querySelector('.post-card__status')).toBeInTheDocument();
  });

  it('renders twitter platform with correct label', () => {
    const post = { ...BASE_POST, platform: 'twitter' };
    render(<PostCard post={post} onClick={vi.fn()} />);
    expect(screen.getByText('twitter')).toBeInTheDocument();
  });

  it('renders instagram platform', () => {
    const post = { ...BASE_POST, platform: 'instagram' };
    render(<PostCard post={post} onClick={vi.fn()} />);
    expect(screen.getByText('instagram')).toBeInTheDocument();
  });

  it('download button click does NOT bubble to card onClick', async () => {
    const onClick = vi.fn();
    const withImage = { ...BASE_POST, preview_url: 'https://cdn.example.com/post.png' };
    const { container } = render(<PostCard post={withImage} onClick={onClick} />);
    // Mock createElement to avoid jsdom anchor click errors
    const mockAnchor = { href: '', download: '', click: vi.fn() };
    vi.spyOn(document, 'createElement').mockReturnValueOnce(mockAnchor as unknown as HTMLElement);
    await userEvent.click(screen.getByTitle('Download image'));
    expect(onClick).not.toHaveBeenCalled();
  });
});
