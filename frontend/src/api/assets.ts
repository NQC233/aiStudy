export interface AssetListItem {
  id: string;
  title: string;
  authors: string[];
  source_type: string;
  status: string;
  created_at: string;
}

export interface AssetDetail {
  id: string;
  user_id: string;
  title: string;
  authors: string[];
  abstract: string | null;
  source_type: string;
  language: string;
  status: string;
  parse_error_message: string | null;
  created_at: string;
  updated_at: string;
  basic_resources: {
    parse_status: string;
    kb_status: string;
    mindmap_status: string;
  };
  enhanced_resources: {
    slides_status: string;
    anki_status: string;
    quiz_status: string;
  };
}

export interface AssetDeleteResponse {
  asset_id: string;
  deleted: boolean;
  deleted_oss_count: number;
  failed_oss_count: number;
  warning: string | null;
}

export interface AssetPdfDescriptor {
  asset_id: string;
  file_id: string;
  file_type: string;
  mime_type: string;
  size: number;
  url: string;
}

export interface AssetUploadResponse {
  asset: AssetDetail;
  uploaded_file_id: string;
  uploaded_file_url: string;
}

export interface AssetParseStatusResponse {
  asset_id: string;
  asset_status: string;
  parse_status: string;
  error_message: string | null;
  latest_parse: {
    id: string;
    asset_id: string;
    provider: string;
    parse_version: string;
    status: string;
    markdown_storage_key: string | null;
    json_storage_key: string | null;
    raw_response_storage_key: string | null;
    error_code: string | null;
    retryable: boolean | null;
    attempt: number | null;
    max_retries: number | null;
    next_retry_eta: string | null;
    task: {
      task_id: string | null;
      data_id: string | null;
      state: string | null;
      trace_id: string | null;
      full_zip_url: string | null;
      err_msg: string | null;
      progress: {
        extracted_pages: number | null;
        total_pages: number | null;
        start_time: string | null;
      } | null;
    };
    created_at: string;
    updated_at: string;
  } | null;
}

export interface AssetParseRetryResponse {
  asset_id: string;
  parse_status: string;
  message: string;
}

export interface MindmapNodeItem {
  id: string;
  parent_id: string | null;
  node_key: string;
  parent_key: string | null;
  title: string;
  summary: string | null;
  level: number;
  order: number;
  page_no: number | null;
  paragraph_ref: string | null;
  section_path: string[];
  block_ids: string[];
  selector_payload: Record<string, unknown>;
  node_type: string;
  stage: string | null;
}

export interface MindmapSnapshot {
  id: string;
  asset_id: string;
  version: number;
  status: string;
  root_node_key: string | null;
  meta: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  nodes: MindmapNodeItem[];
}

export interface AssetMindmapResponse {
  asset_id: string;
  mindmap_status: string;
  mindmap: MindmapSnapshot | null;
}

export interface AssetMindmapRebuildResponse {
  asset_id: string;
  mindmap_status: string;
  message: string;
}

export interface AssetSlidesRebuildResponse {
  asset_id: string;
  slides_status: string;
  schema_version: string | null;
  runtime_bundle?: SlidesRuntimeBundle | null;
}

export interface ParsedDocumentPage {
  page_id: string;
  page_no: number;
  source_page_idx: number;
  width: number | null;
  height: number | null;
  blocks: string[];
}

export interface ParsedDocumentSection {
  section_id: string;
  title: string;
  level: number;
  parent_id: string | null;
  page_start: number;
  page_end: number;
  block_ids: string[];
}

export interface ParsedDocumentBlock {
  block_id: string;
  type: string;
  page_no: number;
  source_page_idx: number;
  order: number;
  section_id: string;
  bbox: number[] | null;
  text: string | null;
  text_level: number | null;
  paragraph_no: number | null;
  anchor: Record<string, unknown>;
  source_refs: Record<string, unknown>;
  resource_ref: string | null;
  metadata: Record<string, unknown>;
}

export interface ParsedDocumentTocItem {
  section_id: string;
  title: string;
  level: number;
  page_start: number;
}

