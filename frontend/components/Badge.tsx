export default function Badge({
  tone,
  children,
}: {
  tone?: "ok" | "warn" | "danger";
  children: React.ReactNode;
}) {
  return <span className={"badge" + (tone ? " " + tone : "")}>{children}</span>;
}

/** Green / amber / red for a 0..1 confidence value. */
export function confTone(c: number): "ok" | "warn" | "danger" {
  if (c >= 0.8) return "ok";
  if (c >= 0.5) return "warn";
  return "danger";
}
