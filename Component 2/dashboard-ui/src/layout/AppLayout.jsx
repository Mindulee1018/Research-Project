import { NavLink, Outlet } from "react-router-dom";

function SideItem({ to, label }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `list-group-item list-group-item-action ${
          isActive ? "active" : ""
        }`
      }
      end
    >
      {label}
    </NavLink>
  );
}

export default function AppLayout() {
  return (
    <div className="container-fluid">
      <div className="row" style={{ minHeight: "100vh" }}>
        {/* Sidebar */}
        <aside className="col-12 col-md-3 col-lg-2 p-0 border-end bg-light">
          <div className="p-3 border-bottom">
            <div className="fw-bold">Component 2</div>
            <div className="text-muted small">Drift & New Terms</div>
          </div>

          <div className="list-group list-group-flush">
            <SideItem to="/" label="Home" />
            <SideItem to="/drift" label="Drift Details" />
          </div>

          <div className="p-3 mt-auto text-muted small">
            Use the menu to navigate
          </div>
        </aside>

        {/* Main */}
        <main className="col-12 col-md-9 col-lg-10 py-3">
          <Outlet />
        </main>
      </div>
    </div>
  );
}