<script setup lang="ts">
import { reactive, ref } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const form = reactive({
  displayName: '',
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
    await authStore.registerWithPassword({
      display_name: form.displayName.trim(),
      email: form.email.trim(),
      password: form.password,
    });
    await router.replace(resolveRedirectTarget(route.query.redirect));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '注册失败。';
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-shell">
      <div class="auth-shell__intro">
        <p class="page-kicker">Spec 18 / Register</p>
        <h1>创建账户后直接进入你的论文学习工作台</h1>
        <p class="page-intro">
          首版账户系统采用邮箱与密码。注册成功后会直接建立登录态，并跳回你原本要访问的受保护页面。
        </p>
        <p class="auth-shell__switch">
          已有账户？
          <RouterLink :to="`/login?redirect=${encodeURIComponent(resolveRedirectTarget(route.query.redirect))}`">
            去登录
          </RouterLink>
        </p>
      </div>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <label class="auth-form__field">
          <span>显示名称</span>
          <input
            v-model="form.displayName"
            type="text"
            name="displayName"
            autocomplete="name"
            placeholder="请输入展示名称"
            required
          />
        </label>

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
            autocomplete="new-password"
            placeholder="至少 8 位密码"
            minlength="8"
            required
          />
        </label>

        <p v-if="errorMessage" class="auth-form__error">{{ errorMessage }}</p>

        <button class="toolbar-button auth-form__submit" type="submit" :disabled="submitting">
          {{ submitting ? '注册中...' : '注册并登录' }}
        </button>
      </form>
    </section>
  </main>
</template>
