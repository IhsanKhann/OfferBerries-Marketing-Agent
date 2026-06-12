import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'OfferBerries Marketing Agent',
  description: 'AI-powered marketing automation for Pakistani SMBs',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
