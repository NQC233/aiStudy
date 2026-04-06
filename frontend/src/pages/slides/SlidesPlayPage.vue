<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import {
  fetchAssetDetail,
  fetchAssetSlides,
  rebuildAssetSlides,
  type AssetDetail,
  type AssetSlidesResponse,
  type SlideDslPage,
} from '@/api/assets';

const route = useRoute();
const router = useRouter();
const assetId = computed(() => String(route.params.assetId ?? ''));

const loading = ref(false);
const errorMessage = ref('');
const recoveringSlides = ref(false);
const asset = ref<AssetDetail | null>(null);
const slidesResponse = ref<AssetSlidesResponse | null>(null);
const currentSlideIndex = ref(0);

const pages = computed(() => slidesResponse.value?.slides_dsl?.pages ?? []);
const currentPage = computed(() => pages.value[currentSlideIndex.value] ?? null);
const qualityScore = computed(() => slidesResponse.value?.quality_report?.overall_score ?? null);
const generationMeta = computed(() => slidesResponse.value?.generation_meta ?? null);
const shadowReport = computed(() => slidesResponse.value?.shadow_report ?? null);
const effectiveSlidesStatus = computed(() => slidesResponse.value?.slides_status ?? asset.value?.enhanced_resources.slides_status ?? 'unknown');
const isSlidesReady = computed(() => effectiveSlidesStatus.value === 'ready');
const canGoPrev = computed(() => currentSlideIndex.value > 0);
const canGoNext = computed(() => currentSlideIndex.value < pages.value.length - 1);

function blockContent(page: SlideDslPage | null, blockType: string): string {
  if (!page) {
    return '';
  }
  return page.blocks.find((item) => item.block_type === blockType)?.content ?? '';
}

function prevSlide() {
  if (!canGoPrev.value) {
    return;
  }
  currentSlideIndex.value -= 1;
}

function nextSlide() {
  if (!canGoNext.value) {
    return;
  }
  currentSlideIndex.value += 1;
}

function clampCurrentSlide() {
  if (!pages.value.length) {
    currentSlideIndex.value = 0;
    return;
  }
  currentSlideIndex.value = Math.max(0, Math.min(currentSlideIndex.value, pages.value.length - 1));
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft') {
    prevSlide();
  }
  if (event.key === 'ArrowRight') {
    nextSlide();
  }
}

async function loadSlides() {
  loading.value = true;
  errorMessage.value = '';

  try {
    const [assetDetail, slides] = await Promise.all([
      fetchAssetDetail(assetId.value),
      fetchAssetSlides(assetId.value),
    ]);
    asset.value = assetDetail;
    slidesResponse.value = slides;

    if (!slides.slides_dsl || slides.slides_status !== 'ready') {
      throw new Error('当前演示内容尚未就绪，请先在工作区触发生成。');
    }
    clampCurrentSlide();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '演示页面加载失败。';
  } finally {
    loading.value = false;
  }
}

function jumpToCitation(pageNo: number, blockId: string | null) {
  void router.push({
    name: 'workspace',
    params: { assetId: assetId.value },
    query: {
      page: String(pageNo),
      blockId: blockId ?? '',
      source: 'slides',
    },
  });
}

async function backToWorkspace() {
  await router.push({
    name: 'workspace',
    params: { assetId: assetId.value },
  });
}

async function recoverSlidesAndBack() {
  if (recoveringSlides.value) {
    return;
  }
  recoveringSlides.value = true;

  try {
    await rebuildAssetSlides(assetId.value);
    await router.push({
      name: 'workspace',
      params: { assetId: assetId.value },
      query: { source: 'slides-rebuild' },
    });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重新生成演示内容失败。';
  } finally {
    recoveringSlides.value = false;
  }
}

watch(
  () => route.params.assetId,
  () => {
    currentSlideIndex.value = 0;
    void loadSlides();
  },
);