export interface ParsedDocumentPayload {
  schema_version: string;
  asset_id: string;
  parse_id: string;
  provider: Record<string, unknown>;
  document: Record<string, unknown>;
  pages: ParsedDocumentPage[];
  sections: ParsedDocumentSection[];
  blocks: ParsedDocumentBlock[];
  assets: {
    images: Record<string, unknown>[];
    tables: Record<string, unknown>[];
  };
  reading_order: string[];
  toc: ParsedDocumentTocItem[];
  stats: Record<string, unknown>;
}

export interface AssetParsedDocumentResponse {
  asset_id: string;
  parse_status: string;
  parse_id: string | null;
  parsed_json: ParsedDocumentPayload | null;
}

export interface AnchorPreviewRequest {
  page_no: number;
  selected_text: string;
  block_id?: string | null;
  paragraph_no?: number | null;
  selector_type?: string;
  selector_payload?: Record<string, unknown>;
}

export interface AnchorPreviewResponse {
  asset_id: string;
  page_no: number;
  block_id: string;
  paragraph_no: number | null;
  selected_text: string;
  selector_type: string;
  selector_payload: Record<string, unknown>;
}

export type NoteAnchorType = 'text_selection' | 'mindmap_node' | 'knowledge_point';

export interface NoteAnchorPayload {
  anchor_type: NoteAnchorType;
  page_no?: number | null;
  block_id?: string | null;
  paragraph_no?: number | null;
  selected_text?: string | null;
  selector_type?: string | null;
  selector_payload?: Record<string, unknown>;
}

export interface CreateNoteRequest {
  anchor: NoteAnchorPayload;
  title?: string | null;
  content: string;
}

export interface UpdateNoteRequest {
  title?: string | null;
  content?: string | null;
}

export interface NoteAnchorItem {
  id: string;
  anchor_type: NoteAnchorType;
  page_no: number | null;
  block_id: string | null;
  paragraph_no: number | null;
  selected_text: string | null;
  selector_type: string;
  selector_payload: Record<string, unknown>;
  created_at: string;
}

export interface NoteItem {
  id: string;
  asset_id: string;
  user_id: string;
  title: string | null;
  content: string;
  anchor: NoteAnchorItem;
  created_at: string;
  updated_at: string;
}

export interface NoteListResponse {
  asset_id: string;
  total: number;
  anchor_type: NoteAnchorType | null;
  notes: NoteItem[];
}

export interface NoteDeleteResponse {
  note_id: string;
  deleted: boolean;
}

export interface ChatSessionItem {
  id: string;
  asset_id: string;
  user_id: string;
  title: string;
  message_count: number;
  created_at: string;
}

export interface ChatCitationItem {
  citation_id: string;
  chunk_id: string;
  score: number;
  page_start: number | null;
  page_end: number | null;
  paragraph_start: number | null;
  paragraph_end: number | null;
  section_path: string[];
  block_ids: string[];
  quote_text: string;
}

export interface ChatMessageItem {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | string;
  message_type: string;
  content: string;
  selection_anchor_payload: Record<string, unknown> | null;
  citations: ChatCitationItem[];
  created_at: string;
}

export interface ChatSessionMessagesResponse {
  session_id: string;
  asset_id: string;
  messages: ChatMessageItem[];
}

export interface ChatSessionMessageRequest {
  question: string;
  selected_anchor?: {
    page_no: number;
    block_id?: string | null;
    paragraph_no?: number | null;
    selected_text?: string;
    selector_type?: string;
    selector_payload?: Record<string, unknown>;
  };
  top_k?: number;
  rewrite_query?: boolean;
  strategy?: 's0' | 's1' | 's2' | 's3';
}

export interface ChatSessionMessageResponse {
  session_id: string;
  question_message_id: string;
  answer_message_id: string;
  answer: string;
  citations: ChatCitationItem[];
}

export interface SlideDslCitation {
  page_no: number;
  block_ids: string[];
  quote: string;
}

