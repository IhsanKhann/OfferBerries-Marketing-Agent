import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentInputBar from '../../../app/(app)/queue/AgentInputBar';

const DEFAULT_PROPS = {
  topic: '',
  setTopic: vi.fn(),
  running: false,
  onRun: vi.fn(),
  researchModel: 'sonar',
  setResearchModel: vi.fn(),
  contentModel: 'anthropic/claude-sonnet-4-6',
  setContentModel: vi.fn(),
  onAttachFiles: vi.fn(),
  onAttachImages: vi.fn(),
};

describe('AgentInputBar', () => {
  it('renders textarea with placeholder', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} />);
    expect(screen.getByPlaceholderText(/Enter a topic/)).toBeInTheDocument();
  });

  it('renders research model selector', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText('Research model')).toBeInTheDocument();
  });

  it('renders content model selector', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} />);
    expect(screen.getByLabelText('Content model')).toBeInTheDocument();
  });

  it('research model select shows current value', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} researchModel="sonar-pro" />);
    const select = screen.getByLabelText('Research model') as HTMLSelectElement;
    expect(select.value).toBe('sonar-pro');
  });

  it('content model select shows current value', () => {
    render(<AgentInputBar {...DEFAULT_PROPS} contentModel="google/gemini-2.5-flash" />);
    const select = screen.getByLabelText('Content model') as HTMLSelectElement;
    expect(select.value).toBe('google/gemini-2.5-flash');
  });

  it('calls setResearchModel when research model is changed', async () => {
    const setResearchModel = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} setResearchModel={setResearchModel} />);
    await userEvent.selectOptions(screen.getByLabelText('Research model'), 'sonar-deep-research');
    expect(setResearchModel).toHaveBeenCalledWith('sonar-deep-research');
  });

  it('calls setContentModel when content model is changed', async () => {
    const setContentModel = vi.fn();
    render(<AgentInputBar {...DEFAULT_PROPS} setContentModel={setContentModel} />);
    await userEvent.selectOptions(screen.getByLabelText('Content model'), 'google/gemini-2.5-flash');
    expect(setContentModel).toHaveBeenCalledWith('google/gemini-2.5-flash');
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
    await userEvent.tab(); // blur
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
