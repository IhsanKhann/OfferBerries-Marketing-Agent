'use client';
import { useRouter } from 'next/navigation';

export function SignOutButton() {
  const router = useRouter();

  async function signOut() {
    await fetch('/api/auth', { method: 'DELETE' });
    router.push('/login');
  }

  return (
    <button
      onClick={signOut}
      style={{
        background: 'none',
        border: 'none',
        color: 'rgba(255,255,255,0.4)',
        fontSize: 12,
        cursor: 'pointer',
        padding: 0,
        fontFamily: 'inherit',
      }}
    >
      Sign Out
    </button>
  );
}