export interface SlideDslBlock {
  block_type: string;
  content: string;
  items: string[];
  svg_content?: string | null;
  meta?: Record<string, unknown>;
}

export interface SlideDslPage {
  slide_key: string;
  stage: string;
  page_type: string;
  layout_hint: string;
  director_source: 'rule' | 'llm';
  visual_tone: 'editorial' | 'technical' | 'spotlight' | 'warm';
  template_type: string;
  animation_preset: string;
  blocks: SlideDslBlock[];
  citations: SlideDslCitation[];
}

export interface SlidesDslPayload {
  schema_version: '2';
  asset_id: string;
  version: number;
  generated_at: string;
  pages: SlideDslPage[];
}

export interface SlideMustPassIssue {
  page_index: number;
  field: string;
  code: string;
  message: string;
}

export interface SlideMustPassReport {
  passed: boolean;
  issues: SlideMustPassIssue[];
}

export interface SlidePageQualityScore {
  page_index: number;
  slide_key: string;
  score: number;
  reasons: string[];
}

export interface SlideQualityReport {
  overall_score: number;
  page_scores: SlidePageQualityScore[];
  low_quality_pages: number[];
}

export interface SlideFixLog {
  page_index: number;
  slide_key: string;
  before_score: number;
  after_score: number;
  reason: string;
}

export interface SlideGenerationMeta {
  requested_strategy: 'template' | 'llm';
  applied_strategy: 'template' | 'llm';
  fallback_used: boolean;
  fallback_reason: string | null;
}

export interface SlideShadowReport {
  enabled: boolean;
  target_strategy: 'llm';
  status: 'skipped' | 'completed' | 'failed';
  skip_reason: string | null;
  error_message: string | null;
  candidate_overall_score: number | null;
  baseline_overall_score: number | null;
  score_delta: number | null;
}

export interface SlideTtsManifestItem {
  slide_key: string;
  audio_url: string | null;
  duration_ms: number | null;
  status: 'pending' | 'processing' | 'ready' | 'failed';
  error_message: string | null;
  retry_meta?: {
    attempt?: number;
    max_retries?: number;
    next_retry_eta?: string;
    auto_retry_pending?: boolean;
    error_code?: string;
  } | null;
}

export interface SlideTtsManifest {
  pages: SlideTtsManifestItem[];
}

export interface SlideCueItem {
  block_id: string;
  start_ms: number;
  end_ms: number;
  animation: string;
}

export interface SlidePlaybackPagePlan {
  slide_key: string;
  start_ms: number;
  end_ms: number;
  duration_ms: number;
  cues: SlideCueItem[];
}

export interface SlidePlaybackPlan {
  total_duration_ms: number;
  pages: SlidePlaybackPagePlan[];
}

export interface RuntimeRenderedPage {
  page_id: string;
  html: string;
  css: string;
  asset_refs: Record<string, unknown>[];
  render_meta: Record<string, unknown>;
}

export interface SlidesRuntimeBundle {
  page_count: number;
  pages: RuntimeRenderedPage[];
}

export interface AssetSlidesResponse {
  asset_id: string;
  slides_status: string;
  schema_version: string | null;
  rebuilding: boolean;
  rebuild_reason: string | null;
  tts_status: 'not_generated' | 'processing' | 'ready' | 'failed' | 'partial';
  playback_status: 'not_ready' | 'ready';
  auto_page_supported: boolean;
  slides_dsl: SlidesDslPayload | null;
  runtime_bundle?: SlidesRuntimeBundle | null;
  must_pass_report: SlideMustPassReport | null;
  quality_report: SlideQualityReport | null;
  fix_logs: SlideFixLog[];
  generation_meta: SlideGenerationMeta;
  shadow_report: SlideShadowReport;
  tts_manifest: SlideTtsManifest;
  playback_plan: SlidePlaybackPlan;
}

export interface AssetSlideTtsEnsureRequest {
  page_index: number;
  prefetch_next?: boolean;
}

