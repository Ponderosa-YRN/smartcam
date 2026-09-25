"use client";

import { useEffect, useState } from "react";
import {
  listUsers, createUser, deleteUser,
  listTenants, createTenant,
  listInvites, createInvite, revokeInvite,
  getTenantUsage, updateTenantBilling,
  listDevices, createDevice, rotateDeviceToken, deleteDevice,
  type AuthUser, type Tenant, type Invite, type TenantUsage, type Device,
} from "@/lib/api";

interface UsageReport {
  tenant: string;
  plan: string;
  billing_status: string;
  limits: { label: string; max_cameras: number; max_storage_gb: number };
  usage: TenantUsage;
}

export default function AdminPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [slug, setSlug] = useState("");
  const [tname, setTname] = useState("");

  const [users, setUsers] = useState<AuthUser[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("viewer");

  const [inviteTenant, setInviteTenant] = useState<number | "">("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");
  const [invites, setInvites] = useState<Invite[]>([]);

  const [usageTenant, setUsageTenant] = useState<number | "">("");
  const [usage, setUsage] = useState<UsageReport | null>(null);

  const [deviceTenant, setDeviceTenant] = useState<number | "">("");
  const [devices, setDevices] = useState<Device[]>([]);
  const [deviceName, setDeviceName] = useState("");
  const [deviceToken, setDeviceToken] = useState("");

  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  function reload() {
    listUsers().then(setUsers).catch((e) => setError(e.message));
    listTenants().then(setTenants).catch(() => {});
  }
  useEffect(reload, []);

  useEffect(() => {
    if (inviteTenant === "") { setInvites([]); return; }
    listInvites(inviteTenant).then(setInvites).catch(() => {});
  }, [inviteTenant]);

  useEffect(() => {
    if (usageTenant === "") { setUsage(null); return; }
    getTenantUsage(usageTenant).then(setUsage).catch(() => {});
  }, [usageTenant]);

  useEffect(() => {
    if (deviceTenant === "") { setDevices([]); return; }
    listDevices(deviceTenant).then(setDevices).catch(() => {});
  }, [deviceTenant]);

  async function onAddTenant(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setMsg("");
    try {
      await createTenant(slug.trim(), tname.trim() || slug.trim());
      setMsg("Tenant created");
      setSlug(""); setTname("");
      reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to create tenant"); }
  }

  async function onAddUser(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setMsg("");
    try {
      await createUser(username.trim(), password, role);
      setMsg("User created");
      setUsername(""); setPassword("");
      reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to create user"); }
  }

  async function onDelete(id: number) {
    setError(""); setMsg("");
    try { await deleteUser(id); setMsg("User deleted"); reload(); }
    catch (err) { setError(err instanceof Error ? err.message : "Failed to delete user"); }
  }

  async function onInvite(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setMsg("");
    try {
      const inv = await createInvite(Number(inviteTenant), inviteEmail.trim(), inviteRole);
      setMsg("Invite link: " + window.location.origin + "/invite/" + inv.token);
      setInviteEmail("");
      listInvites(Number(inviteTenant)).then(setInvites).catch(() => {});
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to create invite"); }
  }

  async function onRevoke(id: number) {
    setError(""); setMsg("");
    try { await revokeInvite(Number(inviteTenant), id); listInvites(Number(inviteTenant)).then(setInvites).catch(() => {}); }
    catch (err) { setError(err instanceof Error ? err.message : "Failed to revoke invite"); }
  }

  async function onChangePlan(plan: string) {
    setError(""); setMsg("");
    try {
      await updateTenantBilling(Number(usageTenant), { plan });
      setMsg("Plan updated");
      getTenantUsage(Number(usageTenant)).then(setUsage).catch(() => {});
      reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to update plan"); }
  }

  async function onCreateDevice(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setMsg("");
    try {
      const d = await createDevice(Number(deviceTenant), deviceName.trim());
      setDeviceToken(d.token);
      setMsg("Device created — copy the token now, it will not be shown again.");
      setDeviceName("");
      listDevices(Number(deviceTenant)).then(setDevices).catch(() => {});
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to create device"); }
  }

  async function onRotateDevice(id: number) {
    setError(""); setMsg("");
    try {
      const r = await rotateDeviceToken(Number(deviceTenant), id);
      setDeviceToken(r.token);
      setMsg("Token rotated — copy the new token now.");
      listDevices(Number(deviceTenant)).then(setDevices).catch(() => {});
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to rotate token"); }
  }

  async function onDeleteDevice(id: number) {
    setError(""); setMsg("");
    try {
      await deleteDevice(Number(deviceTenant), id);
      setMsg("Device deleted");
      listDevices(Number(deviceTenant)).then(setDevices).catch(() => {});
    } catch (err) { setError(err instanceof Error ? err.message : "Failed to delete device"); }
  }

  const pending = invites.filter((i) => !i.consumed);

  return (
    <main>
      <h1>Admin</h1>
      {error && <p style={{ color: "#f87171" }}>{error}</p>}
      {msg && <p className="muted">{msg}</p>}

      <h2>Tenants ({tenants.length})</h2>
      <form onSubmit={onAddTenant} className="row">
        <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="slug (e.g. hotel-a)" required />
        <input value={tname} onChange={(e) => setTname(e.target.value)} placeholder="name (optional)" />
        <button type="submit">Add tenant</button>
      </form>
      {tenants.map((t) => (
        <div className="card" key={t.id}>
          <strong>{t.name}</strong>
          <span className="muted"> · {t.slug} · id {t.id}</span>
        </div>
      ))}

      <h2>Billing &amp; usage</h2>
      <div className="row">
        <select value={usageTenant} onChange={(e) => setUsageTenant(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Select tenant…</option>
          {tenants.map((t) => (<option key={t.id} value={t.id}>{t.name}</option>))}
        </select>
      </div>
      {usage && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <p style={{ margin: 0 }}><strong>{usage.tenant}</strong><span className="muted"> · plan {usage.plan} · {usage.billing_status}</span></p>
            <select value={usage.plan} onChange={(e) => onChangePlan(e.target.value)}>
              {["free", "pro", "enterprise"].map((p) => (<option key={p} value={p}>{p}</option>))}
            </select>
          </div>
          <div className="metrics">
            <div className="metric"><div className="big">{usage.usage.cameras}</div><div className="muted">Cameras</div></div>
            <div className="metric"><div className="big">{usage.usage.events}</div><div className="muted">Events</div></div>
            <div className="metric"><div className="big">{usage.usage.plates}</div><div className="muted">Plates</div></div>
            <div className="metric"><div className="big">{(usage.usage.storage_bytes / 1e6).toFixed(1)} MB</div><div className="muted">Storage</div></div>
          </div>
        </div>
      )}

      <h2>Edge devices</h2>
      <form onSubmit={onCreateDevice} className="row">
        <select value={deviceTenant} onChange={(e) => setDeviceTenant(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Select tenant…</option>
          {tenants.map((t) => (<option key={t.id} value={t.id}>{t.name}</option>))}
        </select>
        <input value={deviceName} onChange={(e) => setDeviceName(e.target.value)} placeholder="device name" required />
        <button type="submit" disabled={deviceTenant === ""}>Provision device</button>
      </form>
      {deviceToken && (
        <div className="card">
          <p style={{ margin: 0 }}><strong>Device token</strong> (shown once):</p>
          <pre style={{ wordBreak: "break-all", whiteSpace: "pre-wrap" }}>{deviceToken}</pre>
          <button className="secondary" onClick={() => navigator.clipboard.writeText(deviceToken)}>Copy token</button>
        </div>
      )}
      {devices.map((d) => (
        <div className="card row" key={d.id} style={{ justifyContent: "space-between" }}>
          <span><strong>{d.name}</strong><span className="muted"> · id {d.id} · gen {d.token_generation ?? 0}</span></span>
          <span className="row" style={{ margin: 0 }}>
            <button className="secondary" onClick={() => onRotateDevice(d.id)}>Rotate token</button>
            <button className="secondary" onClick={() => onDeleteDevice(d.id)}>Delete</button>
          </span>
        </div>
      ))}
      {deviceTenant !== "" && devices.length === 0 && <p className="muted">No devices for this tenant.</p>}

      <h2>Invite users</h2>
      <form onSubmit={onInvite} className="row">
        <select value={inviteTenant} onChange={(e) => setInviteTenant(e.target.value ? Number(e.target.value) : "")}>
          <option value="">Select tenant…</option>
          {tenants.map((t) => (<option key={t.id} value={t.id}>{t.name}</option>))}
        </select>
        <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="email" required />
        <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
          {["admin", "security", "manager", "viewer"].map((r) => (<option key={r} value={r}>{r}</option>))}
        </select>
        <button type="submit" disabled={inviteTenant === ""}>Send invite</button>
      </form>
      {pending.map((i) => (
        <div className="card row" key={i.id} style={{ justifyContent: "space-between" }}>
          <span><strong>{i.email}</strong><span className="muted"> · {i.role}</span></span>
          <span className="row" style={{ margin: 0 }}>
            <button className="secondary" onClick={() => navigator.clipboard.writeText(window.location.origin + "/invite/" + i.token)}>Copy link</button>
            <button className="secondary" onClick={() => onRevoke(i.id)}>Revoke</button>
          </span>
        </div>
      ))}
      {inviteTenant !== "" && pending.length === 0 && <p className="muted">No pending invites.</p>}

      <h2>Users ({users.length})</h2>
      <form onSubmit={onAddUser} className="row">
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" required />
        <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" type="password" required />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {["admin", "security", "manager", "viewer"].map((r) => (<option key={r} value={r}>{r}</option>))}
        </select>
        <button type="submit">Add user</button>
      </form>
      {users.map((u) => (
        <div className="card row" key={u.id} style={{ justifyContent: "space-between" }}>
          <span><strong>{u.username}</strong><span className="muted"> · {u.role}{u.tenant_id != null ? " · tenant " + u.tenant_id : ""}</span></span>
          <button className="secondary" onClick={() => onDelete(u.id)} disabled={u.username === "admin"}>Delete</button>
        </div>
      ))}
    </main>
  );
}
