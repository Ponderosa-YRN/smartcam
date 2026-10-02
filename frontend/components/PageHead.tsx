export default function PageHead({
  title,
  sub,
  actions,
}: {
  title: string;
  sub?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="page-head" style={{ display: "flex", alignItems: "flex-start", gap: "1rem", flexWrap: "wrap" }}>
      <div style={{ flex: 1, minWidth: 220 }}>
        <h1>{title}</h1>
        {sub ? <p className="sub">{sub}</p> : null}
      </div>
      {actions ? <div className="row" style={{ margin: 0 }}>{actions}</div> : null}
    </div>
  );
}
