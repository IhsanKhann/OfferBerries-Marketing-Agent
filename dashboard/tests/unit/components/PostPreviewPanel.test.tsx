import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PostPreviewPanel from '../../../app/(app)/queue/PostPreviewPanel';
import type { PreviewPost } from '../../../hooks/usePostPreview';

const MOCK_POST: PreviewPost = {
  postiz_id: 'post-001',
  platform: 'linkedin',
  scheduled_at: '2026-06-20T09:00:00Z',
  status: 'queued',
  copy: 'OfferBerries automates payroll for Pakistani SMBs. EOBI compliance handled.',
  hashtags: ['#Payroll', '#EOBI', '#PakistanHR'],
  caption: 'OfferBerries automates payroll.',
};

describe('PostPreviewPanel', () => {
  it('renders nothing visible when closed', () => {
    const { container } = render(
      <PostPreviewPanel post={null} isOpen={false} onClose={vi.fn()} />
    );
    expect(container.querySelector('.post-preview-panel')).not.toHaveClass('open');
  });

  it('adds "open" class when isOpen=true', () => {
    const { container } = render(
      <PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />
    );
    expect(container.querySelector('.post-preview-panel')).toHaveClass('open');
  });

  it('renders hashtags as individual pill badges from post.hashtags array', () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('#Payroll')).toBeInTheDocument();
    expect(screen.getByText('#EOBI')).toBeInTheDocument();
    expect(screen.getByText('#PakistanHR')).toBeInTheDocument();
  });

  it('shows each hashtag as a badge (not parsed from caption text)', () => {
    // The hashtags come from post.hashtags array — they are pills, not regex-extracted
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    const badges = document.querySelectorAll('.preview-hashtag-badge');
    expect(badges).toHaveLength(3);
  });

  it('shows "No hashtags" when hashtags array is empty', () => {
    const postNoHashtags = { ...MOCK_POST, hashtags: [] };
    render(<PostPreviewPanel post={postNoHashtags} isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('No hashtags')).toBeInTheDocument();
  });

  it('shows "No hashtags" when hashtags field is undefined', () => {
    const postNoHashtags = { ...MOCK_POST, hashtags: undefined };
    render(<PostPreviewPanel post={postNoHashtags} isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('No hashtags')).toBeInTheDocument();
  });

  it('calls onClose when X button is clicked', async () => {
    const onClose = vi.fn();
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={onClose} />);
    await userEvent.click(screen.getByTitle('Close (Escape)'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows platform name in header', () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    expect(screen.getByText('linkedin')).toBeInTheDocument();
  });

  it('renders copy text in caption textarea', () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    const textarea = screen.getByRole('textbox') as HTMLTextAreaElement;
    expect(textarea.value).toContain('OfferBerries automates payroll');
  });

  it('shows Approve button when onApprove provided and status is not approved', () => {
    render(
      <PostPreviewPanel
        post={MOCK_POST}
        isOpen={true}
        onClose={vi.fn()}
        onApprove={vi.fn().mockResolvedValue(undefined)}
      />
    );
    expect(screen.getByText('Approve & Schedule')).toBeInTheDocument();
  });

  it('does NOT show Approve button when post.status is "approved"', () => {
    const approved = { ...MOCK_POST, status: 'approved' };
    render(
      <PostPreviewPanel
        post={approved}
        isOpen={true}
        onClose={vi.fn()}
        onApprove={vi.fn().mockResolvedValue(undefined)}
      />
    );
    expect(screen.queryByText('Approve & Schedule')).not.toBeInTheDocument();
  });

  it('shows Reject button when onReject is provided', () => {
    render(
      <PostPreviewPanel
        post={MOCK_POST}
        isOpen={true}
        onClose={vi.fn()}
        onReject={vi.fn().mockResolvedValue(undefined)}
      />
    );
    expect(screen.getByText('Reject')).toBeInTheDocument();
  });

  it('in edit mode, hashtag remove buttons appear on each pill', async () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit'));
    const removeBtns = document.querySelectorAll('.preview-hashtag-remove');
    expect(removeBtns).toHaveLength(3);
  });

  it('removes hashtag pill when remove button is clicked in edit mode', async () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit'));
    const removeBtn = document.querySelector('.preview-hashtag-remove') as HTMLElement;
    await userEvent.click(removeBtn);
    const badges = document.querySelectorAll('.preview-hashtag-badge');
    expect(badges).toHaveLength(2);
  });

  it('adds new hashtag in edit mode via Add button', async () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit'));
    const input = screen.getByPlaceholderText('Add hashtag…');
    await userEvent.type(input, 'SMBs');
    await userEvent.click(screen.getByText('Add'));
    expect(screen.getByText('#SMBs')).toBeInTheDocument();
  });

  it('auto-prepends # when adding hashtag without it', async () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit'));
    const input = screen.getByPlaceholderText('Add hashtag…');
    await userEvent.type(input, 'JazzCash');
    await userEvent.click(screen.getByText('Add'));
    expect(screen.getByText('#JazzCash')).toBeInTheDocument();
  });

  it('adds hashtag via Enter key in edit mode', async () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText('Edit'));
    const input = screen.getByPlaceholderText('Add hashtag…');
    await userEvent.type(input, 'TestTag{Enter}');
    expect(screen.getByText('#TestTag')).toBeInTheDocument();
  });

  it('calls onApprove with postiz_id and then closes', async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <PostPreviewPanel
        post={MOCK_POST}
        isOpen={true}
        onClose={onClose}
        onApprove={onApprove}
      />
    );
    await userEvent.click(screen.getByText('Approve & Schedule'));
    expect(onApprove).toHaveBeenCalledWith('post-001');
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onReject with postiz_id and then closes', async () => {
    const onReject = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(
      <PostPreviewPanel
        post={MOCK_POST}
        isOpen={true}
        onClose={onClose}
        onReject={onReject}
      />
    );
    await userEvent.click(screen.getByText('Reject'));
    expect(onReject).toHaveBeenCalledWith('post-001');
    expect(onClose).toHaveBeenCalled();
  });

  it('shows image preview when post.preview_url is set', () => {
    const withImage = { ...MOCK_POST, preview_url: 'https://cdn.example.com/post.png' };
    render(<PostPreviewPanel post={withImage} isOpen={true} onClose={vi.fn()} />);
    const img = document.querySelector('.preview-visual img') as HTMLImageElement;
    expect(img).toBeInTheDocument();
    expect(img.src).toContain('cdn.example.com');
  });

  it('calls clipboard.writeText when Copy button is clicked', async () => {
    render(<PostPreviewPanel post={MOCK_POST} isOpen={true} onClose={vi.fn()} />);
    await userEvent.click(screen.getByText('Copy'));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('OfferBerries')
    );
  });
});
