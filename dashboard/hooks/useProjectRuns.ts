'use client';
import { useState, useEffect, useCallback } from 'react';

export interface ProjectRun {
  id: string;
  topic: string;
  raw_topic?: string;
  overall_status: string;
  created_at?: string;
}

function groupByDate(runs: ProjectRun[]): { label: string; runs: ProjectRun[] }[] {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 86400000;
  const weekStart = todayStart - 6 * 86400000;

  const groups: Record<string, ProjectRun[]> = {
    Today: [],
    Yesterday: [],
    'Last 7 days': [],
    Older: [],
  };

  for (const run of runs) {
    const t = run.created_at ? new Date(run.created_at).getTime() : 0;
    if (t >= todayStart) groups['Today'].push(run);
    else if (t >= yesterdayStart) groups['Yesterday'].push(run);
    else if (t >= weekStart) groups['Last 7 days'].push(run);
    else groups['Older'].push(run);
  }

  return Object.entries(groups)
    .filter(([, r]) => r.length > 0)
    .map(([label, runs]) => ({ label, runs }));
}

export function useProjectRuns(projectId: string) {
  const [runs, setRuns] = useState<ProjectRun[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch(`/api/proxy/runs?project_id=${projectId}&limit=50`);
      if (res.ok) {
        const data = await res.json();
        setRuns(Array.isArray(data) ? data : []);
      }
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { fetchRuns(); }, [fetchRuns]);

  const groups = groupByDate(runs);

  return { runs, groups, loading, refetch: fetchRuns };
}
