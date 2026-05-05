import { createClient } from 'redis';
import dotenv from 'dotenv';

dotenv.config();

export const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';

const client = createClient({
  url: redisUrl
});

client.on('error', (err) => console.error('[Redis] Client Error:', err));

export const connectRedis = async () => {
  try {
    await client.connect();
    console.log('[Redis] Connected successfully');
  } catch (error) {
    console.error('[Redis] Connection failed:', error);
  }
};

export const getCache = async (key: string): Promise<string | null> => {
  try {
    return await client.get(key);
  } catch (error) {
    console.error(`[Redis] Get error for key ${key}:`, error);
    return null;
  }
};

export const setCache = async (key: string, value: string, ttlSeconds: number = 3600): Promise<void> => {
  try {
    await client.set(key, value, {
      EX: ttlSeconds
    });
  } catch (error) {
    console.error(`[Redis] Set error for key ${key}:`, error);
  }
};

export const deleteCache = async (key: string): Promise<void> => {
  try {
    await client.del(key);
  } catch (error) {
    console.error(`[Redis] Delete error for key ${key}:`, error);
  }
};

export const clearAllCache = async (): Promise<void> => {
  try {
    await client.flushAll();
    console.log('[Redis] All cache cleared');
  } catch (error) {
    console.error('[Redis] Flush error:', error);
  }
};

export default client;
