'use client';
import { useState, useEffect, useCallback } from 'react';

export interface Project {
  id: string;
  name: string;
  description?: string;
  brand_voice?: string;
  default_platforms: string[];
  default_model?: string;
  color: string;
  icon: string;
  starred?: boolean;
  memory_enabled: boolean;
  run_count: number;
  created_at?: string;
}

export interface CreateProjectInput {
  name: string;
  description?: string;
  brand_voice?: string;
  default_platforms?: string[];
  default_model?: string;
  color?: string;
  icon?: string;
  memory_enabled?: boolean;
}

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = useCallback(async () => {
    try {
      const res = await fetch('/api/proxy/projects');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setProjects(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const createProject = useCallback(async (input: CreateProjectInput): Promise<Project> => {
    // Optimistic insert
    const tempId = `temp-${Date.now()}`;
    const optimistic: Project = {
      id: tempId,
      name: input.name,
      description: input.description,
      brand_voice: input.brand_voice,
      default_platforms: input.default_platforms ?? ['linkedin', 'instagram'],
      default_model: input.default_model ?? 'sonar-pro',
      color: input.color ?? '#6366F1',
      icon: input.icon ?? '📁',
      memory_enabled: input.memory_enabled ?? true,
      run_count: 0,
    };
    setProjects(prev => [...prev, optimistic]);

    try {
      const res = await fetch('/api/proxy/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const created: Project = await res.json();
      // Replace optimistic entry with real one
      setProjects(prev => prev.map(p => p.id === tempId ? created : p));
      return created;
    } catch (err) {
      // Roll back optimistic update
      setProjects(prev => prev.filter(p => p.id !== tempId));
      throw err;
    }
  }, []);

  return { projects, loading, error, createProject, refetch: fetchProjects };
}
