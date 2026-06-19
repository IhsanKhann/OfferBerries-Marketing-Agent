'use client';
import { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { useRouter } from 'next/navigation';
import { ProjectSidebar } from '../ProjectSidebar';
import type { Project } from '@/hooks/useProjects';

interface ProjectContextValue {
  project: Project;
}

export const ProjectContext = createContext<ProjectContextValue | null>(null);

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error('useProject must be used inside ProjectFrame');
  return ctx;
}

interface Props {
  projectId: string;
  activeRunId?: string;
  children: React.ReactNode;
  onNewChat?: () => void;
}

export function ProjectFrame({ projectId, activeRunId, children, onNewChat }: Props) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/proxy/projects/${projectId}`)
      .then(r => r.ok ? r.json() : null)
      .then(setProject)
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleNewChat = useCallback(() => {
    if (onNewChat) {
      onNewChat();
    } else {
      router.push(`/projects/${projectId}`);
    }
  }, [onNewChat, router, projectId]);

  if (loading) {
    return (
      <div className="workspace-shell">
        <div className="workspace-sidebar-skeleton">
          <div className="skeleton skeleton-title" style={{ margin: '20px 16px' }} />
          <div className="skeleton skeleton-text" style={{ margin: '8px 16px' }} />
          <div className="skeleton skeleton-text" style={{ margin: '8px 16px', width: '60%' }} />
        </div>
        <div className="workspace-main">
          <div className="workspace-loading-center">
            <span className="workspace-loader-dot workspace-loader-dot--lg" />
          </div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="workspace-shell">
        <div className="workspace-main workspace-error">
          <p>Project not found.</p>
          <button className="btn-primary" onClick={() => router.push('/projects')}>
            Back to projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <ProjectContext.Provider value={{ project }}>
      <div className="workspace-shell">
        <ProjectSidebar
          project={project}
          activeRunId={activeRunId}
          onNewChat={handleNewChat}
        />
        <div className="workspace-main">
          {children}
        </div>
      </div>
    </ProjectContext.Provider>
  );
}
