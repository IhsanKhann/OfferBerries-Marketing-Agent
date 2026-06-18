'use client';
import { useRef, useState, KeyboardEvent } from 'react';
import { Paperclip, Image, Wand2 } from 'lucide-react';
import { RESEARCH_MODELS } from '../../../hooks/useAgentRun';

interface Props {
  topic: string;
  setTopic: (v: string) => void;
  running: boolean;
  onRun: () => void;
  researchModel: string;
  setResearchModel: (id: string) => void;
  onAttachFiles: (files: FileList) => void;
  onAttachImages: (files: FileList) => void;
}

export default function AgentInputBar({
  topic, setTopic, running, onRun,
  researchModel, setResearchModel,
  onAttachFiles, onAttachImages,
}: Props) {
  const [focused, setFocused] = useState(false);
  const fileRef  = useRef<HTMLInputElement>(null);
  const imageRef = useRef<HTMLInputElement>(null);

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !running) {
      e.preventDefault();
      onRun();
    }
  }

  return (
    <div className="agent-input-bar">
      <input
        ref={fileRef}
        type="file"
        multiple
        style={{ display: 'none' }}
        onChange={e => e.target.files && onAttachFiles(e.target.files)}
      />
      <input
        ref={imageRef}
        type="file"
        accept="image/*"
        multiple
        style={{ display: 'none' }}
        onChange={e => e.target.files && onAttachImages(e.target.files)}
      />

      <div className={`agent-input-bar__wrap${focused ? ' focused' : ''}${running ? ' disabled' : ''}`}>
        {/* Left icon buttons */}
        <button
          type="button"
          className="input-icon-btn"
          title="Attach file"
          onClick={() => fileRef.current?.click()}
          disabled={running}
        >
          <Paperclip size={16} />
        </button>
        <button
          type="button"
          className="input-icon-btn"
          title="Attach image reference"
          onClick={() => imageRef.current?.click()}
          disabled={running}
        >
          <Image size={16} />
        </button>

        {/* Textarea */}
        <textarea
          value={topic}
          onChange={e => setTopic(e.target.value)}
          onKeyDown={handleKey}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Enter a topic to research and create content about…"
          rows={1}
          disabled={running}
        />

        {/* Right cluster: model chips + run button */}
        <div className="input-right-cluster">
          {RESEARCH_MODELS.map(m => (
            <button
              key={m.id}
              type="button"
              className={`input-cost-chip${researchModel === m.id ? ' active' : ''}`}
              onClick={() => setResearchModel(m.id)}
              title={m.label}
              disabled={running}
            >
              {m.label}
              <span style={{ opacity: 0.7, fontSize: 10 }}>{m.badge}</span>
            </button>
          ))}
          <button
            type="button"
            className="input-run-btn"
            onClick={onRun}
            disabled={running || !topic.trim()}
            title="Run agent"
          >
            {running
              ? <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
              : <Wand2 size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
