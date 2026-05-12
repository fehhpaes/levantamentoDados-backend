import dotenv from 'dotenv';

dotenv.config();

// Simple in-memory cache to replace Redis
const memoryCache = new Map<string, { value: string, expires: number }>();

export const connectRedis = async () => {
  console.log('[Cache] Using In-Memory Cache (Redis disabled)');
  return Promise.resolve();
};

export const getCache = async (key: string): Promise<string | null> => {
  const item = memoryCache.get(key);
  if (!item) return null;

  if (Date.now() > item.expires) {
    memoryCache.delete(key);
    return null;
  }
  return item.value;
};

export const setCache = async (key: string, value: string, ttlSeconds: number = 3600): Promise<void> => {
  memoryCache.set(key, {
    value,
    expires: Date.now() + (ttlSeconds * 1000)
  });
};

export const deleteCache = async (key: string): Promise<void> => {
  memoryCache.delete(key);
};

export const clearAllCache = async (): Promise<void> => {
  memoryCache.clear();
  console.log('[Cache] In-Memory Cache cleared');
};

// Mock client to avoid breaking imports that expect the redis client object
export default {
  connect: () => Promise.resolve(),
  get: getCache,
  set: setCache,
  del: deleteCache,
  flushAll: clearAllCache,
  on: () => {}
};
