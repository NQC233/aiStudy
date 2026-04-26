import type { RouteRecordRaw } from 'vue-router';

import LoginPage from '@/pages/auth/LoginPage.vue';
import RegisterPage from '@/pages/auth/RegisterPage.vue';
import LibraryPage from '@/pages/library/LibraryPage.vue';
import SlidesPlayPage from '@/pages/slides/SlidesPlayPage.vue';
import WorkspacePage from '@/pages/workspace/WorkspacePage.vue';

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/library',
  },
  {
    path: '/login',
    name: 'login',
    component: LoginPage,
    meta: {
      guestOnly: true,
    },
  },
  {
    path: '/register',
    name: 'register',
    component: RegisterPage,
    meta: {
      guestOnly: true,
    },
  },
  {
    path: '/library',
    name: 'library',
    component: LibraryPage,
    meta: {
      requiresAuth: true,
    },
  },
  {
    path: '/workspace/:assetId',
    name: 'workspace',
    component: WorkspacePage,
    props: true,
    meta: {
      requiresAuth: true,
    },
  },
  {
    path: '/workspace/:assetId/slides',
    name: 'slides-play',
    component: SlidesPlayPage,
    props: true,
    meta: {
      requiresAuth: true,
    },
  },
];
