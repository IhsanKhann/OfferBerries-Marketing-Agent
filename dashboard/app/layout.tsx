import type { Metadata } from 'next';
import { Toaster } from 'sonner';
import './globals.css';

export const metadata: Metadata = {
  title: 'OfferBerries Marketing Agent',
  description: 'AI-powered marketing automation for Pakistani SMBs',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <Toaster
          position="top-right"
          richColors
          closeButton
          toastOptions={{
            style: {
              background: 'var(--bg-canvas)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-sans)',
              fontSize: '13px',
            },
          }}
        />
      </body>
    </html>
  );
}
