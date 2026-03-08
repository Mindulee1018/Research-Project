import React, { useEffect, useState } from "react";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";


/* =====================================================
   ENHANCED FB-like Sinhala UI (Bootstrap-based)
   ✅ All backend logic preserved — visual polish only
===================================================== */

/* ---------- Global animation styles injected once ---------- */
const GLOBAL_STYLES = `
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;900&display=swap');

  :root {
    --sl-blue: #1877f2;
    --sl-blue-hover: #1565d8;
    --sl-blue-soft: #e7f0fe;
    --sl-green: #42b72a;
    --sl-bg: #f0f2f5;
    --sl-card-bg: #ffffff;
    --sl-border: #e4e6ea;
    --sl-text: #1c1e21;
    --sl-muted: #65676b;
    --sl-shadow: 0 2px 12px rgba(0,0,0,0.08);
    --sl-radius: 12px;
    --sl-transition: 0.2s cubic-bezier(0.25,0.46,0.45,0.94);
  }

  body { font-family: 'Nunito', sans-serif !important; background: var(--sl-bg); }

  /* Card base */
  .sl-card {
    background: var(--sl-card-bg);
    border-radius: var(--sl-radius);
    box-shadow: var(--sl-shadow);
    border: 1px solid var(--sl-border);
    transition: box-shadow var(--sl-transition);
  }
  .sl-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.11); }

  /* Navbar */
  .sl-navbar {
    background: #fff !important;
    box-shadow: 0 1px 0 var(--sl-border), 0 4px 16px rgba(0,0,0,0.04);
  }
  .sl-logo {
    background: var(--sl-blue);
    color: #fff;
    font-size: 28px;
    font-weight: 900;
    width: 40px; height: 40px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Georgia', serif;
    box-shadow: 0 2px 8px rgba(24,119,242,0.4);
    transition: transform var(--sl-transition);
  }
  .sl-logo:hover { transform: scale(1.1); }

  .sl-search {
    max-width: 260px;
    border-radius: 20px;
    overflow: hidden;
    background: var(--sl-bg);
    border: 2px solid transparent;
    transition: border-color var(--sl-transition), box-shadow var(--sl-transition);
  }
  .sl-search:focus-within {
    border-color: var(--sl-blue);
    box-shadow: 0 0 0 3px rgba(24,119,242,0.15);
  }
  .sl-search .form-control { background: var(--sl-bg) !important; border: none !important; }
  .sl-search .form-control:focus { box-shadow: none !important; }
  .sl-search .input-group-text { background: var(--sl-bg) !important; border: none !important; }

  /* Avatar circle */
  .sl-avatar-circle {
    width: 38px; height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, #1877f2, #42a5f5);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 13px;
    box-shadow: 0 2px 6px rgba(24,119,242,0.35);
    transition: transform var(--sl-transition);
    cursor: pointer;
  }
  .sl-avatar-circle:hover { transform: scale(1.08); }

  .sl-tiny { font-size: 12px; }
  .fw-black { font-weight: 900 !important; }
  .sl-container { max-width: 1200px; margin: 0 auto; }

  /* Sticky sidebar */
  .sl-sticky { top: 72px; }

  /* Menu items */
  .sl-menuitem {
    border-radius: 8px !important;
    padding: 10px 12px !important;
    transition: background var(--sl-transition), transform var(--sl-transition) !important;
    font-weight: 600;
    border: none !important;
  }
  .sl-menuitem:hover {
    background: var(--sl-blue-soft) !important;
    color: var(--sl-blue) !important;
    transform: translateX(4px);
  }
  .sl-menuitem i { color: var(--sl-blue); font-size: 16px; }

  /* Story cards */
  .sl-story {
    flex: 0 0 auto;
    width: 100px; height: 160px;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    transition: transform var(--sl-transition), box-shadow var(--sl-transition);
  }
  .sl-story:hover { transform: scale(1.05); box-shadow: 0 8px 20px rgba(0,0,0,0.18); }
  .sl-story img { width: 100%; height: 100%; object-fit: cover; }
  .sl-story-name {
    position: absolute; bottom: 0; left: 0; right: 0;
    padding: 24px 6px 8px;
    background: linear-gradient(transparent, rgba(0,0,0,0.7));
    color: #fff; font-size: 12px; font-weight: 700;
    text-align: center;
  }
  .sl-story-ring {
    position: absolute; top: 8px; left: 8px;
    width: 30px; height: 30px;
    border-radius: 50%;
    border: 3px solid var(--sl-blue);
    background: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 900; color: var(--sl-blue);
    box-shadow: 0 0 0 2px #fff;
  }

  /* Post avatar */
  .sl-avatar {
    width: 44px; height: 44px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid var(--sl-border);
    transition: border-color var(--sl-transition);
  }
  .sl-avatar:hover { border-color: var(--sl-blue); }

  /* Post media */
  .sl-media {
    border-radius: 10px;
    overflow: hidden;
    max-height: 400px;
  }
  .sl-media img {
    width: 100%; object-fit: cover;
    transition: transform 0.4s ease;
  }
  .sl-media:hover img { transform: scale(1.02); }

  /* Action buttons */
  .sl-action-btn {
    border-radius: 8px !important;
    font-weight: 700 !important;
    padding: 8px 12px !important;
    border: none !important;
    transition: background var(--sl-transition), color var(--sl-transition), transform var(--sl-transition) !important;
  }
  .sl-action-btn:hover {
    background: var(--sl-blue-soft) !important;
    color: var(--sl-blue) !important;
    transform: scale(1.03);
  }
  .sl-action-btn.liked {
    background: var(--sl-blue-soft) !important;
    color: var(--sl-blue) !important;
  }
  .sl-action-btn.liked i { animation: pop 0.3s ease; }

  @keyframes pop {
    0% { transform: scale(1); }
    50% { transform: scale(1.5); }
    100% { transform: scale(1); }
  }

  /* Comment bubble */
  .sl-bubble {
    background: var(--sl-bg);
    border-radius: 14px;
    padding: 8px 12px;
    transition: background var(--sl-transition), box-shadow var(--sl-transition), transform var(--sl-transition);
    border: 1px solid transparent;
  }
  .sl-bubble:hover {
    background: #e7f0fe;
    border-color: rgba(24,119,242,0.2);
    box-shadow: 0 2px 8px rgba(24,119,242,0.1);
    transform: translateX(2px);
  }

  .sl-mini-avatar {
    width: 32px; height: 32px; min-width: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #f093fb, #f5576c);
    color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 13px;
  }

  /* Comment input */
  .sl-comment {
    border-radius: 22px !important;
    background: var(--sl-bg) !important;
    border: 2px solid transparent !important;
    transition: border-color var(--sl-transition), box-shadow var(--sl-transition) !important;
  }
  .sl-comment:focus {
    border-color: var(--sl-blue) !important;
    box-shadow: 0 0 0 3px rgba(24,119,242,0.12) !important;
    background: #fff !important;
  }

  /* Compose button */
  .sl-compose {
    background: var(--sl-bg) !important;
    border: none !important;
    color: var(--sl-muted) !important;
    font-weight: 600 !important;
    transition: background var(--sl-transition) !important;
  }
  .sl-compose:hover { background: #e4e6ea !important; }

  /* Hash items */
  .sl-hash {
    padding: 8px 4px;
    border-radius: 8px;
    transition: background var(--sl-transition);
    cursor: pointer;
  }
  .sl-hash:hover { background: var(--sl-bg); }

  /* Friend row */
  .sl-friend {
    padding: 8px 4px;
    border-radius: 8px;
    cursor: pointer;
    transition: background var(--sl-transition);
  }
  .sl-friend:hover { background: var(--sl-bg); }

  .sl-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    background: var(--sl-green);
    display: inline-block;
    box-shadow: 0 0 0 2px rgba(66,183,42,0.3);
    animation: pulse-dot 2s infinite;
  }
  @keyframes pulse-dot {
    0%, 100% { box-shadow: 0 0 0 2px rgba(66,183,42,0.3); }
    50% { box-shadow: 0 0 0 5px rgba(66,183,42,0.1); }
  }

  /* Prediction badge colors */
  .sl-badge-hate { background: #ff4444; color: #fff; }
  .sl-badge-disinfo { background: #ffaa00; color: #1c1e21; }
  .sl-badge-normal { background: #42b72a; color: #fff; }

  /* Comment status badge */
  .sl-status {
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 12px;
    font-weight: 700;
  }
  .sl-status-normal { background: #d4f0cc; color: #1a5c11; }
  .sl-status-hate { background: #ffe0e0; color: #a00; }
  .sl-status-disinfo { background: #fff3cc; color: #7a5300; }
  .sl-status-pending { background: #ebebeb; color: #555; }
  .sl-status-error { background: #ffe0e0; color: #a00; }

  /* Drawer body scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #f0f2f5; }
  ::-webkit-scrollbar-thumb { background: #bcc0c4; border-radius: 3px; }

  /* Slide-in animation for new comments */
  @keyframes slideInComment {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .sl-comment-new { animation: slideInComment 0.3s ease both; }

  /* Ripple on Like button */
  .sl-ripple {
    position: relative;
    overflow: hidden;
  }
  .sl-ripple::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle, rgba(24,119,242,0.25) 0%, transparent 70%);
    transform: scale(0);
    transition: transform 0.35s ease;
    border-radius: inherit;
  }
  .sl-ripple:active::after { transform: scale(2.5); }

  /* Verified badge glow */
  .sl-verified { filter: drop-shadow(0 0 3px rgba(24,119,242,0.5)); }

  /* Trending tag pill */
  .sl-tag-pill {
    display: inline-block;
    background: var(--sl-blue-soft);
    color: var(--sl-blue);
    font-size: 11px;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 12px;
    margin-right: 4px;
  }

  /* XAI Drawer highlight styles */
  .lime-highlight-high { background: #ff4d4d; color: #fff; border-radius: 3px; padding: 1px 3px; font-weight: 700; }
  .lime-highlight-med { background: #ffaa00; color: #1c1e21; border-radius: 3px; padding: 1px 3px; }
  .lime-highlight-low { background: #ffe066; color: #1c1e21; border-radius: 3px; padding: 1px 3px; }
  .lime-highlight-pos { background: #d4f0cc; color: #155111; border-radius: 3px; padding: 1px 3px; }
`;

