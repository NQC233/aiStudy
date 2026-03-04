import LibraryPage from '@/pages/library/LibraryPage.vue';
import WorkspacePage from '@/pages/workspace/WorkspacePage.vue';
export const routes = [
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
];
