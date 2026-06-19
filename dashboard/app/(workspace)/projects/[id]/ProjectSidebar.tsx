'use client';
import { useState } from 'react';
import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { ArrowLeft, Plus, Search, Folder, Circle, PlayCircle, BarChart2, Activity, Layout } from 'lucide-react';
import { useProjectRuns } from '@/hooks/useProjectRuns';
import type { Project } from '@/hooks/useProjects';

interface Props {
  project: Project;
  activeRunId?: string;
  onNewChat: () => void;
}

const STATUS_COLOR: Record<string, string> = {
  completed: '#059669',
  running: '#6366F1',
  failed: '#DC2626',
  cancelled: '#94A3B8',
  pending: '#D97706',
  paused_for_review: '#D97706',
};

function truncateTopic(topic: string, max = 34): string {
  const clean = (topic || '').trim();
  return clean.length > max ? clean.slice(0, max) + '…' : clean;
}

export function ProjectSidebar({ project, activeRunId, onNewChat }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const { groups, loading } = useProjectRuns(project.id);
  const [search, setSearch] = useState('');

  const projectBase = `/projects/${project.id}`;
  const navLinks = [
    { href: `${projectBase}/runs`,      label: 'Runs',      icon: PlayCircle },
    { href: `${projectBase}/analytics`, label: 'Analytics', icon: BarChart2 },
    { href: `${projectBase}/usage`,     label: 'Usage',     icon: Activity },
    { href: `${projectBase}/templates`, label: 'Templates', icon: Layout },
  ];

  const filtered = search.trim()
    ? groups.map(g => ({
        ...g,
        runs: g.runs.filter(r =>
          (r.raw_topic || r.topic).toLowerCase().includes(search.toLowerCase())
        ),
      })).filter(g => g.runs.length > 0)
    : groups;

  return (
    <aside className="project-sidebar">
      {/* Top: back + logo */}
      <div className="project-sidebar-back-row">
        <Link href="/projects" className="project-sidebar-back-link">
          <ArrowLeft size={14} />
          <span>Projects</span>
        </Link>
      </div>

      {/* Project header */}
      <div className="project-sidebar-project-header">
        <span className="project-sidebar-project-icon"><Folder size={18} /></span>
        <div className="project-sidebar-project-meta">
          <div className="project-sidebar-project-name">{project.name}</div>
          {project.memory_enabled && (
            <div className="project-sidebar-memory-badge">🧠 Memory on</div>
          )}
        </div>
      </div>

      {/* New chat */}
      <div className="project-sidebar-new-chat-wrap">
        <button className="project-sidebar-new-chat" onClick={onNewChat}>
          <Plus size={14} />
          <span>New Chat</span>
        </button>
      </div>

      {/* Search */}
      <div className="project-sidebar-search-wrap">
        <Search size={13} className="project-sidebar-search-icon" />
        <input
          className="project-sidebar-search"
          placeholder="Search chats…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Run history */}
      <div className="project-sidebar-history">
        {loading ? (
          <div className="project-sidebar-history-loading">
            <span className="skeleton skeleton-text" style={{ width: '80%', margin: '8px 0' }} />
            <span className="skeleton skeleton-text" style={{ width: '65%', margin: '4px 0' }} />
            <span className="skeleton skeleton-text" style={{ width: '72%', margin: '4px 0' }} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="project-sidebar-history-empty">
            {search ? 'No matching chats' : 'No chats yet — start one above'}
          </div>
        ) : (
          filtered.map(group => (
            <div key={group.label}>
              <div className="project-sidebar-group-label">{group.label}</div>
              {group.runs.map(run => {
                const isActive = run.id === activeRunId;
                const dotColor = STATUS_COLOR[run.overall_status] ?? '#94A3B8';
                const displayTopic = run.raw_topic || run.topic;
                return (
                  <button
                    key={run.id}
                    className={`project-sidebar-run-item${isActive ? ' project-sidebar-run-item--active' : ''}`}
                    onClick={() => router.push(`/projects/${project.id}?run=${run.id}`)}
                  >
                    <Circle
                      size={7}
                      style={{ fill: dotColor, color: dotColor, flexShrink: 0, marginTop: 2 }}
                    />
                    <span className="project-sidebar-run-topic">
                      {truncateTopic(displayTopic)}
                    </span>
                  </button>
                );
              })}
            </div>
          ))
        )}
      </div>

      {/* Bottom nav — project-scoped links */}
      <div className="project-sidebar-bottom">
        {navLinks.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + '/');
          return (
            <Link
              key={href}
              href={href}
              className={`project-sidebar-nav-link${active ? ' project-sidebar-nav-link--active' : ''}`}
            >
              <Icon size={15} />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
