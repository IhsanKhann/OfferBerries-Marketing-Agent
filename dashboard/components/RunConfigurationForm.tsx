'use client';
import { useState } from 'react';
import { Play, Settings2, ChevronDown, ChevronUp, Info } from 'lucide-react';

export interface RunConfig {
  topic: string;
  platforms: string[];
  execution_mode: 'automated' | 'controlled';
  stages_enabled: {
    research: boolean;
    content_generation: boolean;
    visual_generation: boolean;
    scheduling: boolean;
  };
  provided_content?: string;
}

interface Props {
  onSubmit: (config: RunConfig) => void;
  loading?: boolean;
}

const PLATFORMS = [
  { id: 'linkedin', label: 'LinkedIn' },
  { id: 'instagram', label: 'Instagram' },
  { id: 'twitter', label: 'Twitter' },
  { id: 'youtube', label: 'YouTube' },
];

const STAGE_COSTS: Record<string, { label: string; cost: number; desc: string }> = {
  research:           { label: 'Research',          cost: 0.01, desc: 'Perplexity Sonar' },
  content_generation: { label: 'Content Generation', cost: 0.02, desc: 'Gemini 2.5 Flash' },
  visual_generation:  { label: 'Visual Generation',  cost: 0.05, desc: 'Playwright renderer' },
  scheduling:         { label: 'Scheduling',          cost: 0.00, desc: 'Postiz queue' },
};

export default function RunConfigurationForm({ onSubmit, loading }: Props) {
  const [topic, setTopic] = useState('');
  const [platforms, setPlatforms] = useState<string[]>(['linkedin', 'instagram']);
  const [executionMode, setExecutionMode] = useState<'automated' | 'controlled'>('controlled');
  const [stages, setStages] = useState({
    research: true,
    content_generation: true,
    visual_generation: true,
    scheduling: false,
  });
  const [providedContent, setProvidedContent] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const estimatedCost = Object.entries(stages)
    .filter(([, enabled]) => enabled)
    .reduce((sum, [key]) => sum + (STAGE_COSTS[key]?.cost ?? 0), 0)
    * platforms.length;

  function togglePlatform(id: string) {
    setPlatforms(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );
  }

  function toggleStage(key: keyof typeof stages) {
    setStages(prev => ({ ...prev, [key]: !prev[key] }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim() || platforms.length === 0) return;
    onSubmit({
      topic: topic.trim(),
      platforms,
      execution_mode: executionMode,
      stages_enabled: stages,
      provided_content: providedContent.trim() || undefined,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="run-config-form">
      {/* Topic */}
      <div className="form-group">
        <label className="form-label">Topic</label>
        <input
          type="text"
          className="input"
          placeholder="e.g. EOBI payroll compliance for Pakistani SMBs"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          required
        />
      </div>

      {/* Platforms */}
      <div className="form-group">
        <label className="form-label">Platforms</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {PLATFORMS.map(p => (
            <button
              key={p.id}
              type="button"
              onClick={() => togglePlatform(p.id)}
              className={`badge ${platforms.includes(p.id) ? 'badge-primary' : 'badge-muted'}`}
              style={{ cursor: 'pointer', padding: '6px 12px', fontSize: 13 }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Execution mode */}
      <div className="form-group">
        <label className="form-label">Execution Mode</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {(['automated', 'controlled'] as const).map(mode => (
            <button
              key={mode}
              type="button"
              onClick={() => setExecutionMode(mode)}
              className={executionMode === mode ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
              style={{ flex: 1, textTransform: 'capitalize' }}
            >
              {mode}
            </button>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
          {executionMode === 'controlled'
            ? 'Pipeline pauses after each stage for your review and approval.'
            : 'All stages run automatically without interruption.'}
        </p>
      </div>

      {/* Stage toggles + cost */}
      <div className="form-group">
        <label className="form-label">Stages</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {Object.entries(STAGE_COSTS).map(([key, meta]) => (
            <label
              key={key}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                borderRadius: 6,
                background: 'var(--surface-raised)',
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={stages[key as keyof typeof stages]}
                  onChange={() => toggleStage(key as keyof typeof stages)}
                  style={{ accentColor: 'var(--accent)' }}
                />
                <span style={{ fontWeight: 500 }}>{meta.label}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{meta.desc}</span>
              </span>
              <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                {meta.cost > 0 ? `~$${meta.cost.toFixed(2)}` : 'free'}
              </span>
            </label>
          ))}
        </div>
        <div style={{
          marginTop: 8,
          padding: '6px 12px',
          borderRadius: 6,
          background: 'var(--surface-raised)',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          color: 'var(--text-muted)',
        }}>
          <Info size={12} />
          Estimated cost per run: <strong style={{ color: 'var(--text-primary)' }}>${estimatedCost.toFixed(3)}</strong> ({platforms.length} platform{platforms.length !== 1 ? 's' : ''})
        </div>
      </div>

      {/* Advanced: provided content */}
      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced(v => !v)}
          style={{
            background: 'none',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 12,
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: 0,
            marginBottom: showAdvanced ? 8 : 0,
          }}
        >
          <Settings2 size={12} />
          Advanced options
          {showAdvanced ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>

        {showAdvanced && (
          <div className="form-group" style={{ marginTop: 4 }}>
            <label className="form-label">Provided Content (skips content generation)</label>
            <textarea
              className="input"
              rows={4}
              placeholder="Paste your own post copy here to bypass AI content generation..."
              value={providedContent}
              onChange={e => setProvidedContent(e.target.value)}
              style={{ resize: 'vertical', fontFamily: 'inherit' }}
            />
          </div>
        )}
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        disabled={loading || !topic.trim() || platforms.length === 0}
        style={{ width: '100%', marginTop: 8, gap: 6 }}
      >
        <Play size={14} />
        {loading ? 'Starting run…' : 'Start Run'}
      </button>
    </form>
  );
}