export interface AssetSlideTtsEnsureResponse {
  asset_id: string;
  page_index: number;
  enqueued_slide_keys: string[];
  tts_status: 'not_generated' | 'processing' | 'ready' | 'failed' | 'partial';
  message: string;
}

export interface AssetSlideTtsRetryNextRequest {
  current_page_index: number;
}

export interface AssetSlideTtsRetryNextResponse {
  asset_id: string;
  current_page_index: number;
  next_slide_key: string | null;
  enqueued_slide_keys: string[];
  tts_status: 'not_generated' | 'processing' | 'ready' | 'failed' | 'partial';
  message: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const DEFAULT_REQUEST_TIMEOUT_MS = 10000;
const UPLOAD_REQUEST_TIMEOUT_MS = 180000;
const PARSED_JSON_REQUEST_TIMEOUT_MS = 30000;

async function requestWithTimeout(input: RequestInfo | URL, init?: RequestInit, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => {
    controller.abort();
  }, timeoutMs);

  try {
    return await fetch(input, {
      ...init,
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('请求超时，请检查后端服务或资源地址。');
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

async function parseErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    // ignore
  }

  try {
    const text = (await response.text()).trim();
    if (text) {
      return text;
    }
  } catch {
    // ignore
  }

  return fallback;
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
  }

  return response.json() as Promise<T>;
}


async function postJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
  }

  return response.json() as Promise<T>;
}


async function patchJson<T>(path: string, payload: unknown): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
  }

  return response.json() as Promise<T>;
}


async function deleteJson<T>(path: string): Promise<T> {
  const response = await requestWithTimeout(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
  }

  return response.json() as Promise<T>;
}


export function fetchAssets(): Promise<AssetListItem[]> {
  return requestJson<AssetListItem[]>('/api/assets');
}


export function fetchAssetDetail(assetId: string): Promise<AssetDetail> {
  return requestJson<AssetDetail>(`/api/assets/${assetId}`);
}

export function deleteAsset(assetId: string): Promise<AssetDeleteResponse> {
  return deleteJson<AssetDeleteResponse>(`/api/assets/${assetId}`);
}


export function fetchAssetPdfMeta(assetId: string): Promise<AssetPdfDescriptor> {
  return requestJson<AssetPdfDescriptor>(`/api/assets/${assetId}/pdf-meta`);
}


export function getAssetPdfUrl(assetId: string): string {
  return `${API_BASE_URL}/api/assets/${assetId}/pdf`;
}


export function fetchAssetParseStatus(assetId: string): Promise<AssetParseStatusResponse> {
  return requestJson<AssetParseStatusResponse>(`/api/assets/${assetId}/status`);
}


export function fetchAssetParsedDocument(assetId: string): Promise<AssetParsedDocumentResponse> {
  return (async () => {
    const path = `/api/assets/${assetId}/parsed-json`;
    const attemptFetch = async (timeoutMs: number): Promise<AssetParsedDocumentResponse> => {
      const response = await requestWithTimeout(`${API_BASE_URL}${path}`, undefined, timeoutMs);
      if (!response.ok) {
        throw new Error(await parseErrorMessage(response, `请求失败：${response.status}`));
      }
      return response.json() as Promise<AssetParsedDocumentResponse>;
    };

    try {
      return await attemptFetch(PARSED_JSON_REQUEST_TIMEOUT_MS);
    } catch (error) {
      const message = error instanceof Error ? error.message : '';
      if (!message.includes('请求超时')) {
        throw error;
      }
      return attemptFetch(PARSED_JSON_REQUEST_TIMEOUT_MS + 15000);
    }
  })();
}


export async function uploadAsset(file: File, title?: string): Promise<AssetUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  if (title && title.trim()) {
    formData.append('title', title.trim());
  }

  const response = await requestWithTimeout(
    `${API_BASE_URL}/api/assets/upload`,
    {
      method: 'POST',
      body: formData,
    },
    UPLOAD_REQUEST_TIMEOUT_MS,
  );

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `上传失败：${response.status}`));
  }

  return response.json() as Promise<AssetUploadResponse>;
}


