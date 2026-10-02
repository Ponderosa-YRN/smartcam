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
import PageHead from "@/components/PageHead";
import EmptyState from "@/components/EmptyState";
import Badge from "@/components/Badge";

interface UsageReport {
  tenant: string;
  plan: string;
  billing_status: string;
  limits: { label: string; max_cameras: number; max_storage_gb: number };
  usage: TenantUsage;
}

const PLANS = ["free", "pro", "enterprise"];
const ROLES = ["admin", "security", "manager", "viewer"];
type Tab = "tenants" | "users" | "devices" | "invites" | "billing";

const TABS: [Tab, string][] = [
  ["tenants", "Tenants"],
  ["users", "Users"],
  ["devices", "Edge devices"],
  ["invites", "Invites"],
  ["billing", "Billing & usage"],
];

export default function AdminPage() {
  const [tab, setTab] = useState<Tab>("tenants");

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
    listUsers().then(setUsers).catch((e) => setError(e instanceof Error ? e.message : "Failed to load users"));
    listTenants().then(setTenants).catch(() => {});
  }

  useEffect(reload, []);

  useEffect(() => {
    if (inviteTenant === "") {
      setInvites([]);
      return;
    }
    listInvites(inviteTenant).then(setInvites).catch(() => {});
  }, [inviteTenant]);

  useEffect(() => {
    if (usageTenant === "") {
      setUsage(null);
      return;
    }
    getTenantUsage(usageTenant).then(setUsage).catch(() => {});
  }, [usageTenant]);

  useEffect(() => {
    if (deviceTenant === "") {
      setDevices([]);
      return;
    }
    listDevices(deviceTenant).then(setDevices).catch(() => {});
  }, [deviceTenant]);

  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(""), 5000);
    return () => clearTimeout(t);
  }, [msg]);

  async function onAddTenant(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await createTenant(slug.trim(), tname.trim() || slug.trim());
      setMsg("Tenant created");
      setSlug("");
      setTname("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create tenant");
    }
  }

  async function onAddUser(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await createUser(username.trim(), password, role);
      setMsg("User created");
      setUsername("");
      setPassword("");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    }
  }

  async function onDelete(id: number) {
    setError("");
    setMsg("");
    try {
      await deleteUser(id);
      setMsg("User deleted");
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete user");
    }
  }

  async function onInvite(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      const inv = await createInvite(Number(inviteTenant), inviteEmail.trim(), inviteRole);
      setMsg("Invite link: " + window.location.origin + "/invite/" + inv.token);
      setInviteEmail("");
      listInvites(Number(inviteTenant)).then(setInvites).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create invite");
    }
  }

  async function onRevoke(id: number) {
    setError("");
    setMsg("");
    try {
      await revokeInvite(Number(inviteTenant), id);
      listInvites(Number(inviteTenant)).then(setInvites).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke invite");
    }
  }

  async function onChangePlan(plan: string) {
    setError("");
    setMsg("");
    try {
      await updateTenantBilling(Number(usageTenant), { plan });
      setMsg("Plan updated");
      getTenantUsage(Number(usageTenant)).then(setUsage).catch(() => {});
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update plan");
    }
  }

  async function onCreateDevice(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      const d = await createDevice(Number(deviceTenant), deviceName.trim());
      setDeviceToken(d.token);
      setMsg("Device created — copy the token now, it will not be shown again.");
      setDeviceName("");
      listDevices(Number(deviceTenant)).then(setDevices).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create device");
    }
  }

  async function onRotateDevice(id: number) {
    setError("");
    setMsg("");
    try {
      const r = await rotateDeviceToken(Number(deviceTenant), id);
      setDeviceToken(r.token);
      setMsg("Token rotated — copy the new token now.");
      listDevices(Number(deviceTenant)).then(setDevices).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rotate token");
    }
  }

  async function onDeleteDevice(id: number) {
    setError("");
    setMsg("");
    try {
      await deleteDevice(Number(deviceTenant), id);
      setMsg("Device deleted");
      listDevices(Number(deviceTenant)).then(setDevices).catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete device");
    }
  }

  const pending = invites.filter((i) => !i.consumed);

  const tenantPicker = (
    value: number | "",
    onChange: (v: number | "") => void,
    required = true
  ) => (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : "")}
      required={required}
      style={{ minWidth: 200 }}
    >
      <option value="">Select tenant…</option>
      {tenants.map((t) => (
        <option key={t.id} value={t.id}>
          {t.name}
        </option>
      ))}
    </select>
  );

  return (
    <main>
      <PageHead title="Admin" sub="Tenants, people, edge devices, invitations and billing." />

      {error && <div className="alert-error">{error}</div>}
      {msg && <div className="flash">{msg}</div>}

      <div className="tabs">
        {TABS.map(([key, label]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
            {label}
            {key === "tenants" && <span className="n">{tenants.length}</span>}
            {key === "users" && <span className="n">{users.length}</span>}
          </button>
        ))}
      </div>

      {tab === "tenants" && (
        <>
          <form onSubmit={onAddTenant} className="row card">
            <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="slug (e.g. hotel-a)" required />
            <input value={tname} onChange={(e) => setTname(e.target.value)} placeholder="Display name (optional)" />
            <button type="submit">Add tenant</button>
          </form>

          {tenants.length === 0 ? (
            <EmptyState title="No tenants yet" hint="Create one above — each hotel is a tenant." />
          ) : (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Slug</th>
                    <th>ID</th>
                  </tr>
                </thead>
                <tbody>
                  {tenants.map((t) => (
                    <tr key={t.id}>
                      <td><strong>{t.name}</strong></td>
                      <td className="mono muted">{t.slug}</td>
                      <td className="muted">{t.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {tab === "users" && (
        <>
          <form onSubmit={onAddUser} className="row card">
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" required />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              type="password"
              required
            />
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button type="submit">Add user</button>
          </form>

          {users.length === 0 ? (
            <EmptyState title="No users" hint="Add the first user above." />
          ) : (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Role</th>
                    <th>Tenant</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td><strong>{u.username}</strong></td>
                      <td><Badge>{u.role}</Badge></td>
                      <td className="muted">{u.tenant_id != null ? u.tenant_id : "—"}</td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="secondary btn-sm"
                          onClick={() => onDelete(u.id)}
                          disabled={u.username === "admin"}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {tab === "devices" && (
        <>
          <form onSubmit={onCreateDevice} className="row card">
            {tenantPicker(deviceTenant, setDeviceTenant)}
            <input value={deviceName} onChange={(e) => setDeviceName(e.target.value)} placeholder="device name (e.g. Front desk PC)" required />
            <button type="submit" disabled={deviceTenant === ""}>Provision device</button>
          </form>

          {deviceToken && (
            <div className="card">
              <div className="cam-head">
                <strong>Device token</strong>
                <Badge tone="warn">Shown once</Badge>
              </div>
              <p className="muted" style={{ fontSize: ".88rem", marginTop: 0 }}>
                Paste this into the edge agent running at the hotel.
              </p>
              <pre className="mono" style={{ wordBreak: "break-all", whiteSpace: "pre-wrap", fontSize: ".8rem", margin: 0 }}>
                {deviceToken}
              </pre>
              <button
                className="secondary btn-sm"
                style={{ marginTop: ".7rem" }}
                onClick={() => navigator.clipboard.writeText(deviceToken)}
              >
                Copy token
              </button>
            </div>
          )}

          {devices.length > 0 && (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>ID</th>
                    <th>Token gen</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {devices.map((d) => (
                    <tr key={d.id}>
                      <td><strong>{d.name}</strong></td>
                      <td className="muted">{d.id}</td>
                      <td className="muted">{d.token_generation ?? 0}</td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <button className="secondary btn-sm" onClick={() => onRotateDevice(d.id)}>
                          Rotate
                        </button>{" "}
                        <button className="secondary btn-sm" onClick={() => onDeleteDevice(d.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {deviceTenant !== "" && devices.length === 0 && (
            <EmptyState title="No devices for this tenant" hint="Provision one above to connect a hotel PC." />
          )}
        </>
      )}

      {tab === "invites" && (
        <>
          <form onSubmit={onInvite} className="row card">
            {tenantPicker(inviteTenant, setInviteTenant)}
            <input value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="email" required />
            <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button type="submit" disabled={inviteTenant === ""}>Send invite</button>
          </form>

          {pending.length > 0 && (
            <div className="card">
              <table className="table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Role</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {pending.map((i) => (
                    <tr key={i.id}>
                      <td><strong>{i.email}</strong></td>
                      <td><Badge>{i.role}</Badge></td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <button
                          className="secondary btn-sm"
                          onClick={() =>
                            navigator.clipboard.writeText(window.location.origin + "/invite/" + i.token)
                          }
                        >
                          Copy link
                        </button>{" "}
                        <button className="secondary btn-sm" onClick={() => onRevoke(i.id)}>
                          Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {inviteTenant !== "" && pending.length === 0 && (
            <EmptyState title="No pending invites" hint="Invite a colleague above." />
          )}
          {inviteTenant === "" && <EmptyState title="Pick a tenant" hint="Invitations belong to a tenant." />}
        </>
      )}

      {tab === "billing" && (
        <>
          <div className="row">
            {tenantPicker(usageTenant, setUsageTenant, false)}
          </div>

          {!usage ? (
            <EmptyState title="Pick a tenant" hint="See their plan and how much they are using." />
          ) : (
            <div className="card">
              <div className="cam-head">
                <div>
                  <strong>{usage.tenant}</strong>
                  <span className="muted"> · {usage.billing_status}</span>
                </div>
                <select value={usage.plan} onChange={(e) => onChangePlan(e.target.value)}>
                  {PLANS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>

              <div className="metrics" style={{ marginBottom: 0 }}>
                <div className="metric">
                  <div className="label">Cameras</div>
                  <div className="big">
                    {usage.usage.cameras}
                    <span className="muted" style={{ fontSize: "1rem", fontWeight: 500 }}>
                      {" "}/ {usage.limits.max_cameras}
                    </span>
                  </div>
                </div>
                <div className="metric">
                  <div className="label">Events</div>
                  <div className="big">{usage.usage.events}</div>
                </div>
                <div className="metric">
                  <div className="label">Plates</div>
                  <div className="big">{usage.usage.plates}</div>
                </div>
                <div className="metric">
                  <div className="label">Storage</div>
                  <div className="big">{(usage.usage.storage_bytes / 1e6).toFixed(1)}<span className="muted" style={{ fontSize: "1rem", fontWeight: 500 }}> MB</span></div>
                </div>
              </div>

              <p className="muted" style={{ fontSize: ".85rem", marginBottom: 0 }}>
                Plan {usage.plan} allows {usage.limits.max_cameras} cameras and{" "}
                {usage.limits.max_storage_gb} GB of storage.
              </p>
            </div>
          )}
        </>
      )}
    </main>
  );
}
