import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { routes } from './routes';
export const router = createRouter({
    history: createWebHistory(),
    routes,
});
router.beforeEach(async (to) => {
    const authStore = useAuthStore();
    await authStore.initialize();
    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
        return `/login?redirect=${encodeURIComponent(to.fullPath)}`;
    }
    if (to.meta.guestOnly && authStore.isAuthenticated) {
        return {
            path: '/library',
        };
    }
    return true;
});
