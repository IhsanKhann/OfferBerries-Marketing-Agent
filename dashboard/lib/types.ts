export interface TenantSession {
  tenantId: string;
  tier: string;
  apiKey: string;
  authenticated: boolean;
}

export interface ResearchBrief {
  topic: string;
  trending_angles: string[];
  pain_points: string[];
  suggested_hooks: string[];
  platform_notes: Record<string, string>;
  generated_at?: string;
}

export interface PlatformContent {
  platform: string;
  copy: string;
  hashtags: string[];
  cta: string;
  estimated_reading_time: number;
  word_count: number;
}

export interface VisualAsset {
  path: string;
  url: string;
  format: string;
  width: number;
  height: number;
  source: string;
  template_id: string;
}

export interface QueuedPost {
  postiz_id: string;
  platform: string;
  scheduled_at: string;
  preview_url?: string;
  status?: string;
  caption?: string;
}

export interface AnalyticsReport {
  period_days: number;
  total_impressions: number;
  total_clicks: number;
  top_posts: PostPerformance[];
  platform_breakdown: Record<string, PlatformStats>;
  trend: 'up' | 'down' | 'flat';
  best_performing_template: string;
  best_performing_day: string;
  recommendations: string[];
}

export interface PostPerformance {
  postiz_id: string;
  platform: string;
  impressions: number;
  clicks: number;
  preview_url?: string;
}

export interface PlatformStats {
  impressions: number;
  clicks: number;
  engagement_rate: number;
}

export interface AgentRunStatus {
  status: 'started' | 'running' | 'completed' | 'failed';
  run_id: string;
  state?: {
    brief?: ResearchBrief;
    platform_content?: Record<string, PlatformContent>;
    visual_assets?: Record<string, VisualAsset>;
    queued_posts?: QueuedPost[];
    errors?: string[];
  };
  error?: string;
}