function GlobalStyles() {
  useEffect(() => {
    if (document.getElementById("sl-global-styles")) return;
    const el = document.createElement("style");
    el.id = "sl-global-styles";
    el.textContent = GLOBAL_STYLES;
    document.head.appendChild(el);
  }, []);
  return null;
}

/* =====================================================
   TOP BAR
===================================================== */
export function TopBar() {
  return (
    <>
      <GlobalStyles />
      <nav className="navbar navbar-expand-lg sl-navbar sticky-top">
        <div className="container-fluid sl-container">
          <a className="navbar-brand d-flex align-items-center gap-2 fw-black text-decoration-none" href="#">
            <div className="sl-logo">f</div>
            <span style={{ color: "#1877f2", fontSize: 20, letterSpacing: -0.5 }}>SLBook</span>
          </a>

          <div className="d-none d-lg-flex flex-grow-1 justify-content-center">
            <div className="input-group sl-search">
              <span className="input-group-text bg-light border-0">
                <i className="bi bi-search" style={{ color: "#65676b" }} />
              </span>
              <input className="form-control bg-light border-0" placeholder="SLBook එකේ හොයන්න..." />
            </div>
          </div>

          <div className="d-flex align-items-center gap-2">
            <NavIconBtn icon="bi-house-door-fill" active />
            <NavIconBtn icon="bi-people-fill" />
            <NavIconBtn icon="bi-chat-dots-fill" badge={3} />

            <div className="d-flex align-items-center gap-2 ms-1">
              <div className="sl-avatar-circle">TS</div>
              <div className="d-none d-md-block lh-sm">
                <div className="fw-bold small" style={{ color: "#1c1e21" }}>Sudakran</div>
                <div className="text-muted sl-tiny">Sri Lanka • Sinhala</div>
              </div>
            </div>
          </div>
        </div>
      </nav>
    </>
  );
}

