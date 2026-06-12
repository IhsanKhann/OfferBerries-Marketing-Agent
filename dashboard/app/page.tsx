import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';

export default function Home() {
  const cookieStore = cookies();
  const session = cookieStore.get('ofb_session');
  if (session) {
    redirect('/queue');
  } else {
    redirect('/login');
  }
}
