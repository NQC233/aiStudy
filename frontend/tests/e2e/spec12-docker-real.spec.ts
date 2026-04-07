import { expect, test, type APIRequestContext } from '@playwright/test';

const providedAssetId = process.env.SPEC12_E2E_ASSET_ID || '';
const apiBaseUrl = process.env.SPEC12_E2E_API_BASE_URL || 'http://127.0.0.1:8000';

async function fetchSlides(request: APIRequestContext, id: string) {
  const response = await request.get(`${apiBaseUrl}/api/assets/${id}/slides`);
  expect(response.ok()).toBeTruthy();
  return response.json();
}

async function resolveE2EAssetId(request: APIRequestContext): Promise<string> {
  if (providedAssetId) {
    return providedAssetId;
  }

  const listResponse = await request.get(`${apiBaseUrl}/api/assets`);
  expect(listResponse.ok()).toBeTruthy();
  const assets = (await listResponse.json()) as Array<{ id?: string }>;

  for (const item of assets) {
    const candidateId = item?.id;
    if (!candidateId) {
      continue;
    }
    const slidesResponse = await request.get(`${apiBaseUrl}/api/assets/${candidateId}/slides`);
    if (!slidesResponse.ok()) {
      continue;
    }
    const slides = await slidesResponse.json();
    const pageCount = slides?.slides_dsl?.pages?.length ?? 0;
    if (slides?.slides_status === 'ready' && pageCount >= 2) {
      return candidateId;
    }
  }

  throw new Error(
    'No ready asset with at least 2 slides found. Set SPEC12_E2E_ASSET_ID explicitly.',
  );
}

test.describe('Spec12 Docker E2E', () => {
  test('tts generation pipeline reaches ready state for first two pages', async ({ request, page }) => {
    const assetId = await resolveE2EAssetId(request);

    const ensureResponse = await request.post(
      `${apiBaseUrl}/api/assets/${assetId}/slides/tts/ensure`,
      {
        data: {
          page_index: 0,
          prefetch_next: true,
        },
      },
    );
    expect(ensureResponse.ok()).toBeTruthy();

    let firstPageStatus = 'pending';
    let secondPageStatus = 'pending';
    let firstPageError = '';
    let secondPageError = '';
    let firstAudioUrl = '';
    let secondAudioUrl = '';

    for (let i = 0; i < 45; i += 1) {
      const slides = await fetchSlides(request, assetId);
      const firstPage = slides?.tts_manifest?.pages?.[0];
      const secondPage = slides?.tts_manifest?.pages?.[1];
      firstPageStatus = firstPage?.status ?? 'unknown';
      secondPageStatus = secondPage?.status ?? 'unknown';
      firstPageError = firstPage?.error_message ?? '';
      secondPageError = secondPage?.error_message ?? '';
      firstAudioUrl = firstPage?.audio_url ?? '';
      secondAudioUrl = secondPage?.audio_url ?? '';

      if (firstPageStatus === 'ready' && secondPageStatus === 'ready') {
        break;
      }
      if (firstPageStatus === 'failed') {
        throw new Error(`First slide TTS failed: ${firstPageError || 'unknown error'}`);
      }
      if (secondPageStatus === 'failed') {
        throw new Error(`Second slide TTS failed: ${secondPageError || 'unknown error'}`);
      }
      await page.waitForTimeout(2000);
    }

    expect(firstPageStatus).toBe('ready');
    expect(secondPageStatus).toBe('ready');
    expect(firstAudioUrl).toContain('http');
    expect(secondAudioUrl).toContain('http');
  });
});
