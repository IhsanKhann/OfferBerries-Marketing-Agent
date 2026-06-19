'use client';
import { useRouter } from 'next/navigation';
import { ArrowRight, MessageSquare, Brain, FolderOpen } from 'lucide-react';
import type { Project } from '@/hooks/useProjects';

function timeAgo(iso?: string): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

export function ProjectCard({ project }: { project: Project }) {
  const router = useRouter();

  return (
    <div
      className="project-card"
      onClick={() => router.push(`/projects/${project.id}`)}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && router.push(`/projects/${project.id}`)}
    >
      <div className="project-card-color-bar" style={{ background: project.color }} />
      <div className="project-card-body">
        <div className="project-card-icon-row">
          <span className="project-card-icon"><FolderOpen size={28} style={{ color: project.color }} /></span>
          <ArrowRight size={14} className="project-card-arrow" />
        </div>
        <h3 className="project-card-name">{project.name}</h3>
        {project.description && (
          <p className="project-card-desc">{project.description}</p>
        )}
      </div>
      <div className="project-card-footer">
        <span className="project-card-badge">
          <MessageSquare size={12} />
          {project.run_count} {project.run_count === 1 ? 'chat' : 'chats'}
        </span>
        {project.memory_enabled && (
          <span className="project-card-memory-badge">
            <Brain size={12} />
            Memory
          </span>
        )}
        {project.created_at && (
          <span className="project-card-date">{timeAgo(project.created_at)}</span>
        )}
      </div>
    </div>
  );
}
