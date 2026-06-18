'use client';
import { RefObject } from 'react';
import { Bot } from 'lucide-react';

export type ChatMessage = { role: 'user' | 'assistant'; content: string };

interface Props {
  messages: ChatMessage[];
  running: boolean;
  currentStage: string;
  runStatus: string;
  chatRef: RefObject<HTMLDivElement>;
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
                {msg.content}
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
                {currentStage
                  ? `Running ${currentStage.replace(/_/g, ' ')}…`
                  : runStatus === 'starting'
                  ? 'Starting pipeline…'
                  : 'Processing…'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
