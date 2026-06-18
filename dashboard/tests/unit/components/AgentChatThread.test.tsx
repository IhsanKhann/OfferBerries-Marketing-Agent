import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { createRef } from 'react';
import AgentChatThread from '../../../app/(app)/queue/AgentChatThread';
import type { ChatMessage } from '../../../app/(app)/queue/AgentChatThread';

const MESSAGES: ChatMessage[] = [
  { role: 'user', content: 'Research payroll automation for Pakistani SMBs' },
  { role: 'assistant', content: 'Starting research on payroll automation…' },
];

describe('AgentChatThread', () => {
  it('renders user messages', () => {
    const ref = createRef<HTMLDivElement>();
    render(
      <AgentChatThread
        messages={MESSAGES}
        running={false}
        currentStage=""
        runStatus="idle"
        chatRef={ref}
      />
    );
    expect(screen.getByText('Research payroll automation for Pakistani SMBs')).toBeInTheDocument();
  });

  it('renders assistant messages', () => {
    const ref = createRef<HTMLDivElement>();
    render(
      <AgentChatThread
        messages={MESSAGES}
        running={false}
        currentStage=""
        runStatus="idle"
        chatRef={ref}
      />
    );
    expect(screen.getByText('Starting research on payroll automation…')).toBeInTheDocument();
  });

  it('renders empty state with no messages', () => {
    const ref = createRef<HTMLDivElement>();
    const { container } = render(
      <AgentChatThread
        messages={[]}
        running={false}
        currentStage=""
        runStatus="idle"
        chatRef={ref}
      />
    );
    expect(container.querySelector('.chat-messages')).toBeInTheDocument();
  });

  it('shows spinner when running=true with no currentStage', () => {
    const ref = createRef<HTMLDivElement>();
    const { container } = render(
      <AgentChatThread
        messages={[]}
        running={true}
        currentStage=""
        runStatus="starting"
        chatRef={ref}
      />
    );
    expect(container.querySelector('.spinner')).toBeInTheDocument();
    expect(screen.getByText('Starting pipeline…')).toBeInTheDocument();
  });

  it('shows current stage name when running with a currentStage', () => {
    const ref = createRef<HTMLDivElement>();
    render(
      <AgentChatThread
        messages={[]}
        running={true}
        currentStage="content_generation"
        runStatus="running"
        chatRef={ref}
      />
    );
    expect(screen.getByText('Running content generation…')).toBeInTheDocument();
  });

  it('shows "Processing…" when running but runStatus is not "starting"', () => {
    const ref = createRef<HTMLDivElement>();
    render(
      <AgentChatThread
        messages={[]}
        running={true}
        currentStage=""
        runStatus="running"
        chatRef={ref}
      />
    );
    expect(screen.getByText('Processing…')).toBeInTheDocument();
  });

  it('does NOT show spinner when running=false', () => {
    const ref = createRef<HTMLDivElement>();
    const { container } = render(
      <AgentChatThread
        messages={[]}
        running={false}
        currentStage=""
        runStatus="idle"
        chatRef={ref}
      />
    );
    expect(container.querySelector('.spinner')).not.toBeInTheDocument();
  });

  it('uses chat-messages class on wrapper', () => {
    const ref = createRef<HTMLDivElement>();
    const { container } = render(
      <AgentChatThread
        messages={MESSAGES}
        running={false}
        currentStage=""
        runStatus="idle"
        chatRef={ref}
      />
    );
    expect(container.firstChild).toHaveClass('chat-messages');
  });

  it('renders Agent label for assistant messages', () => {
    const ref = createRef<HTMLDivElement>();
    render(
      <AgentChatThread
        messages={[{ role: 'assistant', content: 'Hello' }]}
        running={false}
        currentStage=""
        runStatus="idle"
        chatRef={ref}
      />
    );
    expect(screen.getByText('Agent')).toBeInTheDocument();
  });
});
