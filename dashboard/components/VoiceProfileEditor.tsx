'use client';
import { useState } from 'react';
import { X } from 'lucide-react';

export interface VoiceProfile {
  tone: 'professional' | 'casual' | 'witty' | 'authoritative';
  personality: string;
  writing_style: string;
  avoid_phrases: string[];
  platform_overrides: Record<string, string>;
  example_ctas: string[];
}

interface Props {
  profile: VoiceProfile;
  onSave: (p: VoiceProfile) => void;
  saving?: boolean;
}

const TONES: { id: VoiceProfile['tone']; label: string }[] = [
  { id: 'professional', label: 'Professional' },
  { id: 'casual',       label: 'Casual' },
  { id: 'witty',        label: 'Witty' },
  { id: 'authoritative', label: 'Authoritative' },
];

const PLATFORMS = ['linkedin', 'instagram', 'twitter'];

export default function VoiceProfileEditor({ profile, onSave, saving }: Props) {
  const [tone, setTone]                     = useState<VoiceProfile['tone']>(profile.tone);
  const [personality, setPersonality]       = useState(profile.personality);
  const [writingStyle, setWritingStyle]     = useState(profile.writing_style);
  const [avoidPhrases, setAvoidPhrases]     = useState<string[]>(profile.avoid_phrases ?? []);
  const [avoidInput, setAvoidInput]         = useState('');
  const [platformOverrides, setPlatformOverrides] = useState<Record<string, string>>(
    () => {
      const base: Record<string, string> = { linkedin: '', instagram: '', twitter: '' };
      return { ...base, ...(profile.platform_overrides ?? {}) };
    }
  );
  const [exampleCtas, setExampleCtas]       = useState<string[]>(profile.example_ctas ?? []);
  const [ctaInput, setCtaInput]             = useState('');

  function addTag(
    value: string,
    list: string[],
    setList: (v: string[]) => void,
    setInput: (v: string) => void
  ) {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) {
      setList([...list, trimmed]);
    }
    setInput('');
  }

  function removeTag(idx: number, list: string[], setList: (v: string[]) => void) {
    setList(list.filter((_, i) => i !== idx));
  }

  function handleSave() {
    onSave({
      tone,
      personality,
      writing_style: writingStyle,
      avoid_phrases: avoidPhrases,
      platform_overrides: platformOverrides,
      example_ctas: exampleCtas,
    });
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Tone */}
      <div className="form-group">
        <label className="form-label">Tone</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {TONES.map(t => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTone(t.id)}
              className={`badge ${tone === t.id ? 'badge-primary' : 'badge-muted'}`}
              style={{ cursor: 'pointer', padding: '6px 14px', fontSize: 13 }}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Personality */}
      <div className="form-group">
        <label className="form-label">Personality</label>
        <textarea
          rows={3}
          className="input"
          value={personality}
          onChange={e => setPersonality(e.target.value)}
          placeholder="e.g. data-driven expert who helps Pakistani SMBs"
          style={{ resize: 'vertical', minHeight: 72 }}
        />
      </div>

      {/* Writing Style */}
      <div className="form-group">
        <label className="form-label">Writing Style</label>
        <textarea
          rows={3}
          className="input"
          value={writingStyle}
          onChange={e => setWritingStyle(e.target.value)}
          placeholder="e.g. short punchy sentences, active voice"
          style={{ resize: 'vertical', minHeight: 72 }}
        />
      </div>

      {/* Avoid Phrases */}
      <div className="form-group">
        <label className="form-label">Avoid Phrases</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {avoidPhrases.map((phrase, i) => (
            <span
              key={i}
              className="badge badge-muted"
              style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'default' }}
            >
              {phrase}
              <button
                type="button"
                onClick={() => removeTag(i, avoidPhrases, setAvoidPhrases)}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', lineHeight: 1, display: 'flex', alignItems: 'center' }}
              >
                <X size={11} color="var(--text-muted)" />
              </button>
            </span>
          ))}
        </div>
        <input
          type="text"
          className="input"
          value={avoidInput}
          onChange={e => setAvoidInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addTag(avoidInput, avoidPhrases, setAvoidPhrases, setAvoidInput);
            }
          }}
          placeholder="Type a phrase and press Enter to add"
        />
      </div>

      {/* Platform Overrides */}
      <div className="form-group">
        <label className="form-label">Platform Overrides</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {PLATFORMS.map(platform => (
            <div key={platform} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{
                width: 80, flexShrink: 0,
                fontSize: 12, fontWeight: 600,
                color: 'var(--text-muted)',
                textTransform: 'capitalize',
              }}>
                {platform}
              </span>
              <input
                type="text"
                className="input"
                value={platformOverrides[platform] ?? ''}
                onChange={e => setPlatformOverrides(prev => ({ ...prev, [platform]: e.target.value }))}
                placeholder={`Extra instruction for ${platform}…`}
                style={{ flex: 1 }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Example CTAs */}
      <div className="form-group">
        <label className="form-label">Example CTAs</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {exampleCtas.map((cta, i) => (
            <span
              key={i}
              className="badge badge-muted"
              style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'default' }}
            >
              {cta}
              <button
                type="button"
                onClick={() => removeTag(i, exampleCtas, setExampleCtas)}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', lineHeight: 1, display: 'flex', alignItems: 'center' }}
              >
                <X size={11} color="var(--text-muted)" />
              </button>
            </span>
          ))}
        </div>
        <input
          type="text"
          className="input"
          value={ctaInput}
          onChange={e => setCtaInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addTag(ctaInput, exampleCtas, setExampleCtas, setCtaInput);
            }
          }}
          placeholder="Type a CTA and press Enter to add"
        />
      </div>

      {/* Save */}
      <div>
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="btn btn-primary btn-sm"
        >
          {saving ? 'Saving…' : 'Save Voice Profile'}
        </button>
      </div>
    </div>
  );
}