watch(
  () => pages.value.length,
  () => {
    clampCurrentSlide();
  },
);

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
  void loadSlides();
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <main class="slides-page">
    <section class="slides-shell">
      <header class="slides-header">
        <div>
          <p class="slides-kicker">Slides / Spec 11C</p>
          <h1>{{ asset?.title ?? '演示播放页' }}</h1>
          <p class="slides-meta">
            状态：{{ effectiveSlidesStatus }}
            <span v-if="qualityScore !== null"> · 质量分：{{ qualityScore.toFixed(2) }}</span>
          </p>
          <p v-if="generationMeta && isSlidesReady" class="slides-meta">
            策略：{{ generationMeta.requested_strategy }} → {{ generationMeta.applied_strategy }}
            <span v-if="generationMeta.fallback_used"> · 已回退（{{ generationMeta.fallback_reason || 'unknown' }}）</span>
          </p>
          <p v-else-if="!isSlidesReady" class="slides-meta">策略结果更新中，请等待当前生成完成。</p>
          <p v-if="shadowReport && isSlidesReady" class="slides-meta">
            Shadow：{{ shadowReport.status }}
            <span v-if="shadowReport.score_delta !== null"> · Δ{{ shadowReport.score_delta.toFixed(2) }}</span>
            <span v-else-if="shadowReport.skip_reason"> · {{ shadowReport.skip_reason }}</span>
          </p>
        </div>
        <RouterLink :to="`/workspace/${assetId}`" class="slides-back">
          返回工作区
        </RouterLink>
      </header>

      <section v-if="loading" class="slides-empty">
        正在加载演示内容...
      </section>
      <section v-else-if="errorMessage" class="slides-empty slides-empty--error">
        <p class="slides-error-message">{{ errorMessage }}</p>
        <div class="slides-error-actions">
          <button type="button" class="toolbar-button toolbar-button--ghost" @click="backToWorkspace">
            返回工作区
          </button>
          <button type="button" class="toolbar-button" :disabled="recoveringSlides" @click="recoverSlidesAndBack">
            {{ recoveringSlides ? '提交中...' : '重新生成并返回工作区' }}
          </button>
        </div>
      </section>

      <section v-else class="slides-layout">
        <section class="slides-stage">
          <header class="slides-stage__toolbar">
            <button type="button" class="toolbar-button toolbar-button--ghost" :disabled="!canGoPrev" @click="prevSlide">
              上一页
            </button>
            <p class="slides-stage__counter">
              {{ pages.length ? `${currentSlideIndex + 1} / ${pages.length}` : '0 / 0' }}
            </p>
            <button type="button" class="toolbar-button" :disabled="!canGoNext" @click="nextSlide">
              下一页
            </button>
          </header>
          <p class="slides-stage__hint">快捷键：← / → 切换页面</p>

          <nav v-if="pages.length" class="slides-page-nav" aria-label="演示分页目录">
            <button
              v-for="(page, index) in pages"
              :key="page.slide_key"
              type="button"
              class="slides-page-nav__item"
              :class="{ 'slides-page-nav__item--active': index === currentSlideIndex }"
              @click="currentSlideIndex = index"
            >
              <span class="slides-page-nav__index">{{ index + 1 }}</span>
              <span class="slides-page-nav__title">{{ blockContent(page, 'title') || page.stage }}</span>
            </button>
          </nav>

          <article v-if="currentPage" class="slides-section">
            <h2>{{ currentSlideIndex + 1 }}. {{ blockContent(currentPage, 'title') || currentPage.stage }}</h2>
            <p class="slides-goal">{{ blockContent(currentPage, 'goal') }}</p>
            <p class="slides-evidence">{{ blockContent(currentPage, 'evidence') }}</p>
          </article>
          <section v-else class="slides-empty">暂无可播放页面。</section>
        </section>

        <aside class="slides-notes">
          <header>
            <p class="slides-kicker">Speaker Notes</p>
            <h2>{{ currentPage?.slide_key ?? '未选中页面' }}</h2>
          </header>

          <p class="slides-script">
            {{ currentPage ? blockContent(currentPage, 'script') : '切换页面后查看讲稿。' }}
          </p>

          <ul v-if="currentPage?.citations.length" class="slides-citations">
            <li v-for="(citation, idx) in currentPage.citations" :key="`${currentPage.slide_key}-${idx}`">
              <button
                type="button"
                class="slides-citation-button"
                @click="jumpToCitation(citation.page_no, citation.block_ids[0] ?? null)"
              >
                <strong>P{{ citation.page_no }} / {{ citation.block_ids[0] ?? 'block' }}</strong>
                <span>{{ citation.quote }}</span>
              </button>
            </li>
          </ul>
          <p v-else class="slides-citation-empty">当前页暂无引用锚点。</p>
        </aside>
      </section>
    </section>
  </main>
