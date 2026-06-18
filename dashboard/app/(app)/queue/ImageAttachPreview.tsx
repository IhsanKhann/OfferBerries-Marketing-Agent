'use client';
import { X } from 'lucide-react';
import { AttachedImage } from '../../../hooks/useImageAttach';

interface Props {
  images: AttachedImage[];
  onRemove: (id: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ImageAttachPreview({ images, onRemove }: Props) {
  if (images.length === 0) return null;

  return (
    <div className="image-attach-stack">
      {images.map(img => (
        <div key={img.id} className="image-attach-item">
          <img
            src={img.url}
            alt={img.file.name}
            className="image-attach-thumb"
          />
          <div className="image-attach-info">
            <div className="image-attach-name">{img.file.name}</div>
            <div className="image-attach-size">{formatBytes(img.file.size)}</div>
          </div>
          <button
            type="button"
            className="image-attach-remove"
            onClick={() => onRemove(img.id)}
            title="Remove"
          >
            <X size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}
