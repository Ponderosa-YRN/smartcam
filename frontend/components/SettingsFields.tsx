"use client";

import { useState } from "react";
import { getPath, type Field } from "@/lib/settings-schema";

/** Number input that keeps what you type locally, so decimals are typeable. */
function NumberControl({
  initial,
  field,
  onChange,
}: {
  initial: unknown;
  field: Field;
  onChange: (v: number) => void;
}) {
  const [text, setText] = useState(initial === undefined || initial === null ? "" : String(initial));
  return (
    <input
      type="number"
      value={text}
      step={field.step}
      min={field.min}
      max={field.max}
      onChange={(e) => {
        setText(e.target.value);
        const n = Number(e.target.value);
        if (e.target.value !== "" && !Number.isNaN(n)) onChange(n);
      }}
    />
  );
}

/** Comma-separated list editor. Leaves empty entries out of the saved value. */
function TagsControl({ initial, onChange }: { initial: unknown; onChange: (v: string[]) => void }) {
  const list = Array.isArray(initial) ? initial.map(String) : [];
  const [text, setText] = useState(list.join(", "));
  return (
    <input
      value={text}
      placeholder="comma separated"
      onChange={(e) => {
        setText(e.target.value);
        onChange(
          e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean)
        );
      }}
    />
  );
}

/** One labelled control for any config path or plain object field. */
export default function Control({
  field,
  cfg,
  onSet,
}: {
  field: Field;
  cfg: unknown;
  onSet: (path: string, value: unknown) => void;
}) {
  const value = getPath(cfg, field.path);

  if (field.kind === "bool") {
    const on = Boolean(value);
    return (
      <label className="switch">
        <input type="checkbox" checked={on} onChange={(e) => onSet(field.path, e.target.checked)} />
        <span className="state">{on ? "On" : "Off"}</span>
      </label>
    );
  }

  if (field.kind === "select") {
    return (
      <select value={String(value ?? "")} onChange={(e) => onSet(field.path, e.target.value)}>
        {(field.options ?? []).map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  }

  if (field.kind === "number") {
    return <NumberControl initial={value} field={field} onChange={(n) => onSet(field.path, n)} />;
  }

  if (field.kind === "tags") {
    return <TagsControl initial={value} onChange={(v) => onSet(field.path, v)} />;
  }

  return (
    <input
      type={field.kind === "secret" ? "password" : "text"}
      value={value === undefined || value === null ? "" : String(value)}
      placeholder={field.kind === "secret" ? "•••• (leave to keep)" : undefined}
      onChange={(e) => onSet(field.path, e.target.value)}
    />
  );
}
