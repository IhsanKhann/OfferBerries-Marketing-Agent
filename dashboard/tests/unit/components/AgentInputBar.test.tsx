import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentInputBar from '../../../app/(app)/queue/AgentInputBar';

const DEFAULT_PROPS = {
  topic: '',
  setTopic: vi.fn(),
  running: false,
  onRun: vi.fn(),
  onOpenOptions: vi.fn(),
  onAttachFiles: vi.fn(),
  onAttachImages: vi.fn(),
};

describe('AgentInputBar', () => {
  it('renders textarea with placeholder', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} />);
    expect(screen.getByPlaceholderText(/Enter a topic/)).toBeInTheDocument();
  });

  it('renders options button', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} />);
    expect(screen.getByTitle(/Options/)).toBeInTheDocument();
  });

  it('calls onOpenOptions when options button is clicked', async () => {
    const onOpenOptions = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} onOpenOptions={onOpenOptions} />);
    await userEvent.click(screen.getByTitle(/Options/));
    expect(onOpenOptions).toHaveBeenCalled();
  });

  it('run button is disabled when topic is empty', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} topic="" />);
    expect(screen.getByTitle('Run agent')).toBeDisabled();
  });

  it('run button is disabled when running=true', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} topic="payroll" running={true} />);
    expect(screen.getByTitle('Run agent')).toBeDisabled();
  });

  it('run button is enabled when topic is non-empty and not running', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} topic="payroll automation" />);
    expect(screen.getByTitle('Run agent')).not.toBeDisabled();
  });

  it('calls onRun when run button is clicked', async () => {
    const onRun = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} topic="payroll" onRun={onRun} />);
    await userEvent.click(screen.getByTitle('Run agent'));
    expect(onRun).toHaveBeenCalled();
  });

  it('calls onRun on Enter keydown (no shift)', () => {
    const onRun = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} topic="payroll" onRun={onRun} />);
    const textarea = screen.getByPlaceholderText(/Enter a topic/);
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onRun).toHaveBeenCalled();
  });

  it('does NOT call onRun on Shift+Enter', () => {
    const onRun = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} topic="payroll" onRun={onRun} />);
    const textarea = screen.getByPlaceholderText(/Enter a topic/);
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(onRun).not.toHaveBeenCalled();
  });

  it('does NOT call onRun on Enter when running=true', () => {
    const onRun = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} topic="payroll" onRun={onRun} running={true} />);
    const textarea = screen.getByPlaceholderText(/Enter a topic/);
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onRun).not.toHaveBeenCalled();
  });

  it('textarea is disabled when running=true', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} running={true} />);
    expect(screen.getByPlaceholderText(/Enter a topic/)).toBeDisabled();
  });

  it('adds "focused" class on wrapper when textarea is focused', async () => {
    const { container } = render(<AgentInputBar {...DEFAULT_PROPS} />);
    const textarea = screen.getByPlaceholderText(/Enter a topic/);
    await userEvent.click(textarea);
    expect(container.querySelector('.agent-input-bar__wrap')).toHaveClass('focused');
  });

  it('removes "focused" class when textarea loses focus', async () => {
    const { container } = render(<AgentInputBar {...DEFAULT_PROPS} />);
    const textarea = screen.getByPlaceholderText(/Enter a topic/);
    await userEvent.click(textarea);
    await userEvent.tab();
    expect(container.querySelector('.agent-input-bar__wrap')).not.toHaveClass('focused');
  });

  it('adds "disabled" class when running=true', () => {
    const { container } = render(<AgentInputBar {...DEFAULT_PROPS} running={true} />);
    expect(container.querySelector('.agent-input-bar__wrap')).toHaveClass('disabled');
  });

  it('shows spinner inside run button when running', () => {
    const { container } = render(<AgentInputBar {...DEFAULT_PROPS} running={true} />);
    expect(container.querySelector('.input-run-btn .spinner')).toBeInTheDocument();
  });
});
