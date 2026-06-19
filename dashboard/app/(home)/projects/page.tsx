'use client';
import { useState } from 'react';
import { Plus, Folder } from 'lucide-react';
import { useProjects } from '@/hooks/useProjects';
import { ProjectCard } from './ProjectCard';
import { CreateProjectModal } from './CreateProjectModal';

function ProjectCardSkeleton() {
  return (
    <div className="project-card project-card--skeleton">
      <div className="project-card-color-bar skeleton" />
      <div className="project-card-body">
        <div className="skeleton skeleton-icon" />
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-text" />
        <div className="skeleton skeleton-text" style={{ width: '60%' }} />
      </div>
      <div className="project-card-footer">
        <div className="skeleton skeleton-badge" />
        <div className="skeleton skeleton-badge" />
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  const { projects, loading, createProject, refetch } = useProjects();
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <div className="projects-page">
      <div className="projects-page-header">
        <div>
          <h1 className="projects-page-title">Projects</h1>
          <p className="projects-page-sub">
            Your marketing campaigns and content workspaces
          </p>
        </div>
        <button className="btn-primary" onClick={() => setModalOpen(true)}>
          <Plus size={16} />
          New Project
        </button>
      </div>

      {loading ? (
        <div className="projects-gallery">
          {[1, 2, 3].map(i => <ProjectCardSkeleton key={i} />)}
        </div>
      ) : projects.length === 0 ? (
        <div className="projects-empty">
          <div className="projects-empty-icon">
            <Folder size={48} />
          </div>
          <h2 className="projects-empty-title">No projects yet</h2>
          <p className="projects-empty-desc">
            Create your first project to start generating marketing content
          </p>
          <button className="btn-primary" onClick={() => setModalOpen(true)}>
            <Plus size={16} />
            Create your first project
          </button>
        </div>
      ) : (
        <div className="projects-gallery">
          {projects.map(p => (
            <ProjectCard key={p.id} project={p} />
          ))}
          <button
            className="project-card project-card--new"
            onClick={() => setModalOpen(true)}
          >
            <div className="project-card-new-inner">
              <Plus size={24} className="project-card-new-icon" />
              <span className="project-card-new-label">New Project</span>
            </div>
          </button>
        </div>
      )}

      {modalOpen && (
        <CreateProjectModal
          onClose={() => setModalOpen(false)}
          onCreate={async input => {
            const project = await createProject(input);
            setModalOpen(false);
            refetch();
            return project;
          }}
        />
      )}
    </div>
  );
}