function NavIconBtn({ icon, active, badge }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      className="btn rounded-pill position-relative"
      style={{
        background: active || hover ? "#e7f0fe" : "transparent",
        color: active ? "#1877f2" : "#65676b",
        border: "none",
        padding: "8px 16px",
        transition: "background 0.18s",
        fontSize: 18,
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <i className={`bi ${icon}`} />
      {badge ? (
        <span
          style={{
            position: "absolute", top: 2, right: 6,
            background: "#ff4444", color: "#fff",
            fontSize: 10, fontWeight: 900,
            width: 16, height: 16,
            borderRadius: "50%",
            display: "flex", alignItems: "center", justifyContent: "center",
            border: "2px solid #fff",
          }}
        >
          {badge}
        </span>
      ) : null}
    </button>
  );
}

/* =====================================================
   LEFT MENU
===================================================== */
export function LeftMenu() {
  return (
    <div className="position-sticky sl-sticky">
      <Card title="Menu">
        <MenuItem icon="bi-house-door-fill" text="මුල් පිටුව (Home)" active />
        <MenuItem icon="bi-people-fill" text="මිතුරන් (Friends)" />
        <MenuItem icon="bi-lightning-fill" text="Groups / Pages" />
        <MenuItem icon="bi-image-fill" text="Photos" />
        <MenuItem icon="bi-camera-video-fill" text="Videos" />
        <MenuItem icon="bi-bookmark-star-fill" text="Saved" />
      </Card>
      <div className="mt-3">
        <Card title="Shortcuts">
          <MenuItem icon="bi-mortarboard-fill" text="කැම්පස් Life" />
          <MenuItem icon="bi-trophy-fill" text="Cricket LK" />
          <MenuItem icon="bi-egg-fried" text="කොත්තු Lovers" />
        </Card>
      </div>
    </div>
  );
}

/* =====================================================
   RIGHT PANEL
===================================================== */
export function RightPanel() {
  return (
    <div className="position-sticky sl-sticky">
      <Card title="✨ Trending (Sri Lanka)">
        <HashItem tag="#කොත්තු" meta="Food • Colombo" count="12.4k" />
        <HashItem tag="#කැම්පස්Life" meta="Uni • Deadlines" count="8.1k" />
        <HashItem tag="#CricketLK" meta="Sports • Updates" count="31k" />
        <HashItem tag="#ගාලුVibe" meta="Travel • Beach" count="5.6k" />
      </Card>

      <div className="mt-3">
        <Card title="🟢 Online Friends">
          <FriendRow name="Namal" sub="Active now" />
          <FriendRow name="Sachini" sub="2m ago" />
          <FriendRow name="Isuru" sub="Active now" />
          <FriendRow name="Tharu" sub="5m ago" />
        </Card>
      </div>

    </div>
  );
}

/* =====================================================
   STORY ROW
===================================================== */
export function StoryRow() {
  const stories = [
    { name: "ඔයා", img: "https://images.unsplash.com/photo-1520975661595-6453be3f7070?auto=format&fit=crop&w=800&q=70", initials: "+" },
    { name: "Sachini", img: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=800&q=70", initials: "S" },
    { name: "Isuru", img: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=800&q=70", initials: "I" },
    { name: "Galle", img: "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=800&q=70", initials: "G" },
  ];

  return (
    <div className="sl-card p-3">
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="fw-black" style={{ fontSize: 16 }}>Stories</div>
        <button className="btn btn-sm rounded-pill" style={{ background: "#e7f0fe", color: "#1877f2", fontWeight: 700, border: "none" }}>
          See All
        </button>
      </div>
      <div className="d-flex gap-2 overflow-auto pb-1">
        {stories.map((s, idx) => (
          <div key={s.name} className="sl-story">
            <img src={s.img} alt={s.name} />
            <div className="sl-story-ring">{s.initials}</div>
            <div className="sl-story-name">{s.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =====================================================
   COMPOSER
===================================================== */
export function Composer({ onDemoClick }) {
  return (
    <div className="sl-card p-3">
      <div className="d-flex gap-2 align-items-center">
        <div className="sl-avatar-circle">TS</div>
        <button
          className="btn sl-compose flex-grow-1 text-start rounded-pill"
          onClick={onDemoClick}
          style={{ height: 42, paddingLeft: 16, color: "#65676b", fontWeight: 600 }}
        >
          මොකක්ද අලුත් කතාව?
        </button>
      </div>
      <hr className="my-3" style={{ borderColor: "#e4e6ea" }} />
      <div className="d-flex gap-2 flex-wrap">
        <ComposerBtn icon="bi-camera-video-fill" text="Live Video" color="#f02849" />
        <ComposerBtn icon="bi-images" text="ඡායාරූප/වීඩියෝ" color="#45bd62" />
        <ComposerBtn icon="bi-emoji-smile-fill" text="Feeling" color="#f7b928" />
        <span className="badge text-bg-warning ms-auto align-self-center">Hardcoded demo</span>
      </div>
    </div>
  );
}

function ComposerBtn({ icon, text, color }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      className="btn rounded-pill fw-bold d-flex align-items-center gap-2"
      style={{
        background: hover ? "#f0f2f5" : "transparent",
        border: "none",
        color: "#65676b",
        fontSize: 14,
        transition: "background 0.18s",
        padding: "6px 14px",
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <i className={`bi ${icon}`} style={{ color, fontSize: 18 }} />
      {text}
    </button>
  );
}

/* =====================================================
   POST CARD  — ✅ all backend props unchanged
===================================================== */
export function PostCard({
  post,
  commentValue,
  onLike,
  onShare,
  onCommentChange,
  onSendComment,
  onCommentClick,
}) {
  const [liked, setLiked] = useState(false);

  const handleLike = () => {
    setLiked((v) => !v);
    onLike?.();
  };

  return (
    <div className="sl-card p-3">
      {/* Header */}
      <div className="d-flex gap-2 align-items-center">
        <img className="sl-avatar" src={post.avatar} alt={post.author} loading="lazy" />
        <div className="flex-grow-1">
          <div className="d-flex align-items-center gap-2">
            <div className="fw-black" style={{ fontSize: 15 }}>{post.author}</div>
            {post.verified && (
              <i className="bi bi-patch-check-fill sl-verified" style={{ color: "#1877f2", fontSize: 15 }} />
            )}
          </div>
          <div className="sl-tiny" style={{ color: "#65676b" }}>
            {post.time} • {post.location} &nbsp;
            <i className="bi bi-globe2" />
          </div>
        </div>
        <button className="btn btn-light rounded-circle" style={{ width: 34, height: 34, padding: 0 }}>
          <i className="bi bi-three-dots" />
        </button>
      </div>

      {/* Text */}
      <div className="mt-2" style={{ lineHeight: 1.6, fontSize: 15 }}>{post.text}</div>

      {/* Image */}
      {post.images?.length ? (
        <div className="mt-2 sl-media">
          <img src={post.images[0]} alt="post" loading="lazy" />
        </div>
      ) : null}

      {/* Stats row */}
      <div
        className="d-flex justify-content-between sl-tiny mt-2"
        style={{ color: "#65676b", padding: "4px 0" }}
      >
        <div className="d-flex align-items-center gap-1">
          <span
            style={{
              background: "#1877f2", color: "#fff",
              width: 18, height: 18, borderRadius: "50%",
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              fontSize: 10,
            }}
          >
            <i className="bi bi-hand-thumbs-up-fill" />
          </span>
          <span style={{ fontWeight: 600 }}>{liked ? post.likes + 1 : post.likes}</span>
        </div>
        <div className="d-flex gap-3">
          <span>{post.comments.length} Comments</span>
          <span>{post.shares} Shares</span>
        </div>
      </div>

      <hr className="my-2" style={{ borderColor: "#e4e6ea" }} />

      {/* Actions */}
      <div className="d-flex gap-1">
        <ActionBtn
          icon={liked ? "bi-hand-thumbs-up-fill" : "bi-hand-thumbs-up"}
          text="Like"
          onClick={handleLike}
          active={liked}
        />
        <ActionBtn
          icon="bi-chat-square-text"
          text="Comment"
          onClick={() => document.getElementById(`c-${post.id}`)?.focus()}
        />
        <ActionBtn icon="bi-share" text="Share" onClick={onShare} />
      </div>

      <hr className="my-2" style={{ borderColor: "#e4e6ea" }} />

      {/* Comments */}
      <div className="d-flex flex-column gap-2">
        {post.comments.map((c) => (
          <CommentItem
            key={c.id}
            name={c.name}
            text={c.text}
            analysis={c.analysis}
            onClick={() => onCommentClick?.(c)}
          />
        ))}
      </div>

      {/* Comment input */}
      <div className="d-flex gap-2 mt-3 align-items-center">
        <div className="sl-avatar-circle" style={{ width: 32, height: 32, fontSize: 12 }}>TS</div>
        <input
          id={`c-${post.id}`}
          className="form-control sl-comment"
          placeholder="කමෙන්ට් එකක් දාන්න…"
          value={commentValue}
          onChange={(e) => onCommentChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onSendComment(); }}
        />
        <button
          className="btn btn-primary fw-bold rounded-pill sl-ripple"
          onClick={onSendComment}
          style={{ padding: "6px 18px", fontSize: 14 }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

/* =====================================================
   SMALL UI BITS
===================================================== */

function Card({ title, children }) {
  return (
    <div className="sl-card p-3">
      <div className="fw-black mb-2" style={{ fontSize: 15, color: "#1c1e21" }}>{title}</div>
      <div className="d-flex flex-column gap-1">{children}</div>
    </div>
  );
}

function MenuItem({ icon, text, active }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      className="btn text-start sl-menuitem d-flex align-items-center gap-2"
      style={{
        background: active || hover ? "#e7f0fe" : "transparent",
        color: active || hover ? "#1877f2" : "#1c1e21",
      }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <i className={`bi ${icon}`} style={{ color: active || hover ? "#1877f2" : "#65676b", fontSize: 17 }} />
      <span style={{ fontWeight: active ? 700 : 600 }}>{text}</span>
    </button>
  );
}

function HashItem({ tag, meta, count }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      className="sl-hash d-flex justify-content-between align-items-center"
      style={{ background: hover ? "#f0f2f5" : "transparent" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div>
        <div className="fw-bold" style={{ fontSize: 14, color: "#1877f2" }}>{tag}</div>
        <div className="sl-tiny text-muted">{meta}</div>
      </div>
      <div className="d-flex align-items-center gap-2">
        {count && <span className="sl-tiny text-muted">{count} posts</span>}
        <i className="bi bi-chevron-right text-muted" style={{ fontSize: 11 }} />
      </div>
    </div>
  );
}

function FriendRow({ name, sub }) {
  const [hover, setHover] = useState(false);
  return (
    <div
      className="sl-friend d-flex align-items-center gap-2"
      style={{ background: hover ? "#f0f2f5" : "transparent" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <span className="sl-dot" />
      <div>
        <div className="fw-bold" style={{ fontSize: 13 }}>{name}</div>
        {sub && <div className="sl-tiny text-muted">{sub}</div>}
      </div>
    </div>
  );
}

function ActionBtn({ icon, text, onClick, active }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      className="btn sl-action-btn w-100 d-flex align-items-center justify-content-center gap-2 sl-ripple"
      style={{
        background: active || hover ? "#e7f0fe" : "transparent",
        color: active || hover ? "#1877f2" : "#65676b",
        fontWeight: 700,
      }}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <i className={`bi ${icon}`} style={{ fontSize: 17 }} />
      <span style={{ fontSize: 14 }}>{text}</span>
    </button>
  );
}

function CommentItem({ name, text, analysis, onClick }) {
  const pred = analysis?.prediction;
  const moderation = analysis?.moderation || {};
  const action = (moderation?.action || "").toUpperCase();

  let statusClass = "sl-status-pending";
  let statusLabel = "⏳ Pending";

  if (analysis) {
    if (pred === "ERROR") {
      statusClass = "sl-status-error";
      statusLabel = "❌ ERROR";
    } else if (action === "BLOCK") {
      statusClass = "sl-status-hate";
      statusLabel = "🚫 BLOCK";
    } else if (action === "FLAG") {
      statusClass = "sl-status-disinfo";
      statusLabel = "⚠️ FLAG";
    } else if (action === "REVIEW" || action === "WARN") {
      statusClass = "sl-status-disinfo";
      statusLabel = `🟠 ${action}`;
    } else if (pred === "HATE") {
      statusClass = "sl-status-hate";
      statusLabel = "🚫 HATE";
    } else if (pred === "DISINFO") {
      statusClass = "sl-status-disinfo";
      statusLabel = "⚠️ DISINFO";
    } else if (pred === "NORMAL") {
      statusClass = "sl-status-normal";
      statusLabel = "✅ NORMAL";
    }
  }

  return (
    <div className="d-flex gap-2 align-items-start sl-comment-new">
      <div className="sl-mini-avatar">{(name || "U").slice(0, 1).toUpperCase()}</div>
      <div
        className="sl-bubble flex-grow-1"
        role="button"
        style={{ cursor: "pointer" }}
        title="Click to open analysis"
        onClick={onClick}
      >
        <div className="d-flex justify-content-between align-items-center gap-2">
          <div className="fw-black sl-tiny" style={{ color: "#1c1e21" }}>
            {name}
          </div>
          <span className={`sl-status ${statusClass}`}>{statusLabel}</span>
        </div>

        <div style={{ fontSize: 14, marginTop: 2 }}>{text}</div>

        {analysis?.moderation?.reason ? (
          <div
            className="sl-tiny"
            style={{ color: "#65676b", marginTop: 6, lineHeight: 1.4 }}
          >
            {analysis.moderation.reason}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/* =====================================================
   TOAST
===================================================== */
export function ToastMsg({ toast, onClose }) {
  const styleMap = {
    warning: { background: "#ffaa00", color: "#1c1e21" },
    info: { background: "#1877f2", color: "#fff" },
    success: { background: "#42b72a", color: "#fff" },
  };
  const s = styleMap[toast.type] || styleMap.success;

  return (
    <div className="position-fixed bottom-0 end-0 p-3" style={{ zIndex: 9999 }}>
      <div
        className="d-flex align-items-center gap-3 rounded-3 px-4 py-3"
        style={{
          ...s,
          boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
          fontWeight: 700,
          fontSize: 14,
          minWidth: 260,
          animation: "slideInComment 0.25s ease both",
        }}
      >
        <span className="flex-grow-1">{toast.text}</span>
        <button
          style={{ background: "none", border: "none", color: "inherit", fontSize: 18, cursor: "pointer", lineHeight: 1 }}
          onClick={onClose}
        >
          ×
        </button>
      </div>
    </div>
  );
}

/* =====================================================
   ANALYSIS DRAWER — ✅ backend logic untouched
===================================================== */
export function AnalysisDrawer({ open, payload, onClose }) {
  const analysis = payload?.analysis || null;
  const text = payload?.text || "";

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const pred = analysis?.prediction || "—";
  const probs = analysis?.probs || {};
  const moderation = analysis?.moderation || {};
  const xai = analysis?.xai_sentence || "";
  const cleaned = analysis?.cleaned || "";
  const original = analysis?.original || text || "";
  const highlightHtml = analysis?.highlight_html || "";
  const rawSuggestions = Array.isArray(analysis?.suggestions) ? analysis.suggestions : [];

  const normalizedSuggestions = rawSuggestions
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") return item.suggestion || item.text || JSON.stringify(item);
      return "";
    })
    .filter(Boolean);

  const moderationAction = (moderation?.action || "").toUpperCase() || "N/A";
  const moderationSeverity = (moderation?.severity || "").toUpperCase() || "LOW";
  const moderationReason = moderation?.reason || "No moderation reason available.";
  const moderationConfidence =
    moderation?.confidence != null
      ? `${(Number(moderation.confidence) * 100).toFixed(2)}%`
      : probs[pred] != null
      ? `${(Number(probs[pred]) * 100).toFixed(2)}%`
      : "—";

  const showSuggestions =
    ["HATE", "DISINFO", "ERROR"].includes(pred) ||
    ["BLOCK", "FLAG", "REVIEW", "WARN"].includes(moderationAction);

  let badgeColor = "#8a8d91";
  let badgeTextColor = "#fff";

  if (pred === "HATE") badgeColor = "#ff4444";
  else if (pred === "DISINFO") {
    badgeColor = "#ffaa00";
    badgeTextColor = "#1c1e21";
  } else if (pred === "NORMAL") badgeColor = "#42b72a";
  else if (pred === "ERROR") badgeColor = "#1c1e21";

  let actionColor = "#8a8d91";
  let actionTextColor = "#fff";

  if (moderationAction === "BLOCK") actionColor = "#dc3545";
  else if (moderationAction === "FLAG") {
    actionColor = "#f59e0b";
    actionTextColor = "#1c1e21";
  } else if (moderationAction === "REVIEW" || moderationAction === "WARN") {
    actionColor = "#ffb020";
    actionTextColor = "#1c1e21";
  } else if (moderationAction === "ALLOW" || moderationAction === "ALLOW_WITH_LOG") {
    actionColor = "#42b72a";
  }

  const copy = async (value) => {
    try {
      await navigator.clipboard.writeText(value || "");
    } catch {}
  };

  return (
    <>
      <div
        onClick={onClose}
        style={{
          display: open ? "block" : "none",
          position: "fixed",
          inset: 0,
          background: "rgba(0,0,0,0.5)",
          zIndex: 9998,
          backdropFilter: "blur(2px)",
        }}
      />

      <div
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          height: "100vh",
          width: "min(560px, 94vw)",
          transform: open ? "translateX(0)" : "translateX(-110%)",
          transition: "transform 220ms cubic-bezier(0.25,0.46,0.45,0.94)",
          background: "#fff",
          zIndex: 9999,
          boxShadow: "4px 0 40px rgba(0,0,0,0.18)",
          display: "flex",
          flexDirection: "column",
          fontFamily: "'Nunito', sans-serif",
        }}
      >
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #e4e6ea",
            background: "linear-gradient(135deg, #f0f4ff 0%, #fff 100%)",
          }}
        >
          <div className="d-flex align-items-start justify-content-between gap-2">
            <div>
              <div style={{ fontSize: 20, fontWeight: 900, color: "#1c1e21" }}>
                🔍 XAI + Moderation Panel
              </div>
              <div style={{ fontSize: 12, color: "#65676b", marginTop: 2 }}>
                Comment analysis • Prediction + moderation + explanation
              </div>
            </div>

            <button
              className="btn btn-light rounded-circle"
              onClick={onClose}
              style={{ width: 36, height: 36, padding: 0, fontSize: 16 }}
            >
              <i className="bi bi-x-lg" />
            </button>
          </div>

          <div className="mt-3 d-flex align-items-center gap-2 flex-wrap">
            <span
              style={{
                background: badgeColor,
                color: badgeTextColor,
                fontWeight: 900,
                fontSize: 14,
                padding: "8px 16px",
                borderRadius: 20,
                boxShadow: `0 2px 8px ${badgeColor}55`,
                letterSpacing: 0.5,
              }}
            >
              Prediction: {pred}
            </span>

            <span
              style={{
                background: actionColor,
                color: actionTextColor,
                fontWeight: 900,
                fontSize: 14,
                padding: "8px 16px",
                borderRadius: 20,
                boxShadow: `0 2px 8px ${actionColor}33`,
                letterSpacing: 0.5,
              }}
            >
              Action: {moderationAction}
            </span>

            <span
              style={{
                background: "#eef2f7",
                color: "#1c1e21",
                fontWeight: 800,
                fontSize: 13,
                padding: "8px 14px",
                borderRadius: 20,
              }}
            >
              Severity: {moderationSeverity}
            </span>

            <span
              style={{
                background: "#f8f9fa",
                color: "#1c1e21",
                fontWeight: 800,
                fontSize: 13,
                padding: "8px 14px",
                borderRadius: 20,
                border: "1px solid #e4e6ea",
              }}
            >
              Confidence: {moderationConfidence}
            </span>

            {pred === "ERROR" && (
              <span
                style={{
                  background: "#1c1e21",
                  color: "#fff",
                  fontSize: 12,
                  padding: "8px 12px",
                  borderRadius: 20,
                  fontWeight: 700,
                }}
              >
                {analysis?.error || "API error"}
              </span>
            )}
          </div>

          <div className="mt-3">
            <div style={{ fontSize: 12, color: "#65676b", marginBottom: 6, fontWeight: 700 }}>
              Input Comment
            </div>
            <div
              style={{
                background: "#f8f9fa",
                border: "1px solid #e4e6ea",
                borderRadius: 10,
                padding: "10px 14px",
                fontSize: 14,
                lineHeight: 1.6,
                color: "#1c1e21",
              }}
            >
              {text || "—"}
            </div>
          </div>

          <div className="mt-2 d-flex gap-2 flex-wrap">
            <button
              onClick={() => copy(xai)}
              style={{
                border: "2px solid #1877f2",
                color: "#1877f2",
                background: "transparent",
                borderRadius: 20,
                padding: "4px 14px",
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.18s",
              }}
              onMouseEnter={(e) => {
                e.target.style.background = "#1877f2";
                e.target.style.color = "#fff";
              }}
              onMouseLeave={(e) => {
                e.target.style.background = "transparent";
                e.target.style.color = "#1877f2";
              }}
            >
              📋 Copy Summary
            </button>

            <button
              onClick={() => copy(cleaned || text)}
              style={{
                border: "2px solid #65676b",
                color: "#65676b",
                background: "transparent",
                borderRadius: 20,
                padding: "4px 14px",
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.18s",
              }}
              onMouseEnter={(e) => {
                e.target.style.background = "#65676b";
                e.target.style.color = "#fff";
              }}
              onMouseLeave={(e) => {
                e.target.style.background = "transparent";
                e.target.style.color = "#65676b";
              }}
            >
              📝 Copy Cleaned
            </button>

            <button
              onClick={() => copy(original || text)}
              style={{
                border: "2px solid #42b72a",
                color: "#42b72a",
                background: "transparent",
                borderRadius: 20,
                padding: "4px 14px",
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 0.18s",
              }}
              onMouseEnter={(e) => {
                e.target.style.background = "#42b72a";
                e.target.style.color = "#fff";
              }}
              onMouseLeave={(e) => {
                e.target.style.background = "transparent";
                e.target.style.color = "#42b72a";
              }}
            >
              📄 Copy Original
            </button>
          </div>
        </div>

        <div style={{ padding: 20, overflow: "auto", flex: 1 }}>
          <Tabs
            tabs={[
              {
                title: "📄 Summary",
                content: (
                  <>
                    <SectionTitle>Moderation Decision</SectionTitle>
                    <div
                      style={{
                        background: "#fff8e8",
                        border: "1px solid #f3d48a",
                        borderRadius: 10,
                        padding: "12px 16px",
                        lineHeight: 1.7,
                        fontSize: 14,
                        color: "#1c1e21",
                      }}
                    >
                      <div><strong>Action:</strong> {moderationAction}</div>
                      <div><strong>Severity:</strong> {moderationSeverity}</div>
                      <div><strong>Confidence:</strong> {moderationConfidence}</div>
                      <div style={{ marginTop: 8 }}>
                        <strong>Reason:</strong> {moderationReason}
                      </div>
                    </div>

                    <div className="mt-4">
                      <SectionTitle>Explainable Summary</SectionTitle>
                      <div
                        style={{
                          background: "#f0f4ff",
                          border: "1px solid #c7d7fd",
                          borderRadius: 10,
                          padding: "12px 16px",
                          lineHeight: 1.7,
                          fontSize: 14,
                          color: "#1c1e21",
                        }}
                      >
                        {xai || "—"}
                      </div>
                      <div style={{ fontSize: 11, color: "#65676b", marginTop: 6 }}>
                        Generated using LIME or backend explanation output.
                      </div>
                    </div>

                    <div className="mt-4">
                      <SectionTitle>Original Text</SectionTitle>
                      <div
                        style={{
                          background: "#f8f9fa",
                          border: "1px solid #e4e6ea",
                          borderRadius: 10,
                          padding: "10px 14px",
                          fontSize: 14,
                        }}
                      >
                        {original || "—"}
                      </div>
                    </div>

                    <div className="mt-4">
                      <SectionTitle>Cleaned Text</SectionTitle>
                      <div
                        style={{
                          background: "#f8f9fa",
                          border: "1px solid #e4e6ea",
                          borderRadius: 10,
                          padding: "10px 14px",
                          fontSize: 14,
                        }}
                      >
                        {cleaned || "—"}
                      </div>
                    </div>
                  </>
                ),
              },
              {
                title: "📊 Probabilities",
                content: (
                  <>
                    <SectionTitle>Model Probabilities</SectionTitle>

                    {Object.keys(probs).length === 0 ? (
                      <div style={{ color: "#65676b", fontSize: 14 }}>No probabilities available.</div>
                    ) : (
                      <div className="d-flex flex-column gap-3">
                        {Object.entries(probs).map(([label, value]) => {
                          const percent = (Number(value) * 100).toFixed(2);
                          const barColor =
                            label === "HATE"
                              ? "#ff4444"
                              : label === "DISINFO"
                              ? "#ffaa00"
                              : "#42b72a";

                          return (
                            <div key={label}>
                              <div className="d-flex justify-content-between mb-1">
                                <div style={{ fontWeight: 800, fontSize: 13 }}>{label}</div>
                                <div style={{ fontSize: 13, color: "#65676b" }}>{percent}%</div>
                              </div>
                              <div
                                style={{
                                  width: "100%",
                                  height: 12,
                                  background: "#e9ecef",
                                  borderRadius: 999,
                                  overflow: "hidden",
                                }}
                              >
                                <div
                                  style={{
                                    width: `${percent}%`,
                                    height: "100%",
                                    background: barColor,
                                    borderRadius: 999,
                                    transition: "width 0.3s ease",
                                  }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </>
                ),
              },
              {
                title: "🎨 Highlight",
                content: (
                  <>
                    <SectionTitle>Token Importance (LIME)</SectionTitle>
                    <div
                      style={{
                        background: "#fafafa",
                        border: "1px solid #e4e6ea",
                        borderRadius: 10,
                        padding: "12px 16px",
                        lineHeight: 2.2,
                        fontSize: 15,
                      }}
                      dangerouslySetInnerHTML={{
                        __html: highlightHtml || "<span style='color:#65676b'>No highlighted output.</span>",
                      }}
                    />
                    <div style={{ fontSize: 11, color: "#65676b", marginTop: 8 }}>
                      Highlighting is based on the cleaned text used by the model.
                    </div>
                  </>
                ),
              },
              {
                title: "💡 Suggestions",
                content: (
                  <>
                    <SectionTitle>Rewrite Suggestions</SectionTitle>

                    {!showSuggestions ? (
                      <div
                        style={{
                          background: "#f0fff4",
                          border: "1px solid #c3f7cc",
                          borderRadius: 10,
                          padding: "12px 16px",
                          fontSize: 14,
                          color: "#155111",
                        }}
                      >
                        ✅ Safe content — no rewrite suggestions needed.
                      </div>
                    ) : normalizedSuggestions.length > 0 ? (
                      <div className="d-flex flex-column gap-2">
                        {normalizedSuggestions.map((s, idx) => (
                          <div
                            key={idx}
                            style={{
                              background: "#fff",
                              border: "1px solid #e4e6ea",
                              borderRadius: 10,
                              padding: "12px 16px",
                              fontSize: 14,
                              lineHeight: 1.6,
                              borderLeft: "4px solid #42b72a",
                              boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
                            }}
                          >
                            <span
                              style={{
                                fontSize: 11,
                                fontWeight: 700,
                                color: "#42b72a",
                                display: "block",
                                marginBottom: 4,
                              }}
                            >
                              Suggestion {idx + 1}
                            </span>
                            {s}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ color: "#65676b", fontSize: 14 }}>
                        No suggestions available.
                      </div>
                    )}
                  </>
                ),
              },
            ]}
          />
        </div>

        <div
          style={{
            padding: "14px 20px",
            borderTop: "1px solid #e4e6ea",
            background: "#fafafa",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ fontSize: 12, color: "#65676b" }}>
            <i className="bi bi-keyboard me-1" /> ESC or click outside to close
          </div>

          <button
            className="btn btn-primary rounded-pill fw-bold sl-ripple"
            onClick={onClose}
            style={{ padding: "8px 24px" }}
          >
            Done
          </button>
        </div>
      </div>
    </>
  );
}

/* --------- Tabs ---------- */
function Tabs({ tabs }) {
  const [active, setActive] = useState(0);
  const safeTabs = Array.isArray(tabs) ? tabs : [];

  return (
    <div>
      <div
        className="d-flex gap-2 flex-wrap"
        style={{
          marginBottom: 16,
          background: "#f0f2f5",
          borderRadius: 12,
          padding: 4,
        }}
      >
        {safeTabs.map((t, idx) => (
          <button
            key={idx}
            onClick={() => setActive(idx)}
            style={{
              border: "none",
              borderRadius: 10,
              padding: "6px 16px",
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.18s",
              background: active === idx ? "#1877f2" : "transparent",
              color: active === idx ? "#fff" : "#65676b",
              boxShadow: active === idx ? "0 2px 8px rgba(24,119,242,0.3)" : "none",
            }}
          >
            {t.title}
          </button>
        ))}
      </div>
      <div>{safeTabs[active]?.content || null}</div>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <div
      style={{
        fontWeight: 900, fontSize: 13, color: "#65676b",
        textTransform: "uppercase", letterSpacing: 0.8,
        marginBottom: 8,
      }}
    >
      {children}
    </div>
  );

}

export function ModerationStatsChart({ posts = [] }) {
  const allComments = posts.flatMap((post) => post.comments || []);

  const stats = {
    BLOCK: 0,
    FLAG: 0,
    REVIEW: 0,
    WARN: 0,
    ALLOW: 0,
    ALLOW_WITH_LOG: 0,
    ERROR: 0,
    PENDING: 0,
  };

  allComments.forEach((comment) => {
    if (!comment.analysis) {
      stats.PENDING += 1;
      return;
    }

    if (comment.analysis.prediction === "ERROR") {
      stats.ERROR += 1;
      return;
    }

    const action = comment.analysis?.moderation?.action || "ALLOW";
    if (stats[action] !== undefined) {
      stats[action] += 1;
    } else {
      stats.ALLOW += 1;
    }
  });

  const data = [
    { name: "BLOCK", value: stats.BLOCK, color: "#dc3545" },
    { name: "FLAG", value: stats.FLAG, color: "#f59e0b" },
    { name: "REVIEW", value: stats.REVIEW, color: "#ffb020" },
    { name: "WARN", value: stats.WARN, color: "#ffd166" },
    { name: "ALLOW", value: stats.ALLOW, color: "#42b72a" },
    { name: "ALLOW_LOG", value: stats.ALLOW_WITH_LOG, color: "#66bb6a" },
    { name: "ERROR", value: stats.ERROR, color: "#6c757d" },
    { name: "PENDING", value: stats.PENDING, color: "#adb5bd" },
  ];

  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <div className="sl-card p-3">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div className="fw-black" style={{ fontSize: 16 }}>
          Moderation Statistics
        </div>
        <span className="badge text-bg-primary">
          Total Comments: {total}
        </span>
      </div>

      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" radius={[8, 8, 0, 0]}>
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="row g-2 mt-2">
        {data.map((item) => (
          <div key={item.name} className="col-6 col-md-3">
            <div
              style={{
                border: "1px solid #e4e6ea",
                borderRadius: 10,
                padding: "10px 12px",
                background: "#fff",
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  color: "#65676b",
                  marginBottom: 4,
                }}
              >
                {item.name}
              </div>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 900,
                  color: item.color,
                }}
              >
                {item.value}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

