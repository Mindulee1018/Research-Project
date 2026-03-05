export default function Pill({ children }) {
  return (
    <span
      className="badge rounded-pill text-bg-light border"
      style={{ fontWeight: 600 }}
    >
      {children}
    </span>
  );
}