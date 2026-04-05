import type { RouteRecordRaw } from 'vue-router';

import LibraryPage from '@/pages/library/LibraryPage.vue';
import SlidesPlayPage from '@/pages/slides/SlidesPlayPage.vue';
import WorkspacePage from '@/pages/workspace/WorkspacePage.vue';

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/library',
  },
  {
    path: '/library',
    name: 'library',
    component: LibraryPage,
  },
  {
    path: '/workspace/:assetId',
    name: 'workspace',
    component: WorkspacePage,
    props: true,
  },
  {
    path: '/workspace/:assetId/slides',
    name: 'slides-play',
    component: SlidesPlayPage,
    props: true,
  },
];
