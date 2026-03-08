import { useMemo, useState } from "react";
import {
  TopBar,
  LeftMenu,
  RightPanel,
  Composer,
  PostCard,
  StoryRow,
  ToastMsg,
  AnalysisDrawer,
} from "../ui/SLBook.jsx";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:5000";

export default function Home() {
  const initialPosts = useMemo(
    () => [
      {
        id: "p1",
        author: "Thamindu S.",
        verified: false,
        time: "අද • 8:10 PM",
        location: "Colombo",
        avatar:
          "https://images.unsplash.com/photo-1520975661595-6453be3f7070?auto=format&fit=crop&w=160&q=60",
        images: [
          "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=70",
        ],
        text: "අද වැස්සත් එක්ක කොත්තු කෑවම මාර සතුටක් 😍🍛",
        likes: 5,
        shares: 1,
        comments: [],
      },
      {
        id: "p2",
        author: "Sachini",
        verified: true,
        time: "ඊයේ • 6:20 PM",
        location: "Kandy",
        avatar:
          "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=160&q=60",
        images: [
          "https://images.unsplash.com/photo-1543248939-4296e1fea89b?auto=format&fit=crop&w=1200&q=70",
        ],
        text: "කැම්පස් assignment ටික දැන් වැඩි වෙලා 😅 deadline එක එනවා!",
        likes: 11,
        shares: 0,
        comments: [],
      },
      {
        id: "p3",
        author: "Isuru Perera",
        verified: false,
        time: "පසුගියදා • 3:05 PM",
        location: "Galle",
        avatar:
          "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=160&q=60",
        images: [
          "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1200&q=70",
        ],
        text: "ගාලු beach vibe එක 🔥🌊 හුළඟත් එක්ක පට්ටයි.",
        likes: 7,
        shares: 2,
        comments: [],
      },
    ],
    []
  );

  const [posts, setPosts] = useState(initialPosts);
  const [draftComments, setDraftComments] = useState({});
  const [toast, setToast] = useState(null);

  // ✅ left-side popup state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerPayload, setDrawerPayload] = useState(null); // { text, analysis, postId, commentId }

  const likePost = (postId) => {
    // UI-only micro-interaction: add a tiny "pulse" marker (doesn't change logic)
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId
          ? { ...p, likes: p.likes + 1, __likePulse: (p.__likePulse || 0) + 1 }
          : p
      )
    );
  };

  const sharePost = (postId) => {
    setPosts((prev) =>
      prev.map((p) =>
        p.id === postId
          ? { ...p, shares: p.shares + 1, __sharePulse: (p.__sharePulse || 0) + 1 }
          : p
      )
    );
    setToast({ type: "info", text: "Share (demo) ✅ — research UI only." });
  };

  const changeComment = (postId, value) => {
    setDraftComments((prev) => ({ ...prev, [postId]: value }));
  };

  async function analyzeTextWithFlask(text) {
    const res = await fetch(`${API_BASE}/api/explain_lime`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!res.ok) {
      const t = await res.text().catch(() => "");
      throw new Error(`Flask API error ${res.status}: ${t || "no body"}`);
    }
    return res.json();
  }

  // ✅ open drawer helper
  const openDrawer = ({ postId, commentId, text, analysis }) => {
    setDrawerPayload({ postId, commentId, text, analysis });
    setDrawerOpen(true);
  };

  const sendComment = async (postId) => {
    const text = (draftComments[postId] || "").trim();
    if (!text) return;

    const commentId = crypto.randomUUID();

    // add comment immediately (same behavior)
    setPosts((prev) =>
      prev.map((p) => {
        if (p.id !== postId) return p;
        return {
          ...p,
          comments: [
            ...p.comments,
            { id: commentId, name: "ඔයා", text, analysis: null },
          ],
        };
      })
    );
    setDraftComments((prev) => ({ ...prev, [postId]: "" }));

    // call Flask
    try {
      const result = await analyzeTextWithFlask(text);

      // attach analysis to comment in state
      setPosts((prev) =>
        prev.map((p) => {
          if (p.id !== postId) return p;
          return {
            ...p,
            comments: p.comments.map((c) =>
              c.id === commentId ? { ...c, analysis: result } : c
            ),
          };
        })
      );

      // ✅ auto-open left panel with the result (1st impression)
      openDrawer({ postId, commentId, text, analysis: result });
    } catch (e) {
      const errorAnalysis = {
        prediction: "ERROR",
        probs: {},
        xai_sentence: "API error",
        highlight_html: "",
        suggestions: [],
        cleaned: "",
        original: text,
        error: e?.message || "unknown",
      };

      setPosts((prev) =>
        prev.map((p) => {
          if (p.id !== postId) return p;
          return {
            ...p,
            comments: p.comments.map((c) =>
              c.id === commentId ? { ...c, analysis: errorAnalysis } : c
            ),
          };
        })
      );

      openDrawer({ postId, commentId, text, analysis: errorAnalysis });

      setToast({
        type: "warning",
        text: `Model API error ❌ (${e?.message || "unknown"})`,
      });
    }
  };

  // ✅ open drawer when user clicks a comment (interactive)
  const onCommentClick = (postId, comment) => {
    if (!comment?.analysis) {
      setToast({ type: "warning", text: "මේ comment එකට analysis තාම නැහැ." });
      return;
    }
    openDrawer({
      postId,
      commentId: comment.id,
      text: comment.text,
      analysis: comment.analysis,
    });
  };

  return (
    <div className="slbg min-vh-100 sl-fade-in">
      <TopBar />

      <div className="container-fluid sl-container my-3">
        <div className="row g-3 align-items-start">
          <div className="col-12 col-lg-3">
            <LeftMenu />
          </div>

          <div className="col-12 col-lg-6">
            <StoryRow />

            <div className="mt-3">
              <Composer
                onDemoClick={() =>
                  setToast({ type: "warning", text: "Composer එක demo එකක් 😄" })
                }
              />
            </div>

            <div className="d-flex flex-column gap-3 mt-3">
              {posts.map((post) => (
                <PostCard
                  key={post.id}
                  post={post}
                  commentValue={draftComments[post.id] || ""}
                  onLike={() => likePost(post.id)}
                  onShare={() => sharePost(post.id)}
                  onCommentChange={(v) => changeComment(post.id, v)}
                  onSendComment={() => sendComment(post.id)}
                  onCommentClick={(comment) => onCommentClick(post.id, comment)}
                />
              ))}
            </div>
          </div>

          <div className="col-12 col-lg-3">
            <RightPanel />
          </div>
        </div>
      </div>

      {toast && <ToastMsg toast={toast} onClose={() => setToast(null)} />}

      {/* ✅ Left-side popup */}
      <AnalysisDrawer
        open={drawerOpen}
        payload={drawerPayload}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
