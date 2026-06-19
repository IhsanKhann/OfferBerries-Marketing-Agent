'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { LogOut, User } from 'lucide-react';

export function SiteHeader() {
  const router = useRouter();

  async function handleSignOut() {
    await fetch('/api/auth', { method: 'DELETE' });
    router.push('/login');
  }

  return (
    <header className="site-header">
      <Link href="/projects" className="site-logo">
        <span className="site-logo-mark">O</span>
        <span className="site-logo-name">OfferBerries</span>
      </Link>
      <div className="site-header-right">
        <Link href="/profile" className="site-header-profile-btn" title="Profile">
          <User size={15} />
        </Link>
        <button className="site-header-signout" onClick={handleSignOut} title="Sign out">
          <LogOut size={16} />
          <span>Sign out</span>
        </button>
      </div>
    </header>
  );
}