</template>

<style scoped>
.slides-page {
  min-height: 100vh;
  padding: 1.25rem;
  background: radial-gradient(circle at 0% 0%, #f6f0df 0%, #f2efe8 30%, #ebe9e1 100%);
  font-family: 'Avenir Next', 'Segoe UI', sans-serif;
  color: #1f2730;
}

.slides-shell {
  max-width: 1380px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slides-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.slides-kicker {
  margin: 0;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #965d17;
}

.slides-header h1 {
  margin: 0.35rem 0;
  font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
  font-size: 2rem;
}

.slides-meta {
  margin: 0;
  color: #4d5b6b;
}

.slides-back {
  text-decoration: none;
  color: #fff;
  background: linear-gradient(135deg, #9a5f17, #6d4010);
  padding: 0.65rem 0.95rem;
  border-radius: 0.75rem;
}

.slides-empty {
  background: #fff;
  border-radius: 1rem;
  padding: 1.25rem;
}

.slides-empty--error {
  background: #fbe9e9;
  color: #8a1f1f;
}

.slides-error-message {
  margin: 0;
}

.slides-error-actions {
  margin-top: 0.85rem;
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.slides-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 1rem;
}

.slides-stage,
.slides-notes {
  background: #fff;
  border-radius: 1rem;
  border: 1px solid #d9d7cf;
  padding: 1rem;
}

.slides-stage__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}

.slides-stage__counter {
  margin: 0;
  color: #556274;
  font-weight: 600;
}

.slides-stage__hint {
  margin: 0 0 0.7rem;
  color: #687586;
  font-size: 0.88rem;
}

.slides-page-nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.85rem;
}

.slides-page-nav__item {
  border: 1px solid #dccfb6;
  border-radius: 0.7rem;
  background: #fff9ef;
  color: #61401c;
  padding: 0.5rem 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  text-align: left;
  cursor: pointer;
}

.slides-page-nav__item:hover {
  border-color: #ba8a4d;
  background: #fff4df;
}

.slides-page-nav__item--active {
  border-color: #8e5a22;
  background: #f6e7cf;
}

.slides-page-nav__index {
  width: 1.45rem;
  height: 1.45rem;
  border-radius: 50%;
  background: #e9d5b4;
  color: #6e4417;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.slides-page-nav__title {
  font-size: 0.88rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-button {
  border: 1px solid #ab7c44;
  border-radius: 0.7rem;
  background: linear-gradient(135deg, #9a5f17, #6d4010);
  color: #fff;
  padding: 0.42rem 0.85rem;
  cursor: pointer;
}

.toolbar-button--ghost {
  background: #fff9ef;
  color: #7a4d1f;
}

.toolbar-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.slides-section h2 {
  margin-top: 0;
  font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
  color: #7a4310;
}

.slides-goal {
  font-weight: 600;
}

.slides-evidence {
  opacity: 0.86;
}

.slides-script {
  margin: 0.75rem 0;
  line-height: 1.5;
}

.slides-citations {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.slides-citation-button {
  width: 100%;
  border: 1px solid #d8d1c3;
  border-radius: 0.8rem;
  padding: 0.65rem;
  background: #fff8ec;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  cursor: pointer;
}

.slides-citation-button:hover {
  border-color: #b1762f;
  background: #fff1dc;
}

.slides-citation-empty {
  color: #6a7483;
}

@media (max-width: 980px) {
  .slides-layout {
    grid-template-columns: 1fr;
  }

  .slides-header {
    flex-direction: column;
  }
}
</style>