export async function retryAssetParse(assetId: string): Promise<AssetParseRetryResponse> {
  const response = await requestWithTimeout(`${API_BASE_URL}/api/assets/${assetId}/parse/retry`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `重试解析失败：${response.status}`));
  }

  return response.json() as Promise<AssetParseRetryResponse>;
}


export function fetchAssetMindmap(assetId: string): Promise<AssetMindmapResponse> {
  return requestJson<AssetMindmapResponse>(`/api/assets/${assetId}/mindmap`);
}


export async function rebuildAssetMindmap(assetId: string): Promise<AssetMindmapRebuildResponse> {
  const response = await requestWithTimeout(`${API_BASE_URL}/api/assets/${assetId}/mindmap/rebuild`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, `重建导图失败：${response.status}`));
  }

  return response.json() as Promise<AssetMindmapRebuildResponse>;
}


export function previewAnchor(assetId: string, payload: AnchorPreviewRequest): Promise<AnchorPreviewResponse> {
  return postJson<AnchorPreviewResponse>(`/api/assets/${assetId}/anchor-preview`, payload);
}


export function createAssetNote(assetId: string, payload: CreateNoteRequest): Promise<NoteItem> {
  return postJson<NoteItem>(`/api/assets/${assetId}/notes`, payload);
}


export function fetchAssetNotes(assetId: string, anchorType?: NoteAnchorType): Promise<NoteListResponse> {
  const query = anchorType ? `?anchor_type=${encodeURIComponent(anchorType)}` : '';
  return requestJson<NoteListResponse>(`/api/assets/${assetId}/notes${query}`);
}


export function updateNote(noteId: string, payload: UpdateNoteRequest): Promise<NoteItem> {
  return patchJson<NoteItem>(`/api/notes/${noteId}`, payload);
}


export function deleteNote(noteId: string): Promise<NoteDeleteResponse> {
  return deleteJson<NoteDeleteResponse>(`/api/notes/${noteId}`);
}


export function createAssetChatSession(assetId: string, title?: string): Promise<ChatSessionItem> {
  return postJson<ChatSessionItem>(`/api/assets/${assetId}/chat/sessions`, {
    title: title?.trim() || null,
  });
}


export function fetchAssetChatSessions(assetId: string): Promise<ChatSessionItem[]> {
  return requestJson<ChatSessionItem[]>(`/api/assets/${assetId}/chat/sessions`);
}


export function fetchChatSessionMessages(sessionId: string): Promise<ChatSessionMessagesResponse> {
  return requestJson<ChatSessionMessagesResponse>(`/api/chat/sessions/${sessionId}/messages`);
}


export function sendChatSessionMessage(
  sessionId: string,
  payload: ChatSessionMessageRequest,
): Promise<ChatSessionMessageResponse> {
  return postJson<ChatSessionMessageResponse>(`/api/chat/sessions/${sessionId}/messages`, payload);
}

export function fetchAssetSlides(assetId: string): Promise<AssetSlidesResponse> {
  return requestJson<AssetSlidesResponse>(`/api/assets/${assetId}/slides`);
}

export function rebuildAssetSlides(assetId: string): Promise<AssetSlidesRebuildResponse> {
  return postJson<AssetSlidesRebuildResponse>(`/api/assets/${assetId}/slides/runtime-bundle/rebuild`, {});
}

export function ensureAssetSlideTts(
  assetId: string,
  payload: AssetSlideTtsEnsureRequest,
): Promise<AssetSlideTtsEnsureResponse> {
  return postJson<AssetSlideTtsEnsureResponse>(`/api/assets/${assetId}/slides/tts/ensure`, payload);
}

export function retryNextAssetSlideTts(
  assetId: string,
  payload: AssetSlideTtsRetryNextRequest,
): Promise<AssetSlideTtsRetryNextResponse> {
  return postJson<AssetSlideTtsRetryNextResponse>(`/api/assets/${assetId}/slides/tts/retry-next`, payload);
}
