'use client';
import { useState, useCallback, useEffect } from 'react';

export interface PreviewPost {
  postiz_id: string;
  platform: string;
  scheduled_at: string;
  status: string;
  caption?: string;
  preview_url?: string;
  copy?: string;
  hashtags?: string[];
  cta?: string;
  hook?: string;
}

export function usePostPreview() {
  const [selectedPost, setSelectedPost] = useState<PreviewPost | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const openPost = useCallback((post: PreviewPost) => {
    setSelectedPost(post);
    setIsOpen(true);
  }, []);

  const closePost = useCallback(() => {
    setIsOpen(false);
    // Keep selectedPost for the slide-out animation, then clear it
    setTimeout(() => setSelectedPost(null), 160);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen) closePost();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [isOpen, closePost]);

  return { selectedPost, isOpen, openPost, closePost };
}
