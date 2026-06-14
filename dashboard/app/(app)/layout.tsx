import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { SignOutButton } from './sign-out-button';

const NAV = [
  { href: '/queue', label: 'Queue' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/templates', label: 'Templates' },
  { href: '/settings', label: 'Settings' },
  { href: '/billing', label: 'Billing' },
  { href: '/tenants', label: 'Tenants' },
  { href: '/demo', label: 'Demo' },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = cookies();
  const session = cookieStore.get('ofb_session');
  if (!session) redirect('/login');

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220,
        background: 'var(--sidebar-dark)',
        display: 'flex',
        flexDirection: 'column',
        padding: '32px 0',
        flexShrink: 0,
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        zIndex: 10,
      }}>
        <div style={{ padding: '0 24px', marginBottom: 32 }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: 'white', letterSpacing: '-0.01em' }}>OfferBerries</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontWeight: 500, marginTop: 2 }}>Marketing Agent</div>
        </div>
        <nav style={{ flex: 1 }}>
          {NAV.map(({ href, label }) => (
            <Link key={href} href={href} style={{
              display: 'block',
              padding: '10px 24px',
              fontSize: 14,
              fontWeight: 500,
              color: 'rgba(255,255,255,0.7)',
            }}>
              {label}
            </Link>
          ))}
        </nav>
        <div style={{ padding: '16px 24px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <a
            href={`https://design.${process.env.DOMAIN || 'yourdomain.com'}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', display: 'block', marginBottom: 12 }}
          >
            Open Design Studio
          </a>
          <SignOutButton />
        </div>
      </aside>
      {/* Main content */}
      <main style={{ flex: 1, marginLeft: 220, padding: '32px 40px', minHeight: '100vh' }}>
        {children}
      </main>
    </div>
  );
}
