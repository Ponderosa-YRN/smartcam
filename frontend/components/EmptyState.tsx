export default function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <div className="title">{title}</div>
      {hint ? <div>{hint}</div> : null}
    </div>
  );
}
