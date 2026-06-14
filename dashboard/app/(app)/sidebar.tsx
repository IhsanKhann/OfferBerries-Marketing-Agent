'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, BarChart2, Layout, Settings, CreditCard,
  Users, Monitor, Activity, ChevronLeft, ChevronRight, LogOut, PlayCircle,
} from 'lucide-react';

const NAV_MAIN = [
  { href: '/queue',     label: 'Queue',     icon: LayoutDashboard },
  { href: '/runs',      label: 'Runs',      icon: PlayCircle },
  { href: '/analytics', label: 'Analytics', icon: BarChart2 },
  { href: '/templates', label: 'Templates', icon: Layout },
  { href: '/usage',     label: 'Usage',     icon: Activity },
];

const NAV_ACCOUNT = [
  { href: '/settings', label: 'Settings', icon: Settings },
  { href: '/billing',  label: 'Billing',  icon: CreditCard },
  { href: '/tenants',  label: 'Tenants',  icon: Users },
  { href: '/demo',     label: 'Demo',     icon: Monitor },
];

async function signOut() {
  await fetch('/api/auth', { method: 'DELETE' });
  window.location.href = '/login';
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  function NavItem({ href, label, icon: Icon }: { href: string; label: string; icon: React.ElementType }) {
    const active = pathname === href || (href !== '/' && pathname.startsWith(href));
    return (
      <Link href={href} className={`sidebar-item${active ? ' active' : ''}`} title={collapsed ? label : undefined}>
        <Icon size={16} className="sidebar-item-icon" />
        <span className="sidebar-item-label">{label}</span>
      </Link>
    );
  }

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">O</div>
          <div className="sidebar-logo-text">
            <div className="sidebar-logo-name">OfferBerries</div>
            <div className="sidebar-logo-sub">Marketing Agent</div>
          </div>
        </div>
        <button
          className="sidebar-toggle"
          onClick={() => setCollapsed(c => !c)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Main</div>
        {NAV_MAIN.map(n => <NavItem key={n.href} {...n} />)}
        <div className="sidebar-section-label">Account</div>
        {NAV_ACCOUNT.map(n => <NavItem key={n.href} {...n} />)}
      </nav>

      <div className="sidebar-footer">
        <button
          onClick={signOut}
          className="sidebar-item"
          style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer' }}
          title={collapsed ? 'Sign out' : undefined}
        >
          <LogOut size={16} className="sidebar-item-icon" />
          <span className="sidebar-item-label">Sign Out</span>
        </button>
      </div>
    </aside>
  );
}
