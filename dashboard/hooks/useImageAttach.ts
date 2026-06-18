'use client';
import { useState, useCallback, useEffect } from 'react';

export interface AttachedImage {
  id: string;
  file: File;
  url: string;
}

export function useImageAttach() {
  const [images, setImages] = useState<AttachedImage[]>([]);

  // Revoke all object URLs on unmount
  useEffect(() => {
    return () => {
      images.forEach(img => URL.revokeObjectURL(img.url));
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const addImages = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files);
    setImages(prev => {
      const newItems: AttachedImage[] = arr.map(file => ({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        file,
        url: URL.createObjectURL(file),
      }));
      return [...prev, ...newItems];
    });
  }, []);

  const removeImage = useCallback((id: string) => {
    setImages(prev => {
      const item = prev.find(i => i.id === id);
      if (item) URL.revokeObjectURL(item.url);
      return prev.filter(i => i.id !== id);
    });
  }, []);

  const clearAll = useCallback(() => {
    setImages(prev => {
      prev.forEach(img => URL.revokeObjectURL(img.url));
      return [];
    });
  }, []);

  return { images, addImages, removeImage, clearAll };
}
