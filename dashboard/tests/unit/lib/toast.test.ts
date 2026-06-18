import { describe, it, expect, vi, beforeEach } from 'vitest';
import { notify } from '../../../lib/toast';

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    promise: vi.fn(),
  },
}));

describe('notify', () => {
  beforeEach(() => vi.clearAllMocks());

  it('notify.success calls toast.success', async () => {
    const { toast } = await import('sonner');
    notify.success('Done', 'Post saved');
    expect(toast.success).toHaveBeenCalledWith('Done', { description: 'Post saved' });
  });

  it('notify.error calls toast.error', async () => {
    const { toast } = await import('sonner');
    notify.error('Failed', 'Could not save');
    expect(toast.error).toHaveBeenCalledWith('Failed', { description: 'Could not save' });
  });

  it('notify.info calls toast.info', async () => {
    const { toast } = await import('sonner');
    notify.info('Running', 'Pipeline started');
    expect(toast.info).toHaveBeenCalledWith('Running', { description: 'Pipeline started' });
  });

  it('notify.warning calls toast.warning', async () => {
    const { toast } = await import('sonner');
    notify.warning('Caution', 'Rate limit near');
    expect(toast.warning).toHaveBeenCalledWith('Caution', { description: 'Rate limit near' });
  });

  it('notify.promise calls toast.promise', async () => {
    const { toast } = await import('sonner');
    const p = Promise.resolve('ok');
    notify.promise(p, { loading: 'Saving…', success: 'Saved', error: 'Failed' });
    expect(toast.promise).toHaveBeenCalledWith(
      p,
      { loading: 'Saving…', success: 'Saved', error: 'Failed' }
    );
  });

  it('notify.success without description passes undefined', async () => {
    const { toast } = await import('sonner');
    notify.success('Done');
    expect(toast.success).toHaveBeenCalledWith('Done', { description: undefined });
  });
});
