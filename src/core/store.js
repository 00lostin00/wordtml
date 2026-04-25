/**
 * IndexedDB 封装。
 *
 * 数据结构:
 *   - progress     key: wordId     value: { wordId, wordlistId, box, ease, reps, interval, due, wrong, lastReviewed }
 *   - wrongbook    key: wordId     value: { wordId, wordlistId, count, lastWrong, resolvedStreak }
 *   - settings     key: string     value: any
 *   - stats        key: YYYY-MM-DD value: { date, learned, reviewed, correct, total }
 *   - sessions     key: autoInc    value: { startedAt, endedAt, mode, wordlistId, total, correct }
 *   - mapProgress  key: nodeKey    value: { nodeKey, chapterId, nodeId, bestStars, bestAccuracy, attempts, firstClearedAt, lastAttemptAt }
 *   - economy      key: "main"     value: { coins, items: { hint, skip, extend, xray } }
 *   - rankHistory  key: autoInc    value: { at, tierKey, points, highest, delta, win, isDaily }
 *   - achievements key: id         value: { id, unlockedAt, event }
 *   - examAttempts key: autoInc    value: { examId, startedAt, endedAt, answers, scoredSections, totalScore }
 */
const DB_NAME = "wordtml";
const DB_VERSION = 5;
const DEFAULT_ITEMS = { hint: 0, skip: 0, extend: 0, xray: 0 };

const STORES = {
  progress: { keyPath: "wordId", indexes: [["wordlistId", "wordlistId"], ["due", "due"]] },
  wrongbook: { keyPath: "wordId", indexes: [["wordlistId", "wordlistId"]] },
  settings: { keyPath: "key" },
  stats: { keyPath: "date" },
  sessions: { keyPath: "id", autoIncrement: true, indexes: [["startedAt", "startedAt"]] },
  mapProgress: { keyPath: "nodeKey", indexes: [["chapterId", "chapterId"]] },
  economy: { keyPath: "key" },
  rankHistory: { keyPath: "id", autoIncrement: true, indexes: [["at", "at"]] },
  achievements: { keyPath: "id", indexes: [["unlockedAt", "unlockedAt"]] },
  examAttempts: { keyPath: "id", autoIncrement: true, indexes: [["examId", "examId"], ["endedAt", "endedAt"]] },
};

let dbPromise = null;

function open() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      for (const [name, def] of Object.entries(STORES)) {
        if (db.objectStoreNames.contains(name)) continue;
        const os = db.createObjectStore(name, {
          keyPath: def.keyPath,
          autoIncrement: !!def.autoIncrement,
        });
        (def.indexes || []).forEach(([idxName, key]) => os.createIndex(idxName, key));
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  return dbPromise;
}

function tx(storeName, mode = "readonly") {
  return open().then((db) => db.transaction(storeName, mode).objectStore(storeName));
}

function reqToPromise(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export const store = {
  async get(storeName, key) {
    const os = await tx(storeName);
    return reqToPromise(os.get(key));
  },

  async put(storeName, value) {
    const os = await tx(storeName, "readwrite");
    return reqToPromise(os.put(value));
  },

  async delete(storeName, key) {
    const os = await tx(storeName, "readwrite");
    return reqToPromise(os.delete(key));
  },

  async all(storeName) {
    const os = await tx(storeName);
    return reqToPromise(os.getAll());
  },

  async byIndex(storeName, indexName, query) {
    const os = await tx(storeName);
    const idx = os.index(indexName);
    return reqToPromise(idx.getAll(query));
  },

  async clear(storeName) {
    const os = await tx(storeName, "readwrite");
    return reqToPromise(os.clear());
  },

  // 便捷工具:settings
  async setSetting(key, value) {
    return this.put("settings", { key, value });
  },
  async getSetting(key, fallback = null) {
    const row = await this.get("settings", key);
    return row ? row.value : fallback;
  },

  // 便捷工具:stats
  async bumpStats(patch) {
    const date = new Date().toISOString().slice(0, 10);
    const cur = (await this.get("stats", date)) || { date, learned: 0, reviewed: 0, correct: 0, total: 0 };
    for (const k of Object.keys(patch)) cur[k] = (cur[k] || 0) + patch[k];
    await this.put("stats", cur);
    return cur;
  },

  // 经济系统(金币、道具)
  async getEconomy() {
    const row = await this.get("economy", "main");
    const eco = row ? row.value : { coins: 0, items: { ...DEFAULT_ITEMS } };
    eco.coins = Number(eco.coins || 0);
    eco.items = { ...DEFAULT_ITEMS, ...(eco.items || {}) };
    return eco;
  },
  async setEconomy(eco) {
    return this.put("economy", { key: "main", value: eco });
  },
  async addCoins(delta) {
    const eco = await this.getEconomy();
    eco.coins = Math.max(0, (eco.coins || 0) + delta);
    await this.setEconomy(eco);
    return eco;
  },

  async exportAll() {
    const result = {};
    for (const name of Object.keys(STORES)) {
      result[name] = await this.all(name);
    }
    return { version: DB_VERSION, exportedAt: Date.now(), data: result };
  },

  async importAll(dump) {
    if (!dump || !dump.data) throw new Error("invalid dump");
    for (const [name, rows] of Object.entries(dump.data)) {
      if (!STORES[name]) continue;
      const os = await tx(name, "readwrite");
      await reqToPromise(os.clear());
      for (const row of rows) {
        await reqToPromise(os.put(row));
      }
    }
  },
};
