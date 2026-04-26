import { defineStore } from 'pinia';

import {
  clearStoredAccessToken,
  fetchCurrentUser,
  login,
  readStoredAccessToken,
  register,
  storeAccessToken,
  type LoginRequest,
  type RegisterRequest,
  type CurrentUser,
} from '@/api/auth';

let initializePromise: Promise<void> | null = null;

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: readStoredAccessToken() as string | null,
    currentUser: null as CurrentUser | null,
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken && state.currentUser),
  },
  actions: {
    async initialize() {
      if (this.initialized) {
        return;
      }

      if (initializePromise) {
        return initializePromise;
      }

      initializePromise = (async () => {
        if (!this.accessToken) {
          this.currentUser = null;
          this.initialized = true;
          return;
        }

        try {
          this.currentUser = await fetchCurrentUser();
        } catch {
          this.clearSession();
        }

        this.initialized = true;
      })();

      try {
        await initializePromise;
      } finally {
        initializePromise = null;
      }
    },
    async loginWithPassword(payload: LoginRequest) {
      const response = await login(payload);
      this.accessToken = response.access_token;
      this.currentUser = response.user;
      this.initialized = true;
      storeAccessToken(response.access_token);
    },
    async registerWithPassword(payload: RegisterRequest) {
      const response = await register(payload);
      this.accessToken = response.access_token;
      this.currentUser = response.user;
      this.initialized = true;
      storeAccessToken(response.access_token);
    },
    clearSession() {
      this.accessToken = null;
      this.currentUser = null;
      clearStoredAccessToken();
    },
  },
});
