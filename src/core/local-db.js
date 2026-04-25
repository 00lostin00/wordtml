/**
 * 本地 SQLite 同步层。
 * 页面仍可用 IndexedDB 快速运行;本模块负责把关键个人记录落到 server.py 的 wordtml.db。
 */
const API_BASE = "/api";

export async function getLocalDbStatus() {
  return apiGet("/local/status");
}

export async function saveExamAttempt(attempt) {
  return apiPost("/exam-attempts", attempt);
}

export async function getExamAttempts(limit = 200) {
  const data = await apiGet(`/exam-attempts?limit=${encodeURIComponent(limit)}`);
  return data.items || [];
}

export async function savePracticeHistory(item) {
  return apiPost("/practice-history", item);
}

export async function getPracticeHistory(limit = 50) {
  const data = await apiGet(`/practice-history?limit=${encodeURIComponent(limit)}`);
  return data.items || [];
}

export async function tryGetExamAttempts(limit = 200) {
  try {
    return await getExamAttempts(limit);
  } catch {
    return [];
  }
}

export async function tryGetPracticeHistory(limit = 50) {
  try {
    return await getPracticeHistory(limit);
  } catch {
    return [];
  }
}

export async function trySaveExamAttempt(attempt) {
  try {
    return await saveExamAttempt(attempt);
  } catch (e) {
    console.warn("local db exam attempt sync failed", e);
    return null;
  }
}

export async function trySavePracticeHistory(item) {
  try {
    return await savePracticeHistory(item);
  } catch (e) {
    console.warn("local db practice history sync failed", e);
    return null;
  }
}

export function examAttemptKey(attempt) {
  return [
    attempt.mode || "exam",
    attempt.examId || "",
    attempt.practiceUnitId || "",
    attempt.startedAt || "",
    attempt.endedAt || "",
  ].join(":");
}

export async function trySyncExamAttempts(attempts) {
  const saved = [];
  for (const attempt of attempts || []) {
    const item = await trySaveExamAttempt({
      ...attempt,
      mode: attempt.mode || "exam",
      localDbKey: attempt.localDbKey || examAttemptKey(attempt),
    });
    if (item) saved.push(item);
  }
  return saved;
}

async function apiGet(path) {
  const res = await fetch(API_BASE + path, { cache: "no-store" });
  return parseApiResponse(res);
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseApiResponse(res);
}

async function parseApiResponse(res) {
  const data = await res.json();
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `local db request failed: ${res.status}`);
  }
  return data;
}
