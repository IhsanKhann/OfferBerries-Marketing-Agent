import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      // Only include the testable UI layer — exclude Next.js page/layout server components
      include: [
        'hooks/**/*.ts',
        'app/**/queue/PostCard.tsx',
        'app/**/queue/PostPreviewPanel.tsx',
        'app/**/queue/AgentPipelinePanel.tsx',
        'app/**/queue/AgentInputBar.tsx',
        'app/**/queue/AgentChatThread.tsx',
        'components/AgentErrorBanner.tsx',
        'lib/toast.ts',
      ],
    },
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
});
