'use client';
import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { RESEARCH_MODELS, CONTENT_MODELS } from '@/hooks/useAgentRun';

const PLATFORMS = ['LinkedIn', 'Twitter', 'Instagram', 'YouTube', 'Email'];

interface Props {
  open: boolean;
  onClose: () => void;
  activePlatforms: string[];
  onTogglePlatform: (p: string) => void;
  researchModel: string;
  setResearchModel: (id: string) => void;
  contentModel: string;
  setContentModel: (id: string) => void;
}

export function OptionsModal({
  open, onClose,
  activePlatforms, onTogglePlatform,
  researchModel, setResearchModel,
  contentModel, setContentModel,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  useEffect(() => {
    function handler(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    if (open) document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="options-overlay">
      <div className="options-modal" ref={ref}>
        <div className="options-modal-hd">
          <span className="options-modal-title">Options</span>
          <button className="options-close-btn" onClick={onClose}><X size={16} /></button>
        </div>

        <div className="options-section">
          <div className="options-section-lbl">Publish to</div>
          <div className="options-platforms">
            {PLATFORMS.map(p => (
              <button
                key={p}
                onClick={() => onTogglePlatform(p)}
                className={`options-platform-btn${activePlatforms.includes(p) ? ' active' : ''}`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div className="options-section">
          <div className="options-section-lbl">
            Research model <span className="options-lbl-hint">(Perplexity)</span>
          </div>
          <div className="options-model-btns">
            {RESEARCH_MODELS.map(m => (
              <button
                key={m.id}
                onClick={() => setResearchModel(m.id)}
                className={`options-model-btn${researchModel === m.id ? ' active' : ''}`}
              >
                {m.label}
                <span className="options-model-badge">{m.badge}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="options-section">
          <div className="options-section-lbl">Content model</div>
          <div className="options-model-btns">
            {CONTENT_MODELS.map(m => (
              <button
                key={m.id}
                onClick={() => setContentModel(m.id)}
                className={`options-model-btn${contentModel === m.id ? ' active' : ''}`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
