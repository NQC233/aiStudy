import { computed, ref } from 'vue';
function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}
function resolvePagePlan(page, pagePlans) {
    if (!page) {
        return null;
    }
    return pagePlans.find((item) => item.slide_key === page.slide_key) ?? null;
}
export function useSlidesPlaybackTimeline(options) {
    const { pages, currentSlideIndex, playbackPlan } = options;
    const isPlaying = ref(false);
    const autoPageEnabled = ref(true);
    const currentPageElapsedMs = ref(0);
    const previewGlobalMs = ref(null);
    const totalDurationMs = computed(() => playbackPlan.value?.total_duration_ms ?? 0);
    const pagePlans = computed(() => playbackPlan.value?.pages ?? []);
    const currentPage = computed(() => pages.value[currentSlideIndex.value]);
    const currentPagePlan = computed(() => resolvePagePlan(currentPage.value, pagePlans.value));
    const currentPageDurationMs = computed(() => currentPagePlan.value?.duration_ms ?? 0);
    const committedGlobalMs = computed(() => {
        if (!currentPagePlan.value) {
            return 0;
        }
        return clamp(currentPagePlan.value.start_ms + currentPageElapsedMs.value, 0, totalDurationMs.value);
    });
    const displayedGlobalMs = computed(() => {
        if (previewGlobalMs.value === null) {
            return committedGlobalMs.value;
        }
        return previewGlobalMs.value;
    });
    const activeCueBlockId = computed(() => {
        if (!currentPagePlan.value || currentPagePlan.value.cues.length === 0) {
            return null;
        }
        const cursor = clamp(currentPageElapsedMs.value, 0, currentPagePlan.value.duration_ms);
        const cue = currentPagePlan.value.cues.find((item) => cursor >= item.start_ms && cursor < item.end_ms);
        return cue?.block_id ?? currentPagePlan.value.cues[currentPagePlan.value.cues.length - 1]?.block_id ?? null;
    });
    function setPlaying(value) {
        isPlaying.value = value;
    }
    function setAutoPageEnabled(value) {
        autoPageEnabled.value = value;
    }
    function syncToSlideStart(index) {
        const page = pages.value[index];
        const plan = resolvePagePlan(page, pagePlans.value);
        currentPageElapsedMs.value = 0;
        previewGlobalMs.value = null;
        if (!plan) {
            return;
        }
        currentPageElapsedMs.value = clamp(currentPageElapsedMs.value, 0, plan.duration_ms);
    }
    function setCurrentPageElapsedMs(value) {
        const duration = currentPageDurationMs.value;
        if (duration <= 0) {
            currentPageElapsedMs.value = 0;
            return;
        }
        currentPageElapsedMs.value = clamp(Math.round(value), 0, duration);
    }
    function beginPreview(globalMs) {
        previewGlobalMs.value = clamp(Math.round(globalMs), 0, totalDurationMs.value);
    }
    function endPreviewAndGetSeekTarget() {
        const target = previewGlobalMs.value ?? committedGlobalMs.value;
        previewGlobalMs.value = null;
        return target;
    }
    function seekGlobalMs(globalMs) {
        const clamped = clamp(Math.round(globalMs), 0, totalDurationMs.value);
        if (!pagePlans.value.length) {
            return { pageIndex: 0, pageElapsedMs: 0 };
        }
        const matched = pagePlans.value.find((item) => clamped >= item.start_ms && clamped < item.end_ms) ?? pagePlans.value[pagePlans.value.length - 1];
        const index = pages.value.findIndex((item) => item.slide_key === matched.slide_key);
        const pageIndex = index >= 0 ? index : 0;
        return {
            pageIndex,
            pageElapsedMs: clamp(clamped - matched.start_ms, 0, matched.duration_ms),
        };
    }
    return {
        isPlaying,
        autoPageEnabled,
        totalDurationMs,
        displayedGlobalMs,
        currentPageElapsedMs,
        activeCueBlockId,
        setPlaying,
        setAutoPageEnabled,
        syncToSlideStart,
        setCurrentPageElapsedMs,
        beginPreview,
        endPreviewAndGetSeekTarget,
        seekGlobalMs,
    };
}
