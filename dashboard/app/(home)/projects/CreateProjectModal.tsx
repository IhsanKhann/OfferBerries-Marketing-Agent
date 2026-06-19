'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { X, ChevronRight, ChevronLeft, Brain, BrainCog, Check } from 'lucide-react';
import { toast } from 'sonner';
import type { CreateProjectInput, Project } from '@/hooks/useProjects';

const COLORS = [
  '#6366F1', '#7C3AED', '#0EA5E9', '#059669',
  '#D97706', '#DC2626', '#DB2777', '#0284C7',
];

const ICONS = ['📁', '🚀', '🎯', '🌙', '⭐', '🔥', '💡', '📊', '🌿', '🎨', '💼', '📣'];

const PLATFORMS = [
  { id: 'linkedin', label: 'LinkedIn' },
  { id: 'instagram', label: 'Instagram' },
  { id: 'twitter', label: 'Twitter/X' },
  { id: 'youtube', label: 'YouTube' },
  { id: 'email', label: 'Email' },
];

const MODELS = [
  { id: 'sonar', label: 'Sonar', desc: 'Fast, good for quick campaigns' },
  { id: 'sonar-pro', label: 'Sonar Pro', desc: 'Deeper research, recommended' },
];

interface Props {
  onClose: () => void;
  onCreate: (input: CreateProjectInput) => Promise<Project>;
}

