import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { SiteHeader } from '@/components/SiteHeader';

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = cookies();
  const session = cookieStore.get('ofb_session');
  if (!session) redirect('/login');

  return (
    <div className="home-shell">
      <SiteHeader />
      <main className="home-main">
        {children}
      </main>
    </div>
  );
}
