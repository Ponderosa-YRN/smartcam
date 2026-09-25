// API client for the SmartCam backend. Tokens are stored in localStorage (v1).
// TODO(hardening): switch to an httpOnly cookie via a Next.js server route.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "smartcam_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = "Bearer " + token;

  const res = await fetch(API_URL + path, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(res.status + ": " + detail);
  }
  return (await res.json()) as T;
}

// -- types -------------------------------------------------------------

export interface User {
  id: number;
  username: string;
  role: string;
}

export interface EventItem {
  id: number;
  camera_id: string;
  camera_name: string;
  event_type: string;
  top_object: string;
  start_ts: number;
  summary?: string;
  created_at?: string;
  objects?: string[];
}

export interface OpenAlert extends EventItem {
  acknowledged: number;
  resolved: number;
  escalated: number;
  assignee?: string;
}

export interface CameraSource {
  id: string;
  name: string;
  uri: string;
  enabled: boolean;
  running: boolean;
  status: string;
  health: string;
}

export interface Plate {
  id: number;
  camera_id: string;
  camera_name: string;
  plate: string;
  confidence: number;
  ts: number;
}

export interface Face {
  id: number;
  name: string;
  role: string;
  consent: number;
  thumb_path?: string;
}

export interface FaceMatch {
  id: number;
  camera_id: string;
  camera_name: string;
  face_id: number;
  name: string;
  confidence: number;
  ts: number;
}

export interface Identity {
  id: number;
  name: string;
  face_id?: number;
}

export interface Sighting {
  id: number;
  identity_id: number;
  camera_id: string;
  camera_name: string;
  confidence: number;
  ts: number;
}

export interface AuthUser {
  id: number;
  username: string;
  role: string;
  tenant_id?: number | null;
  created_at?: string;
}

export interface Tenant {
  id: number;
  slug: string;
  name: string;
  created_at?: string;
}

export interface Invite {
  id: number;
  tenant_id: number;
  email: string;
  role: string;
  token?: string;
  consumed: number;
  expires_at: number;
}

export interface InvitePreview {
  email: string;
  role: string;
  tenant: string;
}

export interface Plan {
  label: string;
  max_cameras: number;
  max_storage_gb: number;
}

export interface TenantUsage {
  cameras: number;
  events: number;
  plates: number;
  faces: number;
  identities: number;
  storage_bytes: number;
}

export interface Device {
  id: number;
  tenant_id: number;
  site_id?: number | null;
  name: string;
  token_generation?: number;
  last_seen?: number | null;
  created_at?: string;
}

export interface Occupancy {
  people: number;
  vehicles: number;
  entered?: number;
  left?: number;
  cameras: Record<string, { name: string; people: number; vehicles: number; status: string }>;
}

export interface OccupancySample {
  ts: number;
  people: number;
  vehicles: number;
}

// -- auth --------------------------------------------------------------

export async function login(username: string, password: string): Promise<{ role: string }> {
  const data = await request<{ access_token: string; refresh_token: string; role: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.access_token);
  return { role: data.role };
}

export function logout(): void {
  setToken(null);
}

export async function me(): Promise<User> {
  return request<User>("/auth/me");
}

// -- cameras / live ----------------------------------------------------

export async function listSources(): Promise<CameraSource[]> {
  return request<CameraSource[]>("/api/sources");
}

export async function fetchFrameBlob(sourceId: string): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API_URL + "/api/frame/" + sourceId, { headers });
  if (!res.ok) throw new Error(res.status + ": " + res.statusText);
  return res.blob();
}

export async function fetchClipBlob(eventId: number): Promise<Blob> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API_URL + "/api/clips/" + eventId, { headers });
  if (!res.ok) throw new Error(res.status + ": " + res.statusText);
  return res.blob();
}

// -- import / sources --------------------------------------------------

export interface SourceInput {
  id: string;
  name: string;
  uri: string;
  loop: boolean;
  fast: boolean;
}

