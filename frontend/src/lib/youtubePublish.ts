export type Privacy = "private" | "unlisted" | "public";

export type ChannelKind = "any" | "short" | "video";
export type PublishFormat = "auto" | "short" | "video";

export interface YouTubeAccount {
  channel_id: string;
  title?: string;
  subscribers?: string;
  thumbnail?: string;
  tag?: string;
  keywords?: string[];
  kind?: ChannelKind;
}

export interface YouTubeStatus {
  configured: boolean;
  connected: boolean;
  channel: { title?: string; subscribers?: string; thumbnail?: string } | null;
  accounts?: YouTubeAccount[];
}

export interface PublishSuggestion {
  format: "short" | "video";
  width: number;
  height: number;
  duration: number;
  ratio: string;
  channel_id: string;
  reason: string;
}

export const AUTO_PUBLISH_KEY = "lumen_auto_publish";
export const AUTO_PRIVACY_KEY = "lumen_auto_publish_privacy";

export function readAutoPublish(): { enabled: boolean; privacy: Privacy } {
  try {
    const enabled = localStorage.getItem(AUTO_PUBLISH_KEY) === "1";
    const p = localStorage.getItem(AUTO_PRIVACY_KEY) as Privacy | null;
    return { enabled, privacy: p === "public" || p === "unlisted" || p === "private" ? p : "private" };
  } catch {
    return { enabled: false, privacy: "private" };
  }
}

export function saveAutoPublish(enabled: boolean, privacy: Privacy) {
  try {
    localStorage.setItem(AUTO_PUBLISH_KEY, enabled ? "1" : "0");
    localStorage.setItem(AUTO_PRIVACY_KEY, privacy);
  } catch {
    /* almacenamiento no disponible */
  }
}

export async function fetchYouTubeStatus(): Promise<YouTubeStatus> {
  const res = await fetch("/api/publish/youtube/status");
  if (!res.ok) throw new Error("No se pudo consultar el estado de YouTube");
  return res.json();
}

export function connectYouTube() {
  window.location.href = "/api/publish/youtube/connect";
}

export async function disconnectYouTube(channelId?: string) {
  await fetch("/api/publish/youtube/disconnect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(channelId ? { channel_id: channelId } : {}),
  });
}

export async function updateYouTubeAccount(
  channelId: string,
  patch: { tag?: string; keywords?: string; kind?: ChannelKind },
): Promise<YouTubeAccount> {
  const res = await fetch("/api/publish/youtube/accounts/update", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel_id: channelId, ...patch }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || "No se pudo guardar el canal");
  return data;
}

export async function suggestPublishTarget(
  projectId: string,
  meta: { title?: string; description?: string; tags?: string[] },
): Promise<PublishSuggestion | null> {
  try {
    const res = await fetch("/api/publish/youtube/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_id: projectId, ...meta }),
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

async function postJson(url: string, body: unknown) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`);
  return data;
}

export interface PublishResult {
  videoUrl: string;
  studioUrl: string;
  thumbnailSet: boolean;
  format?: "short" | "video";
  channelTitle?: string;
}

/**
 * Publica un proyecto completo: metadatos (usa los del proyecto), miniatura y subida.
 * onProgress recibe porcentaje 0-100 y un mensaje corto.
 */
export async function publishProject(
  projectId: string,
  opts: {
    privacy: Privacy;
    title?: string;
    description?: string;
    tags?: string[];
    channelId?: string;
    format?: PublishFormat;
    onProgress?: (pct: number, msg: string) => void;
  },
): Promise<PublishResult> {
  const report = opts.onProgress || (() => {});

  report(2, "Preparando metadatos...");
  let title = opts.title;
  let description = opts.description;
  let tags = opts.tags;
  if (!title || !description || !tags || tags.length === 0) {
    const info = await fetch(`/api/projects/${projectId}/publish-info`).then((r) => (r.ok ? r.json() : null));
    title = title || info?.title || "Video";
    description = description || [info?.description, info?.hashtags_str].filter(Boolean).join("\n\n");
    tags = tags && tags.length ? tags : (info?.tags as string[]) || [];
  }

  report(6, "Preparando miniatura...");
  const prep = await postJson("/api/publish/prepare", { project_id: projectId });
  let thumbnailUrl: string | null = prep?.thumbnail_url || null;
  if (!thumbnailUrl) {
    try {
      const t = await postJson("/api/publish/thumbnail", {
        project_id: projectId,
        title,
        topic: prep?.topic || title,
        style: "cinematic",
      });
      thumbnailUrl = t?.url || null;
    } catch {
      thumbnailUrl = null; // se publica igual; YouTube elegirá un fotograma
    }
  }

  report(10, "Iniciando subida...");
  const { task_id } = await postJson("/api/publish/youtube/upload", {
    project_id: projectId,
    title,
    description,
    tags,
    privacy: opts.privacy,
    thumbnail_url: thumbnailUrl,
    channel_id: opts.channelId || undefined,
    format: opts.format && opts.format !== "auto" ? opts.format : undefined,
  });

  // Sondeo del progreso de subida hasta terminar o fallar
  for (let i = 0; i < 3600; i++) {
    await new Promise((r) => setTimeout(r, 1500));
    const p = await fetch(`/api/progress/${encodeURIComponent(task_id)}`).then((r) => (r.ok ? r.json() : null));
    if (!p) continue;
    if (typeof p.progress === "number") report(Math.max(10, Math.min(99, p.progress)), p.message || "Subiendo...");
    if (p.error) throw new Error(p.error);
    if (p.completed && p.result?.video_id) {
      report(100, "Publicado");
      return {
        videoUrl: p.result.video_url || `https://youtu.be/${p.result.video_id}`,
        studioUrl: p.result.studio_url || "",
        thumbnailSet: Boolean(p.result.thumbnail_set),
        format: p.result.format,
        channelTitle: p.result.channel_title,
      };
    }
  }
  throw new Error("La subida tardó demasiado. Revisa YouTube Studio.");
}
