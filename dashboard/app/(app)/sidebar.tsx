'use client';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, BarChart2, Layout, Settings, CreditCard,
  Users, Monitor, Activity, ChevronLeft, ChevronRight, LogOut,
  PlayCircle, Wand2, Search, FolderOpen, Plus,
} from 'lucide-react';
import { isToday, isYesterday, isWithinInterval, subDays, formatDistanceToNow } from 'date-fns';
import { useProjects } from '../../hooks/useProjects';

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

interface RunSummary {
  id: string;
  topic: string;
  created_at: string | null;
  overall_status: string;
}

async function signOut() {
  await fetch('/api/auth', { method: 'DELETE' });
  window.location.href = '/login';
}

function groupByDate(runs: RunSummary[]): Record<string, RunSummary[]> {
  const groups: Record<string, RunSummary[]> = {};
  runs.forEach(run => {
    const d = run.created_at ? new Date(run.created_at) : null;
    let label = 'Older';
    if (d) {
      if (isToday(d)) label = 'Today';
      else if (isYesterday(d)) label = 'Yesterday';
      else if (isWithinInterval(d, { start: subDays(new Date(), 7), end: new Date() })) label = 'Last 7 days';
    }
    (groups[label] ??= []).push(run);
  });
  return groups;
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [search, setSearch] = useState('');
  const pathname = usePathname();
  const { projects } = useProjects();

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch('/api/proxy/runs');
      if (!res.ok) return;
      const data = await res.json();
      const list: RunSummary[] = data.runs ?? data;
      setRuns(list.slice(0, 30));
    } catch { /* non-fatal */ }
  }, []);

  useEffect(() => { fetchRuns(); }, [fetchRuns]);

  // Refetch when navigating away from a run page (so history stays fresh)
  useEffect(() => { fetchRuns(); }, [pathname, fetchRuns]);

  function NavItem({ href, label, icon: Icon }: { href: string; label: string; icon: React.ElementType }) {
    const active = pathname === href || (href !== '/' && pathname.startsWith(href));
    return (
      <Link href={href} className={`sidebar-item${active ? ' active' : ''}`} title={collapsed ? label : undefined}>
        <Icon size={16} className="sidebar-item-icon" />
        <span className="sidebar-item-label">{label}</span>
      </Link>
    );
  }

  const filteredRuns = search.trim()
    ? runs.filter(r => r.topic.toLowerCase().includes(search.toLowerCase()))
    : runs;

  const grouped = groupByDate(filteredRuns);
  const GROUP_ORDER = ['Today', 'Yesterday', 'Last 7 days', 'Older'];

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      {/* Header: Logo + collapse toggle */}
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

      {/* New Run button */}
      <div className="sidebar-new-run-wrap">
        <Link href="/runs/new" className="sidebar-new-run" title={collapsed ? 'New Run' : undefined}>
          <Wand2 size={15} />
          <span className="sidebar-new-run-label">New Run</span>
        </Link>
      </div>

      {/* Search */}
      <div className="sidebar-search-wrap">
        <div className="sidebar-search">
          <Search size={13} color="var(--sidebar-text)" />
          <input
            type="text"
            placeholder="Search runs…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Nav */}
      <nav className="sidebar-nav">
        <div className="sidebar-section-label">Main</div>
        {NAV_MAIN.map(n => <NavItem key={n.href} {...n} />)}
        <div className="sidebar-section-label">Account</div>
        {NAV_ACCOUNT.map(n => <NavItem key={n.href} {...n} />)}
      </nav>

      {/* Projects */}
      <div className="sidebar-projects">
        <div className="sidebar-section-header">
          <span className="sidebar-section-label">Projects</span>
          <Link href="/runs/new" className="sidebar-new-icon-btn" title="New project" aria-label="New project">
            <Plus size={12} />
          </Link>
        </div>
        {projects.map(proj => {
          const active = pathname.startsWith(`/projects/${proj.id}`);
          return (
            <Link
              key={proj.id}
              href={`/projects/${proj.id}`}
              className={`sidebar-project-item${active ? ' active' : ''}`}
              title={collapsed ? proj.name : undefined}
            >
              <span className="sidebar-project-icon" style={{ background: proj.color }}>{proj.icon}</span>
              <span className="sidebar-project-name">{proj.name}</span>
              {proj.run_count > 0 && (
                <span className="sidebar-project-badge">{proj.run_count}</span>
              )}
            </Link>
          );
        })}
      </div>

      {/* Run history */}
      <div className="sidebar-history">
        {filteredRuns.length > 0 && (
          <>
            {GROUP_ORDER.map(group => {
              const items = grouped[group];
              if (!items?.length) return null;
              return (
                <div key={group}>
                  <div className="sidebar-history-group-label">{group}</div>
                  {items.map(run => {
                    const active = pathname.includes(run.id);
                    const relTime = run.created_at
                      ? formatDistanceToNow(new Date(run.created_at), { addSuffix: false })
                      : '';
                    return (
                      <Link
                        key={run.id}
                        href={`/runs/${run.id}`}
                        className={`sidebar-history-item${active ? ' active' : ''}`}
                      >
                        <div className="sidebar-history-dot" />
                        <div className="sidebar-history-text">
                          <div className="sidebar-history-topic" title={run.topic}>{run.topic}</div>
                        </div>
                        <div className="sidebar-history-time">{relTime}</div>
                      </Link>
                    );
                  })}
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Footer: user row */}
      <div className="sidebar-footer">
        <div className="sidebar-user-row">
          <div className="avatar-chip" style={{ width: 28, height: 28, fontSize: 12 }}>I</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">Account</div>
            <div className="sidebar-user-role">Owner</div>
          </div>
          <button
            type="button"
            className="sidebar-sign-out-btn"
            onClick={signOut}
            title="Sign out"
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
