import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePostPreview, PreviewPost } from '../../../hooks/usePostPreview';

const MOCK_POST: PreviewPost = {
  postiz_id: 'post-001',
  platform: 'linkedin',
  scheduled_at: '2026-06-20T09:00:00Z',
  status: 'queued',
  copy: 'OfferBerries automates payroll for Pakistani SMBs.',
  hashtags: ['#Payroll', '#EOBI', '#PakistanHR'],
  caption: 'OfferBerries automates payroll.',
};

describe('usePostPreview', () => {
  it('starts closed with no selected post', () => {
    const { result } = renderHook(() => usePostPreview());
    expect(result.current.isOpen).toBe(false);
    expect(result.current.selectedPost).toBeNull();
  });

  it('opens and sets post on openPost()', () => {
    const { result } = renderHook(() => usePostPreview());
    act(() => result.current.openPost(MOCK_POST));
    expect(result.current.isOpen).toBe(true);
    expect(result.current.selectedPost).toBe(MOCK_POST);
  });

  it('closes on closePost()', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => usePostPreview());
    act(() => result.current.openPost(MOCK_POST));
    act(() => result.current.closePost());
    expect(result.current.isOpen).toBe(false);
    // selectedPost stays during animation window
    expect(result.current.selectedPost).toBe(MOCK_POST);
    act(() => vi.advanceTimersByTime(200));
    expect(result.current.selectedPost).toBeNull();
    vi.useRealTimers();
  });

  it('closes on Escape keydown when open', () => {
    const { result } = renderHook(() => usePostPreview());
    act(() => result.current.openPost(MOCK_POST));
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    expect(result.current.isOpen).toBe(false);
  });

  it('does NOT close on Escape when already closed', () => {
    const { result } = renderHook(() => usePostPreview());
    act(() => {
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    });
    // No error, still closed
    expect(result.current.isOpen).toBe(false);
  });

  it('replaces selected post on second openPost()', () => {
    const { result } = renderHook(() => usePostPreview());
    const second: PreviewPost = { ...MOCK_POST, postiz_id: 'post-002', platform: 'twitter' };
    act(() => result.current.openPost(MOCK_POST));
    act(() => result.current.openPost(second));
    expect(result.current.selectedPost?.postiz_id).toBe('post-002');
    expect(result.current.selectedPost?.platform).toBe('twitter');
  });
});
