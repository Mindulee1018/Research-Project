import { useState } from "react";
import Home from "./pages/Home";
import Statistics from "./pages/Statistics";

function App() {

  const [page, setPage] = useState("home");
  const [posts, setPosts] = useState([]);

  if (page === "stats") {
    return (
      <Statistics
        posts={posts}
        goHome={() => setPage("home")}
      />
    );
  }

  return (
    <Home
      posts={posts}
      setPosts={setPosts}
      openStats={() => setPage("stats")}
    />
  );
}

export default App;