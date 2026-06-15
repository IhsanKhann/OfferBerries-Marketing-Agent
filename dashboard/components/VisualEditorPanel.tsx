'use client';
import { useState } from 'react';
import { RefreshCw, CheckCircle, ChevronDown, ChevronUp, ImageIcon } from 'lucide-react';
import { notify } from '../lib/toast';

interface HistoryEntry {
  timestamp: string;
  platform: string;
  instructions: string;
  visual_url: string;
  source: string;
}

interface VisualEditorPanelProps {
  runId: string;
  platform: string;
  initialVisualUrl?: string;
  onApprove: (platform: string, visualUrl: string) => void;
}

const SOURCE_OPTIONS = [
  { value: 'fal', label: 'Flux (fal.ai)' },
  { value: 'open_design', label: 'OpenDesign' },
  { value: 'template', label: 'Template renderer' },
];

export default function VisualEditorPanel({
  runId,
  platform,
  initialVisualUrl,
  onApprove,
}: VisualEditorPanelProps) {
  const [visualUrl, setVisualUrl] = useState<string>(initialVisualUrl ?? '');
  const [instructions, setInstructions] = useState('');
  const [source, setSource] = useState('fal');
  const [regenerating, setRegenerating] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      const resp = await fetch(`/api/proxy/runs/${runId}/visual/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          platform,
          additional_instructions: instructions,
          source,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setVisualUrl(data.visual_url ?? '');
      setHistory(prev => [data.history_entry, ...prev]);
      setInstructions('');
      notify.success('Visual regenerated');
    } catch (err) {
      notify.error(err instanceof Error ? err.message : 'Regeneration failed');
    } finally {
      setRegenerating(false);
    }
  }

  function handleUseThis() {
    onApprove(platform, visualUrl);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Preview */}
      <div style={{
        width: '100%', aspectRatio: '1 / 1',
        background: 'var(--surface-raised)',
        borderRadius: 8,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        overflow: 'hidden',
        border: '1px solid var(--border-default)',
        maxHeight: 360,
      }}>
        {visualUrl ? (
          <img
            src={visualUrl}
            alt={`Visual for ${platform}`}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8, color: 'var(--text-muted)' }}>
            <ImageIcon size={32} />
            <span style={{ fontSize: 12 }}>No visual yet</span>
          </div>
        )}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <label style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-muted)' }}>
          Refinement instructions
        </label>
        <textarea
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          placeholder="e.g. make the background darker, increase contrast, use bolder headline…"
          rows={3}
          style={{
            width: '100%', padding: '8px 10px',
            background: 'var(--surface-raised)',
            border: '1px solid var(--border-default)',
            borderRadius: 6, fontSize: 13,
            color: 'var(--text-primary)',
            resize: 'vertical',
            fontFamily: 'inherit',
            boxSizing: 'border-box',
          }}
        />

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 11, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Model</label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              style={{
                width: '100%', padding: '6px 8px',
                background: 'var(--surface-raised)',
                border: '1px solid var(--border-default)',
                borderRadius: 6, fontSize: 12,
                color: 'var(--text-primary)',
              }}
            >
              {SOURCE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="btn btn-secondary btn-sm"
            style={{ gap: 6, flex: 1 }}
          >
            <RefreshCw size={13} style={{ animation: regenerating ? 'spin 1s linear infinite' : undefined }} />
            {regenerating ? 'Regenerating…' : '↻ Regenerate Visual'}
          </button>
          <button
            onClick={handleUseThis}
            disabled={!visualUrl || regenerating}
            className="btn btn-primary btn-sm"
            style={{ gap: 6, flex: 1 }}
          >
            <CheckCircle size={13} />
            ✓ Use This Visual
          </button>
        </div>
      </div>

      {/* Instruction history */}
      {history.length > 0 && (
        <div>
          <button
            onClick={() => setShowHistory(h => !h)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: 12, color: 'var(--text-muted)',
              background: 'none', border: 'none', cursor: 'pointer', padding: 0,
            }}
          >
            {showHistory ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            Instruction history ({history.length})
          </button>
          {showHistory && (
            <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
              {history.map((entry, i) => (
                <div key={i} style={{
                  padding: '8px 10px',
                  background: 'var(--surface-raised)',
                  borderRadius: 6,
                  fontSize: 12,
                  borderLeft: '3px solid var(--border-default)',
                }}>
                  <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>
                    {new Date(entry.timestamp).toLocaleTimeString()} · {entry.source}
                  </div>
                  {entry.instructions && (
                    <div style={{ color: 'var(--text-primary)' }}>
                      &ldquo;{entry.instructions}&rdquo;
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
