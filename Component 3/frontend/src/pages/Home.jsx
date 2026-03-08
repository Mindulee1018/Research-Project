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
  ModerationStatsChart,
} from "../ui/SLBook.jsx";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:5000").replace(/\/$/, "");

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

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerPayload, setDrawerPayload] = useState(null);

  const likePost = (postId) => {
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

  function normalizeAnalysisResponse(raw, text) {
    const probs = raw?.probs || {
      HATE: 0,
      DISINFO: 0,
      NORMAL: 0,
    };

    const prediction = raw?.prediction || "UNKNOWN";

    const moderation = raw?.moderation || {
      action: prediction === "HATE" ? "REVIEW" : prediction === "DISINFO" ? "FLAG" : "ALLOW",
      severity: prediction === "NORMAL" ? "LOW" : "MEDIUM",
      confidence: Number(probs[prediction] || 0),
      reason: raw?.reason || "Moderation result generated from prediction.",
    };

    return {
      original: raw?.original || text,
      cleaned: raw?.cleaned || text,
      prediction,
      probs,
      moderation,
      xai_sentence: raw?.xai_sentence || "No explanation generated.",
      highlight_html: raw?.highlight_html || "",
      suggestions: Array.isArray(raw?.suggestions) ? raw.suggestions : [],
      error: raw?.error || null,
    };
  }

  async function analyzeTextWithFlask(text) {
    const payload = { text };

    const endpoints = [
      `${API_BASE}/api/explain_lime`,
      `${API_BASE}/analyze`,
    ];

    let lastError = null;

    for (const url of endpoints) {
      try {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const msg = await res.text().catch(() => "");
          lastError = new Error(`Flask API error ${res.status}: ${msg || "no body"}`);
          continue;
        }

        const data = await res.json();
        return normalizeAnalysisResponse(data, text);
      } catch (err) {
        lastError = err;
      }
    }

    throw lastError || new Error("Could not connect to backend.");
  }

  const openDrawer = ({ postId, commentId, text, analysis }) => {
    setDrawerPayload({ postId, commentId, text, analysis });
    setDrawerOpen(true);
  };

  const sendComment = async (postId) => {
    const text = (draftComments[postId] || "").trim();
    if (!text) return;

    const commentId = crypto.randomUUID();

    setPosts((prev) =>
      prev.map((p) => {
        if (p.id !== postId) return p;
        return {
          ...p,
          comments: [
            ...p.comments,
            {
              id: commentId,
              name: "ඔයා",
              text,
              analysis: null,
              status: "loading",
            },
          ],
        };
      })
    );

    setDraftComments((prev) => ({ ...prev, [postId]: "" }));

    try {
      const result = await analyzeTextWithFlask(text);

      setPosts((prev) =>
        prev.map((p) => {
          if (p.id !== postId) return p;
          return {
            ...p,
            comments: p.comments.map((c) =>
              c.id === commentId
                ? {
                    ...c,
                    analysis: result,
                    status: "done",
                  }
                : c
            ),
          };
        })
      );

      openDrawer({ postId, commentId, text, analysis: result });

      setToast({
        type: "success",
        text: `Analysis completed: ${result.prediction} / ${result.moderation?.action || "DONE"}`,
      });
    } catch (e) {
      const errorAnalysis = {
        original: text,
        cleaned: text,
        prediction: "ERROR",
        probs: { HATE: 0, DISINFO: 0, NORMAL: 0 },
        moderation: {
          action: "REVIEW",
          severity: "LOW",
          confidence: 0,
          reason: "Backend connection failed.",
        },
        xai_sentence: "API error",
        highlight_html: "",
        suggestions: [],
        error: e?.message || "unknown",
      };

      setPosts((prev) =>
        prev.map((p) => {
          if (p.id !== postId) return p;
          return {
            ...p,
            comments: p.comments.map((c) =>
              c.id === commentId
                ? {
                    ...c,
                    analysis: errorAnalysis,
                    status: "error",
                  }
                : c
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

            <div className="mt-3">
              <ModerationStatsChart posts={posts} />
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

      <AnalysisDrawer
        open={drawerOpen}
        payload={drawerPayload}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}