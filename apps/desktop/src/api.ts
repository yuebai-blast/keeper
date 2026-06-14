// Keeper 推理 sidecar 的 HTTP 客户端。
// 本机服务，默认 127.0.0.1:8761（mise run sidecar 启动）。可由 VITE_SIDECAR_URL 覆盖。

const BASE = import.meta.env.VITE_SIDECAR_URL ?? "http://127.0.0.1:8761";

/** /health 返回：模型就绪态。 */
export interface Health {
  status: "loading" | "ready" | "error" | string;
  version: string;
  detail: string;
}

async function get<T>(path: string): Promise<T> {
  const resp = await fetch(`${BASE}${path}`);
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} ${resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

/** 查询 sidecar 健康/就绪状态。连不上会抛错（服务没起）。 */
export function getHealth(): Promise<Health> {
  return get<Health>("/health");
}

/** 一个「瞬间组」。 */
export interface Group {
  id: string;
  photos: string[];
}

export interface PhotoError {
  path: string;
  error: string;
}

export interface GroupResponse {
  groups: Group[];
  errors: PhotoError[];
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    throw new Error(`HTTP ${resp.status} ${resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

/** 把一批照片路径分成「瞬间组」（DINOv2 语义 + 时间）。 */
export function groupPhotos(photos: string[]): Promise<GroupResponse> {
  return post<GroupResponse>("/group", { photos });
}
