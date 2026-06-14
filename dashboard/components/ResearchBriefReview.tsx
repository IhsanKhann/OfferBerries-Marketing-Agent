'use client';
import { useState, useCallback } from 'react';
import { GripVertical, Trash2, Plus, CheckCircle, RefreshCw, Edit3 } from 'lucide-react';

export interface ResearchBrief {
  topic: string;
  trending_angles: string[];
  pain_points: string[];
  suggested_hooks: string[];
  platform_notes: Record<string, string>;
  generated_at: string;
}

interface Props {
  brief: ResearchBrief;
  runId: string;
  stage?: string;
  onApprove: (edited: ResearchBrief) => void;
  onReject: () => void;
  approving?: boolean;
}

type ListKey = 'trending_angles' | 'pain_points' | 'suggested_hooks';

const LIST_META: Record<ListKey, { label: string; placeholder: string }> = {
  trending_angles: { label: 'Trending Angles', placeholder: 'Add a trend angle…' },
  pain_points:     { label: 'Pain Points',     placeholder: 'Add a pain point…' },
  suggested_hooks: { label: 'Suggested Hooks', placeholder: 'Add a hook…' },
};

function DraggableList({
  items,
  onChange,
  placeholder,
}: {
  items: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [dragging, setDragging] = useState<number | null>(null);
  const [newItem, setNewItem] = useState('');

  function onDragStart(idx: number) {
    setDragging(idx);
  }

  function onDragOver(e: React.DragEvent, idx: number) {
    e.preventDefault();
    if (dragging === null || dragging === idx) return;
    const next = [...items];
    const [removed] = next.splice(dragging, 1);
    next.splice(idx, 0, removed);
    onChange(next);
    setDragging(idx);
  }

  function addItem() {
    const trimmed = newItem.trim();
    if (!trimmed) return;
    onChange([...items, trimmed]);
    setNewItem('');
  }

  function removeItem(idx: number) {
    onChange(items.filter((_, i) => i !== idx));
  }

  function updateItem(idx: number, value: string) {
    const next = [...items];
    next[idx] = value;
    onChange(next);
  }

  return (
    <div>
      {items.map((item, idx) => (
        <div
          key={idx}
          draggable
          onDragStart={() => onDragStart(idx)}
          onDragOver={e => onDragOver(e, idx)}
          onDragEnd={() => setDragging(null)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 8px',
            marginBottom: 4,
            borderRadius: 6,
            background: dragging === idx ? 'var(--surface-raised)' : 'var(--surface)',
            border: '1px solid var(--border)',
            cursor: 'grab',
            opacity: dragging === idx ? 0.5 : 1,
          }}
        >
          <GripVertical size={12} color="var(--text-muted)" style={{ flexShrink: 0 }} />
          <input
            type="text"
            value={item}
            onChange={e => updateItem(idx, e.target.value)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              fontSize: 13,
              color: 'var(--text-primary)',
            }}
          />
          <button
            type="button"
            onClick={() => removeItem(idx)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, color: 'var(--text-muted)' }}
          >
            <Trash2 size={12} />
          </button>
        </div>
      ))}

      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        <input
          type="text"
          value={newItem}
          onChange={e => setNewItem(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addItem(); } }}
          placeholder={placeholder}
          style={{
            flex: 1,
            padding: '6px 8px',
            borderRadius: 6,
            border: '1px dashed var(--border)',
            background: 'transparent',
            fontSize: 13,
            color: 'var(--text-primary)',
            outline: 'none',
          }}
        />
        <button
          type="button"
          onClick={addItem}
          className="btn btn-secondary btn-sm"
          style={{ padding: '4px 8px' }}
        >
          <Plus size={12} />
        </button>
      </div>
    </div>
  );
}

export default function ResearchBriefReview({
  brief: initialBrief,
  runId,
  stage = 'research',
  onApprove,
  onReject,
  approving,
}: Props) {
  const [brief, setBrief] = useState<ResearchBrief>(initialBrief);
  const [customAngle, setCustomAngle] = useState('');
  const [editingTopic, setEditingTopic] = useState(false);

  function updateList(key: ListKey, next: string[]) {
    setBrief(b => ({ ...b, [key]: next }));
  }

  function addCustomAngle() {
    const trimmed = customAngle.trim();
    if (!trimmed) return;
    setBrief(b => ({ ...b, trending_angles: [...b.trending_angles, trimmed] }));
    setCustomAngle('');
  }

  return (
    <div className="research-brief-review">
      {/* Header */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Research Brief</h3>
          <span className="badge badge-muted" style={{ fontSize: 11 }}>
            {new Date(brief.generated_at).toLocaleTimeString()}
          </span>
        </div>
        {editingTopic ? (
          <input
            autoFocus
            type="text"
            value={brief.topic}
            onChange={e => setBrief(b => ({ ...b, topic: e.target.value }))}
            onBlur={() => setEditingTopic(false)}
            onKeyDown={e => { if (e.key === 'Enter') setEditingTopic(false); }}
            style={{
              fontSize: 13,
              color: 'var(--text-muted)',
              background: 'var(--surface-raised)',
              border: '1px solid var(--accent)',
              borderRadius: 4,
              padding: '2px 6px',
              outline: 'none',
              width: '100%',
            }}
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditingTopic(true)}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              color: 'var(--text-muted)',
              fontSize: 13,
            }}
          >
            {brief.topic}
            <Edit3 size={11} />
          </button>
        )}
      </div>

      {/* Lists */}
      {(Object.keys(LIST_META) as ListKey[]).map(key => (
        <div key={key} style={{ marginBottom: 16 }}>
          <label className="form-label" style={{ marginBottom: 6 }}>
            {LIST_META[key].label}
            <span style={{ marginLeft: 6, color: 'var(--text-muted)', fontWeight: 400 }}>
              ({brief[key].length})
            </span>
          </label>
          <DraggableList
            items={brief[key]}
            onChange={next => updateList(key, next)}
            placeholder={LIST_META[key].placeholder}
          />
        </div>
      ))}

      {/* Add custom angle shortcut */}
      <div style={{ marginBottom: 20 }}>
        <label className="form-label">Add Custom Angle</label>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="text"
            className="input"
            placeholder="Specific angle you want covered…"
            value={customAngle}
            onChange={e => setCustomAngle(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomAngle(); } }}
          />
          <button
            type="button"
            onClick={addCustomAngle}
            className="btn btn-secondary btn-sm"
          >
            <Plus size={13} /> Add
          </button>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="button"
          onClick={() => onApprove(brief)}
          disabled={approving}
          className="btn btn-primary"
          style={{ flex: 1, gap: 6 }}
        >
          <CheckCircle size={14} />
          {approving ? 'Approving…' : 'Approve & Continue'}
        </button>
        <button
          type="button"
          onClick={onReject}
          className="btn btn-secondary"
          style={{ gap: 6 }}
        >
          <RefreshCw size={14} />
          Redo Research
        </button>
      </div>
    </div>
  );
}
