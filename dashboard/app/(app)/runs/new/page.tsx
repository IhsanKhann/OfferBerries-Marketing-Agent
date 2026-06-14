'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import RunConfigurationForm, { type RunConfig } from '../../../../components/RunConfigurationForm';
import { notify } from '../../../../lib/toast';

export default function NewRunPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleSubmit(config: RunConfig) {
    setLoading(true);
    try {
      const resp = await fetch('/api/proxy/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      notify.success('Run started');
      router.push(`/runs/${data.run_id}`);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Failed to start run';
      notify.error(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-container" style={{ maxWidth: 640, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 24 }}>
        <Link href="/runs" style={{ color: 'var(--text-muted)', display: 'flex' }}>
          <ArrowLeft size={16} />
        </Link>
        <h1 className="page-title" style={{ margin: 0 }}>New Run</h1>
      </div>
      <div className="card">
        <RunConfigurationForm onSubmit={handleSubmit} loading={loading} />
      </div>
    </div>
  );
}
