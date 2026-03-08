import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "http://127.0.0.1:8002",
});

export async function fetchStats() {
  const res = await api.get("/stats");
  return res.data;
}

export async function fetchTopRisk(k = 20) {
  const res = await api.get("/risk/top", { params: { k } });
  return res.data.rows;
}

export async function fetchTopQueue(k = 20) {
  const res = await api.get("/queue/top", { params: { k } });
  return res.data.rows;
}

export async function fetchTopCommunities(k = 20) {
  const res = await api.get("/communities/top", { params: { k } });
  return res.data.rows;
}

export async function fetchNetworkGraph(k = 25, neighborLimit = 3) {
  const res = await api.get("/graph/sample", {
    params: { k, neighbor_limit: neighborLimit },
  });
  return res.data;
}