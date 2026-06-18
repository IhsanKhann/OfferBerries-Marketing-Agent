'use client';
import { useRef } from 'react';
import Link from 'next/link';
import { X, ExternalLink } from 'lucide-react';
import { StepStatus, STEPS } from '../../../hooks/useAgentRun';
import { useImageAttach } from '../../../hooks/useImageAttach';

interface Props {
  open: boolean;
  onClose: () => void;
  stepStatuses: StepStatus[];
  runId: string | null;
}

export default function AgentPipelinePanel({ open, onClose, stepStatuses, runId }: Props) {
  const { images: refImages, addImages: addRefImages, removeImage: removeRefImage } = useImageAttach();
  const dropRef = useRef<HTMLDivElement>(null);
  const refInputRef = useRef<HTMLInputElement>(null);

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    dropRef.current?.classList.add('drag-over');
  }
  function handleDragLeave() {
    dropRef.current?.classList.remove('drag-over');
  }
  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    dropRef.current?.classList.remove('drag-over');
    if (e.dataTransfer.files.length) addRefImages(e.dataTransfer.files);
  }

  return (
    <>
      {open && <div className="pipeline-backdrop" onClick={onClose} />}
      <div className={`pipeline-panel${open ? ' open' : ''}`}>
        <div className="pipeline-panel__header">
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>Agent Pipeline</div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {runId && (
              <Link
                href={`/runs/${runId}`}
                className="btn btn-secondary btn-sm"
                style={{ gap: 4, fontSize: 11 }}
                title="View full run detail"
              >
                <ExternalLink size={11} /> View Run
              </Link>
            )}
            <button type="button" className="input-icon-btn" onClick={onClose} title="Close pipeline">
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="pipeline-panel__body">
          {/* Stepper */}
          <div>
            <div className="stepper">
              {STEPS.map((step, i) => {
                const status = stepStatuses[i] ?? 'pending';
                return (
                  <div key={i} className="step-item">
                    <div className={`step-dot ${status}`}>
                      {status === 'done'
                        ? '✓'
                        : status === 'running'
                        ? <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5 }} />
                        : status === 'failed'
                        ? '✗'
                        : i + 1}
                    </div>
                    <div className="step-content">
                      <div className="step-title">{step.label}</div>
                      <div className="step-meta">{step.meta}</div>
                    </div>
                  </div>
                );
              })}
            </div>

            {runId && (
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)' }}>
                <Link
                  href="/runs"
                  style={{ fontSize: 12, color: 'var(--text-muted)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4 }}
                >
                  <ExternalLink size={11} /> All runs
                </Link>
              </div>
            )}
          </div>

          {/* Visual References */}
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>Visual References</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
              Upload inspiration images for the agent
            </div>

            <input
              ref={refInputRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: 'none' }}
              onChange={e => e.target.files && addRefImages(e.target.files)}
            />

            <div
              ref={dropRef}
              className="drop-zone"
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => refInputRef.current?.click()}
            >
              Drop images here
              <br />
              <span style={{ fontSize: 11, color: 'var(--text-placeholder)' }}>PNG, JPG up to 20 files</span>
            </div>

            {refImages.length > 0 && (
              <div className="drop-zone-grid">
                {refImages.map(img => (
                  <div key={img.id} className="drop-zone-thumb">
                    <img src={img.url} alt={img.file.name} />
                    <button
                      type="button"
                      className="drop-zone-remove"
                      onClick={() => removeRefImage(img.id)}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
