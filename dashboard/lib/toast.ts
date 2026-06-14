import { toast } from 'sonner';

export const notify = {
  success: (title: string, description?: string) =>
    toast.success(title, { description }),
  error: (title: string, description?: string) =>
    toast.error(title, { description }),
  info: (title: string, description?: string) =>
    toast.info(title, { description }),
  warning: (title: string, description?: string) =>
    toast.warning(title, { description }),
  promise: <T,>(
    promise: Promise<T>,
    messages: {
      loading: string;
      success: string | ((data: T) => string);
      error: string | ((err: unknown) => string);
    }
  ) => toast.promise(promise, messages),
};
