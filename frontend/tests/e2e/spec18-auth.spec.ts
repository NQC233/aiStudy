import { expect, test } from '@playwright/test';

test('redirects unauthenticated user to login and preserves redirect target', async ({ page }) => {
  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: '登录态无效或已过期。' }),
    });
  });

  await page.goto('/library');

  await expect(page).toHaveURL(/\/login\?redirect=/);
  expect(new URL(page.url()).searchParams.get('redirect')).toBe('/library');
});

test('logs in and redirects back to the original protected route', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'token-123',
        token_type: 'bearer',
        user: {
          id: 'user-1',
          email: 'demo@example.com',
          display_name: 'Demo User',
          status: 'active',
          created_at: '2026-04-26T00:00:00Z',
        },
      }),
    });
  });

  await page.route('**/api/assets', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.goto('/login?redirect=%2Flibrary');
  await page.getByLabel('邮箱').fill('demo@example.com');
  await page.getByLabel('密码').fill('password123');
  await page.getByRole('button', { name: '登录' }).click();

  await expect(page).toHaveURL(/\/library$/);
});

test('registers a new user and redirects to the original protected route', async ({ page }) => {
  await page.route('**/api/auth/register', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'token-register-123',
        token_type: 'bearer',
        user: {
          id: 'user-2',
          email: 'new@example.com',
          display_name: 'New User',
          status: 'active',
          created_at: '2026-04-26T00:00:00Z',
        },
      }),
    });
  });

  await page.route('**/api/assets', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.goto('/register?redirect=%2Flibrary');
  await page.getByLabel('显示名称').fill('New User');
  await page.getByLabel('邮箱').fill('new@example.com');
  await page.getByLabel('密码').fill('password123');
  await page.getByRole('button', { name: '注册并登录' }).click();

  await expect(page).toHaveURL(/\/library$/);
  await expect(page.getByText('New User')).toBeVisible();
});
