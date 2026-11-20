export function Signal({ small = false }: { small?: boolean }) {
  return (
    <span className={"signal" + (small ? " small" : "")} aria-hidden>
      <i />
      <i />
      <i />
      <i />
      <i />
    </span>
  );
}
export function Brand() {
  return (
    <div className="brand">
      <Signal />
      <div>
        <strong>音乐教职雷达</strong>
        <span>FACULTY RADAR</span>
      </div>
    </div>
  );
}