export interface SourceStatus {
  status: string;
  fps: number;
  frames: number;
  active_objects?: string[];
  object_counts?: Record<string, number>;
  error?: string;
  [key: string]: unknown;
}

export async function uploadVideo(file: File): Promise<{ path: string; filename: string }> {
  const token = getToken();
  const fd = new FormData();
  fd.append("file", file);
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API_URL + "/api/upload", { method: "POST", body: fd, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new Error(res.status + ": " + detail);
  }
  return res.json();
}

export async function createSource(src: SourceInput): Promise<{ id: string }> {
  return request<{ id: string }>("/api/sources", { method: "POST", body: JSON.stringify(src) });
}

export async function startSource(id: string): Promise<void> {
  await request<{ ok: boolean }>("/api/start/" + id, { method: "POST" });
}

export async function stopSource(id: string): Promise<void> {
  await request<{ ok: boolean }>("/api/stop/" + id, { method: "POST" });
}

export async function removeSource(id: string): Promise<void> {
  await request<{ ok: boolean }>("/api/sources/" + id, { method: "DELETE" });
}

export async function getSourceStatus(id: string): Promise<SourceStatus> {
  return request<SourceStatus>("/api/status/" + id);
}

// -- events / alerts ---------------------------------------------------

export async function listEvents(
  limit = 50,
  filters?: { camera_id?: string; event_type?: string }
): Promise<EventItem[]> {
  let q = "/api/events?limit=" + limit;
  if (filters?.camera_id) q += "&camera_id=" + encodeURIComponent(filters.camera_id);
  if (filters?.event_type) q += "&event_type=" + encodeURIComponent(filters.event_type);
  return request<EventItem[]>(q);
}

export async function listAlerts(limit = 200): Promise<OpenAlert[]> {
  return request<OpenAlert[]>("/api/open_alerts?limit=" + limit);
}

export async function ackAlert(id: number): Promise<void> {
  await request<{ ok: boolean }>("/api/ack/" + id, { method: "POST" });
}

export async function resolveAlert(id: number): Promise<void> {
  await request<{ ok: boolean }>("/api/resolve/" + id, { method: "POST" });
}

// -- search / analytics ------------------------------------------------

export async function search(q: string, limit = 50): Promise<EventItem[]> {
  return request<EventItem[]>("/api/search?q=" + encodeURIComponent(q) + "&limit=" + limit);
}

export async function occupancy(): Promise<Occupancy> {
  return request<Occupancy>("/api/occupancy");
}

export async function occupancyHistory(since?: number, limit = 500): Promise<OccupancySample[]> {
  let q = "/api/occupancy_history?limit=" + limit;
  if (since) q += "&since=" + since;
  return request<OccupancySample[]>(q);
}

// -- plates / faces / track --------------------------------------------

export async function listPlates(limit = 100): Promise<Plate[]> {
  return request<Plate[]>("/api/plates?limit=" + limit);
}

export async function listFaces(): Promise<Face[]> {
  return request<Face[]>("/api/faces");
}

export async function listFaceMatches(limit = 100): Promise<FaceMatch[]> {
  return request<FaceMatch[]>("/api/face_matches?limit=" + limit);
}

export async function listIdentities(): Promise<Identity[]> {
  return request<Identity[]>("/api/identities");
}

export async function listSightings(identityId: number, limit = 100): Promise<Sighting[]> {
  return request<Sighting[]>("/api/sightings/" + identityId + "?limit=" + limit);
}

// -- config -----------------------------------------------------------

export async function getConfig(): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/config");
}

export async function saveConfig(cfg: Record<string, unknown>): Promise<void> {
  await request<{ ok: boolean }>("/api/config", { method: "PUT", body: JSON.stringify(cfg) });
}

// -- tenants -----------------------------------------------------------

export async function listTenants(): Promise<Tenant[]> {
  return request<Tenant[]>("/tenants");
}

