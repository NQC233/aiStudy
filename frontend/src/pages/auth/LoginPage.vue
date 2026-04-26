<script setup lang="ts">
import { reactive, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const form = reactive({
  email: '',
  password: '',
});
const submitting = ref(false);
const errorMessage = ref('');

function resolveRedirectTarget(value: unknown): string {
  return typeof value === 'string' && value.startsWith('/') ? value : '/library';
}

async function handleSubmit() {
  submitting.value = true;
  errorMessage.value = '';

  try {
    await authStore.loginWithPassword({
      email: form.email.trim(),
      password: form.password,
    });
    await router.replace(resolveRedirectTarget(route.query.redirect));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败。';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-shell">
      <div class="auth-shell__intro">
        <p class="page-kicker">Spec 18 / Sign in</p>
        <h1>登录后进入你的论文学习工作台</h1>
        <p class="page-intro">
          使用邮箱与密码恢复个人资产、工作区和演示内容。未登录状态下，受保护页面会自动跳回这里。
        </p>
        <p class="auth-shell__switch">
          还没有账户？
          <RouterLink :to="`/register?redirect=${encodeURIComponent(resolveRedirectTarget(route.query.redirect))}`">
            去注册
          </RouterLink>
        </p>
      </div>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <label class="auth-form__field">
          <span>邮箱</span>
          <input
            v-model="form.email"
            type="email"
            name="email"
            autocomplete="email"
            placeholder="you@example.com"
            required
          />
        </label>

        <label class="auth-form__field">
          <span>密码</span>
          <input
            v-model="form.password"
            type="password"
            name="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            required
          />
        </label>

        <p v-if="errorMessage" class="auth-form__error">{{ errorMessage }}</p>

        <button class="toolbar-button auth-form__submit" type="submit" :disabled="submitting">
          {{ submitting ? '登录中...' : '登录' }}
        </button>
      </form>
    </section>
  </main>
</template>
