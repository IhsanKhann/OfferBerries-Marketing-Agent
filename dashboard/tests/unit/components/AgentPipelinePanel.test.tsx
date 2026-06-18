import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentPipelinePanel from '../../../app/(app)/queue/AgentPipelinePanel';

const IDLE_STATUSES = ['pending', 'pending', 'pending', 'pending'] as const;
const RUNNING_STATUSES = ['done', 'running', 'pending', 'pending'] as const;
const DONE_STATUSES = ['done', 'done', 'done', 'done'] as const;

// next/link renders as <a> in jsdom
describe('AgentPipelinePanel', () => {
  it('renders without crashing', () => {
    render(
      <AgentPipelinePanel
        open={false}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(document.querySelector('.pipeline-panel')).toBeInTheDocument();
  });

  it('adds "open" class when open=true', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(document.querySelector('.pipeline-panel')).toHaveClass('open');
  });

  it('does NOT have "open" class when open=false', () => {
    render(
      <AgentPipelinePanel
        open={false}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(document.querySelector('.pipeline-panel')).not.toHaveClass('open');
  });

  it('shows backdrop when open=true', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(document.querySelector('.pipeline-backdrop')).toBeInTheDocument();
  });

  it('does NOT show backdrop when open=false', () => {
    render(
      <AgentPipelinePanel
        open={false}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(document.querySelector('.pipeline-backdrop')).not.toBeInTheDocument();
  });

  it('renders 4 step items matching STEPS', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(screen.getByText('Research')).toBeInTheDocument();
    expect(screen.getByText('Content Generation')).toBeInTheDocument();
    expect(screen.getByText('Visual Generation')).toBeInTheDocument();
    expect(screen.getByText('Scheduling')).toBeInTheDocument();
  });

  it('shows step-dot with "done" class for completed steps', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...DONE_STATUSES]}
        runId={null}
      />
    );
    const dots = document.querySelectorAll('.step-dot.done');
    expect(dots).toHaveLength(4);
  });

  it('shows ✓ in done step dots', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={['done', 'pending', 'pending', 'pending']}
        runId={null}
      />
    );
    expect(screen.getByText('✓')).toBeInTheDocument();
  });

  it('shows spinner for running step', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={['done', 'running', 'pending', 'pending']}
        runId={null}
      />
    );
    expect(document.querySelector('.step-dot.running .spinner')).toBeInTheDocument();
  });

  it('shows ✗ for failed step', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={['failed', 'pending', 'pending', 'pending']}
        runId={null}
      />
    );
    expect(screen.getByText('✗')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', async () => {
    const onClose = vi.fn();
    render(
      <AgentPipelinePanel
        open={true}
        onClose={onClose}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    await userEvent.click(screen.getByTitle('Close pipeline'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn();
    render(
      <AgentPipelinePanel
        open={true}
        onClose={onClose}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    await userEvent.click(document.querySelector('.pipeline-backdrop') as HTMLElement);
    expect(onClose).toHaveBeenCalled();
  });

  it('shows "View Run" link when runId provided', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId="run-abc123"
      />
    );
    expect(screen.getByTitle('View full run detail')).toBeInTheDocument();
  });

  it('does NOT show "View Run" link when runId is null', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(screen.queryByTitle('View full run detail')).not.toBeInTheDocument();
  });

  it('shows "Drop images here" drop zone', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    expect(screen.getByText(/Drop images here/)).toBeInTheDocument();
  });

  it('shows step numbers for pending steps', () => {
    render(
      <AgentPipelinePanel
        open={true}
        onClose={vi.fn()}
        stepStatuses={[...IDLE_STATUSES]}
        runId={null}
      />
    );
    // Steps 1-4 numbers shown for pending
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });
});
