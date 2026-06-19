'use client';
import { RefObject } from 'react';
import { Bot, ExternalLink } from 'lucide-react';

export type ChatMessage = { role: 'user' | 'assistant'; content: string };

interface Props {
  messages: ChatMessage[];
  running: boolean;
  currentStage: string;
  runStatus: string;
  chatRef: RefObject<HTMLDivElement>;
}

const STAGE_LABELS: Record<string, string> = {
  research:           'Searching Perplexity…',
  content_generation: 'Generating content…',
  visual_generation:  'Rendering visuals…',
  scheduling:         'Scheduling posts…',
};

function renderContent(text: string) {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];

  lines.forEach((line, lineIdx) => {
    // Citation link lines: [1] https://...
    const citationMatch = line.match(/^\[(\d+)\]\s+(https?:\/\/\S+)(.*)$/);
    if (citationMatch) {
      const [, num, url, rest] = citationMatch;
      elements.push(
        <div key={lineIdx} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
          <span style={{ fontSize: 10, fontWeight: 700, background: 'rgba(99,102,241,0.12)', color: '#6366F1', padding: '1px 5px', borderRadius: 4, flexShrink: 0 }}>{num}</span>
          <a href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: '#0EA5E9', textDecoration: 'none', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
            {url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
            {rest && <span style={{ color: 'var(--text-muted)' }}>{rest}</span>}
          </a>
          <ExternalLink size={10} style={{ color: '#0EA5E9', flexShrink: 0 }} />
        </div>
      );
      return;
    }

    // Inline formatting: **bold**, *italic*
    const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g);
    const formatted = parts.map((part, pi) => {
      if (part.startsWith('**') && part.endsWith('**')) return <strong key={pi}>{part.slice(2, -2)}</strong>;
      if (part.startsWith('*') && part.endsWith('*')) return <em key={pi}>{part.slice(1, -1)}</em>;
      return part;
    });

    if (line === '') {
      elements.push(<div key={lineIdx} style={{ height: 6 }} />);
    } else {
      elements.push(<div key={lineIdx}>{formatted}</div>);
    }
  });

  return <>{elements}</>;
}

export default function AgentChatThread({ messages, running, currentStage, runStatus, chatRef }: Props) {
  return (
    <div className="chat-messages" ref={chatRef}>
      {messages.map((msg, i) =>
        msg.role === 'assistant' ? (
          <div key={i} className="agent-msg-row">
            <div className="agent-avatar">
              <Bot size={14} color="white" />
            </div>
            <div className="agent-bubble">
              <div className="bubble-label">Agent</div>
              <div className="bubble-body" style={{ background: 'var(--bg-canvas)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', borderBottomLeftRadius: 'var(--radius-xs)' }}>
                {renderContent(msg.content)}
              </div>
            </div>
          </div>
        ) : (
          <div key={i} className="chat-bubble user">
            <div className="bubble-body" style={{ background: 'var(--brand-gradient)', color: 'white', borderBottomRightRadius: 'var(--radius-xs)' }}>
              {msg.content}
            </div>
          </div>
        )
      )}

      {running && (
        <div className="agent-msg-row">
          <div className="agent-avatar">
            <Bot size={14} color="white" />
          </div>
          <div className="agent-bubble">
            <div className="bubble-label">Agent</div>
            <div className="bubble-body" style={{ background: 'var(--bg-canvas)', color: 'var(--text-primary)', border: '1px solid var(--border-default)', borderBottomLeftRadius: 'var(--radius-xs)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="spinner spinner-dark" />
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                {STAGE_LABELS[currentStage] ?? (runStatus === 'starting' ? 'Starting pipeline…' : 'Processing…')}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