export async function createTenant(slug: string, name: string): Promise<Tenant> {
  return request<Tenant>("/tenants", { method: "POST", body: JSON.stringify({ slug, name }) });
}

// -- invites & registration ---------------------------------------------

export async function register(company: string, username: string, password: string): Promise<{ role: string }> {
  const data = await request<{ access_token: string; refresh_token: string; role: string }>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ company, username, password }),
  });
  setToken(data.access_token);
  return { role: data.role };
}

export async function createInvite(tenantId: number, email: string, role: string): Promise<Invite> {
  return request<Invite>("/tenants/" + tenantId + "/invites", { method: "POST", body: JSON.stringify({ email, role }) });
}

export async function listInvites(tenantId: number): Promise<Invite[]> {
  return request<Invite[]>("/tenants/" + tenantId + "/invites");
}

export async function revokeInvite(tenantId: number, inviteId: number): Promise<void> {
  await request<{ ok: boolean }>("/tenants/" + tenantId + "/invites/" + inviteId, { method: "DELETE" });
}

export async function getInvitePreview(token: string): Promise<InvitePreview> {
  return request<InvitePreview>("/invites/" + token);
}

export async function acceptInvite(token: string, username: string, password: string): Promise<void> {
  await request<{ id: number }>("/invites/" + token + "/accept", { method: "POST", body: JSON.stringify({ username, password }) });
}

// -- admin users -------------------------------------------------------

export async function listUsers(): Promise<AuthUser[]> {
  return request<AuthUser[]>("/auth/users");
}

export async function createUser(username: string, password: string, role: string): Promise<AuthUser> {
  return request<AuthUser>("/auth/users", {
    method: "POST",
    body: JSON.stringify({ username, password, role }),
  });
}

export async function deleteUser(id: number): Promise<void> {
  await request<{ ok: boolean }>("/auth/users/" + id, { method: "DELETE" });
}

// -- billing / usage ----------------------------------------------------

export async function listPlans(): Promise<Record<string, Plan>> {
  return request<Record<string, Plan>>("/plans");
}

export async function getTenantUsage(tenantId: number): Promise<{ tenant: string; plan: string; billing_status: string; limits: Plan; usage: TenantUsage }> {
  return request<{ tenant: string; plan: string; billing_status: string; limits: Plan; usage: TenantUsage }>("/tenants/" + tenantId + "/usage");
}

export async function updateTenantBilling(tenantId: number, fields: { plan?: string; billing_status?: string }): Promise<void> {
  await request<{ ok: boolean }>("/tenants/" + tenantId + "/billing", { method: "POST", body: JSON.stringify(fields) });
}

// -- edge devices ------------------------------------------------------

export async function listDevices(tenantId: number): Promise<Device[]> {
  return request<Device[]>("/tenants/" + tenantId + "/devices");
}

export async function createDevice(tenantId: number, name: string, siteId?: number): Promise<{ id: number; name: string; tenant_id: number; token: string }> {
  return request<{ id: number; name: string; tenant_id: number; token: string }>("/tenants/" + tenantId + "/devices", { method: "POST", body: JSON.stringify({ name, site_id: siteId }) });
}

export async function rotateDeviceToken(tenantId: number, deviceId: number): Promise<{ device_id: number; generation: number; token: string }> {
  return request<{ device_id: number; generation: number; token: string }>("/tenants/" + tenantId + "/devices/" + deviceId + "/rotate-token", { method: "POST" });
}

export async function deleteDevice(tenantId: number, deviceId: number): Promise<void> {
  await request<{ ok: boolean }>("/tenants/" + tenantId + "/devices/" + deviceId, { method: "DELETE" });
}

// -- webrtc -----------------------------------------------------------

export interface WebRTCIceServer {
  urls: string;
  username?: string;
  credential?: string;
}

export async function getWebRTCConfig(): Promise<{ enabled: boolean; ice_servers: WebRTCIceServer[] }> {
  return request<{ enabled: boolean; ice_servers: WebRTCIceServer[] }>("/api/webrtc/config");
}
