'use client';
import { useRouter } from 'next/navigation';
import { LogOut } from 'lucide-react';

export function SignOutButton() {
  const router = useRouter();

  async function signOut() {
    await fetch('/api/auth', { method: 'DELETE' });
    router.push('/login');
  }

  return (
    <button onClick={signOut} className="sidebar-item" style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer' }}>
      <LogOut size={16} className="sidebar-item-icon" />
      <span className="sidebar-item-label">Sign Out</span>
    </button>
  );
}
