<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const showAccountBar = computed(() => !['login', 'register'].includes(String(route.name)) && authStore.isAuthenticated);

async function handleLogout() {
  authStore.clearSession();
  await router.replace({
    name: 'login',
    query: {
      redirect: route.fullPath,
    },
  });
}
</script>

<template>
  <div>
    <header v-if="showAccountBar" class="account-bar">
      <div class="account-bar__inner">
        <div>
          <p class="page-kicker">Signed in</p>
          <strong>{{ authStore.currentUser?.display_name }}</strong>
        </div>

        <div class="account-bar__actions">
          <span class="account-bar__email">{{ authStore.currentUser?.email }}</span>
          <button class="toolbar-button toolbar-button--ghost" type="button" @click="handleLogout">
            退出登录
          </button>
        </div>
      </div>
    </header>

    <router-view />
  </div>
</template>
