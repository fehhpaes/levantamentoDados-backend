// Service to track sync progress without circular dependencies
export const syncState = {
  isSyncing: false,
  progress: 0,
  currentTask: '',
  lastSync: null as Date | null,
  leaguesProcessed: [] as string[]
};

export const updateSyncStatus = (data: Partial<typeof syncState>) => {
  Object.assign(syncState, data);
};