export function CreateProjectModal({ onClose, onCreate }: Props) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState(COLORS[0]);
  const [icon, setIcon] = useState('📁');

  const [brandVoice, setBrandVoice] = useState('');
  const [platforms, setPlatforms] = useState<string[]>(['linkedin', 'instagram']);
  const [model, setModel] = useState('sonar-pro');

  const [memoryEnabled, setMemoryEnabled] = useState(true);

  function togglePlatform(id: string) {
    setPlatforms(prev =>
      prev.includes(id) ? prev.filter(p => p !== id) : [...prev, id]
    );
  }

  async function handleSubmit() {
    if (!name.trim()) return;
    setSaving(true);
    try {
      const project = await onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        brand_voice: brandVoice.trim() || undefined,
        default_platforms: platforms,
        default_model: model,
        color,
        icon,
        memory_enabled: memoryEnabled,
      });
      toast.success(`"${project.name}" created`);
      router.push(`/projects/${project.id}`);
    } catch {
      toast.error('Failed to create project. Please try again.');
    } finally {
      setSaving(false);
    }
  }

  const steps = ['Details', 'Platforms', 'Memory'];

  return (
    <div className="modal-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="create-project-modal">
        {/* Header */}
        <div className="modal-header">
          <h2 className="modal-title">New Project</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        {/* Step dots */}
        <div className="modal-steps">
          {steps.map((label, i) => (
            <div key={i} className={`modal-step ${i === step ? 'modal-step--active' : ''} ${i < step ? 'modal-step--done' : ''}`}>
              <div className="modal-step-dot">
                {i < step ? <Check size={10} /> : i + 1}
              </div>
              <span className="modal-step-label">{label}</span>
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="modal-body">
          {step === 0 && (
            <div className="modal-step-content">
              <div className="form-group">
                <label className="form-label">Project name <span className="form-required">*</span></label>
                <input
                  className="form-input"
                  placeholder="e.g. Ramadan Campaign 2026"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label className="form-label">Description</label>
                <textarea
                  className="form-input form-textarea"
                  placeholder="What is this project about?"
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  rows={2}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Icon</label>
                <div className="icon-picker-grid">
                  {ICONS.map(ic => (
                    <button
                      key={ic}
                      className={`icon-picker-item ${icon === ic ? 'icon-picker-item--active' : ''}`}
                      onClick={() => setIcon(ic)}
                      type="button"
                    >
                      {ic}
                    </button>
                  ))}
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Color</label>
                <div className="color-swatch-grid">
                  {COLORS.map(c => (
                    <button
                      key={c}
                      className={`color-swatch ${color === c ? 'color-swatch--active' : ''}`}
                      style={{ background: c }}
                      onClick={() => setColor(c)}
                      type="button"
                      aria-label={c}
                    >
                      {color === c && <Check size={12} />}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="modal-step-content">
              <div className="form-group">
                <label className="form-label">Brand voice</label>
                <textarea
                  className="form-input form-textarea"
                  placeholder="Describe how your brand communicates. e.g. 'Friendly and approachable, speaks to Pakistani SMB owners, avoids jargon'"
                  value={brandVoice}
                  onChange={e => setBrandVoice(e.target.value)}
                  rows={3}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Default platforms</label>
                <div className="platform-checkbox-grid">
                  {PLATFORMS.map(p => (
                    <label key={p.id} className="platform-checkbox-item">
                      <input
                        type="checkbox"
                        checked={platforms.includes(p.id)}
                        onChange={() => togglePlatform(p.id)}
                      />
                      <span>{p.label}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">Research model</label>
                <div className="model-radio-group">
                  {MODELS.map(m => (
                    <label key={m.id} className={`model-radio-item ${model === m.id ? 'model-radio-item--active' : ''}`}>
                      <input
                        type="radio"
                        name="model"
                        value={m.id}
                        checked={model === m.id}
                        onChange={() => setModel(m.id)}
                      />
                      <div>
                        <div className="model-radio-label">{m.label}</div>
                        <div className="model-radio-desc">{m.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="modal-step-content">
              <p className="memory-intro">
                Project memory lets chats in this project build on each other.
                When enabled, each completed chat stores its research and generated content —
                so the next chat picks up where you left off.
              </p>
              <div className="memory-toggle-options">
                <button
                  className={`memory-toggle-card ${memoryEnabled ? 'memory-toggle-card--active' : ''}`}
                  onClick={() => setMemoryEnabled(true)}
                  type="button"
                >
                  <div className="memory-toggle-card-icon">
                    <Brain size={28} />
                  </div>
                  <div className="memory-toggle-card-content">
                    <div className="memory-toggle-card-title">Memory ON</div>
                    <div className="memory-toggle-card-desc">
                      Chats remember context from previous conversations in this project.
                      Past research, hooks, and campaigns are recalled automatically to
                      suggest fresh, complementary angles.
                    </div>
                    <div className="memory-toggle-card-use-case">
                      Best for: ongoing campaigns, brand storytelling, seasonal series
                    </div>
                  </div>
                  {memoryEnabled && <Check size={16} className="memory-toggle-check" />}
                </button>

                <button
                  className={`memory-toggle-card ${!memoryEnabled ? 'memory-toggle-card--active' : ''}`}
                  onClick={() => setMemoryEnabled(false)}
                  type="button"
                >
                  <div className="memory-toggle-card-icon memory-toggle-card-icon--off">
                    <BrainCog size={28} />
                  </div>
                  <div className="memory-toggle-card-content">
                    <div className="memory-toggle-card-title">Memory OFF</div>
                    <div className="memory-toggle-card-desc">
                      Each chat starts completely fresh. No shared context between
                      conversations. Keeps your database lean.
                    </div>
                    <div className="memory-toggle-card-use-case">
                      Best for: one-off posts, A/B testing, isolated campaigns
                    </div>
                  </div>
                  {!memoryEnabled && <Check size={16} className="memory-toggle-check" />}
                </button>
              </div>

              <p className="memory-change-note">
                You can change this setting later from the project workspace.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          {step > 0 ? (
            <button className="btn-ghost" onClick={() => setStep(s => s - 1)}>
              <ChevronLeft size={16} />
              Back
            </button>
          ) : (
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
          )}

          {step < steps.length - 1 ? (
            <button
              className="btn-primary"
              onClick={() => setStep(s => s + 1)}
              disabled={step === 0 && !name.trim()}
            >
              Next
              <ChevronRight size={16} />
            </button>
          ) : (
            <button
              className="btn-primary"
              onClick={handleSubmit}
              disabled={saving || !name.trim()}
            >
              {saving ? 'Creating…' : 'Create Project'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
