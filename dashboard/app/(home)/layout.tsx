import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { Sidebar } from '../(app)/sidebar';

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = cookies();
  const session = cookieStore.get('ofb_session');
  if (!session) redirect('/login');

  return (
    <div className="shell">
      <Sidebar />
      <div className="main-content" id="main-content">
        {children}
      </div>
    </div>
  );
}
