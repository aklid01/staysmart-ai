import { expect, test } from '@playwright/test'

const SEARCH_MESSAGE =
  'Find a hotel in Kyoto for two guests in December under 250 with breakfast and wifi.'

test('initial load shows header, health status and empty state', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'StaySmart AI', level: 1 })).toBeVisible()
  await expect(page.getByText('API connected')).toBeVisible()
  await expect(page.getByText('mock data')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Where would you like to stay?' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Send' })).toBeDisabled()
})

test('search flow returns assistant reply with hotel card and tool trace', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill(SEARCH_MESSAGE)
  await input.press('Enter')

  await expect(page.getByText('Thinking...')).toBeVisible()
  const card = page.getByRole('heading', { name: 'Gion Machiya Stay' })
  await expect(card).toBeVisible()
  await expect(page.getByText('211.86 USD').first()).toBeVisible()
  await expect(page.locator('.tool-chip', { hasText: 'search_hotels' })).toBeVisible()
  await page.screenshot({ path: '../artifacts/e2e_ui/search_flow.png', fullPage: false })
})

test('details dialog shows room quotes and cancellation policy', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill(SEARCH_MESSAGE)
  await input.press('Enter')
  await expect(page.getByRole('heading', { name: 'Gion Machiya Stay' })).toBeVisible()

  await page.getByRole('button', { name: 'Details' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('heading', { name: /details/i })).toBeVisible()
  await expect(dialog.getByRole('cell', { name: 'Tatami Double' })).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Cancellation' })).toBeVisible()

  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()
})

test('policies dialog opens and closes', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill(SEARCH_MESSAGE)
  await input.press('Enter')
  await expect(page.getByRole('heading', { name: 'Gion Machiya Stay' })).toBeVisible()

  await page.getByRole('button', { name: 'Policies' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Pets' })).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'Check-in / check-out' })).toBeVisible()

  await dialog.getByRole('button', { name: 'Close' }).click()
  await expect(dialog).toBeHidden()
})

test('assistant reply renders markdown table and inline code', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill(SEARCH_MESSAGE)
  await input.press('Enter')
  await expect(page.getByRole('heading', { name: 'Gion Machiya Stay' })).toBeVisible()

  const table = page.locator('.md-table')
  await expect(table).toBeVisible()
  await expect(table.getByRole('cell', { name: 'Tatami Double' })).toBeVisible()
  await expect(page.locator('.markdown code', { hasText: 'STAY-2026-12' })).toBeVisible()
  await page.screenshot({ path: '../artifacts/e2e_ui/markdown_rendering.png', fullPage: false })
})

test('chat failure surfaces error banner and failed user bubble', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill('Please trigger a failure for testing.')
  await input.press('Enter')

  const banner = page.locator('.error-banner')
  await expect(banner).toBeVisible()
  await expect(banner).toHaveAttribute('role', 'alert')
  await expect(banner).toContainText('llm_unavailable')
  const failedBubble = page.locator('.user-bubble-failed')
  await expect(failedBubble).toBeVisible()
  await expect(failedBubble).toContainText('trigger a failure for testing')
})

test('compare flow renders the comparison table', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill('Compare hotels in Lisbon for December 4 to 7.')
  await input.press('Enter')

  const table = page.getByTestId('comparison-table')
  await expect(table).toBeVisible()
  await expect(table.getByRole('cell', { name: 'Alfama Riverside Boutique' })).toBeVisible()
  await expect(table.getByRole('cell', { name: 'Baixa Central Hotel' })).toBeVisible()
})

test('policy question renders grounded source chips', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill('Are dogs allowed at the townhouse?')
  await input.press('Enter')

  const sources = page.locator('.source-row')
  await expect(sources).toBeVisible()
  await expect(sources.locator('.source-chip').first()).toBeVisible()
})

test('network failure maps to a network_error banner', async ({ page }) => {
  await page.route('**/api/chat', (route) => route.abort())
  await page.goto('/')
  const input = page.getByRole('textbox', { name: 'Chat message' })
  await input.fill('Find a hotel in Kyoto.')
  await input.press('Enter')

  const banner = page.locator('.error-banner')
  await expect(banner).toBeVisible()
  await expect(banner).toContainText('network_error')
})

test('degraded health endpoint shows the degraded status', async ({ page }) => {
  await page.route('**/api/health', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'degraded',
        service: 'staysmart-ai',
        version: '0.0.0',
        provider: 'mock',
        currency: 'USD',
        data_source: 'mock',
        is_live: false,
        mcp_server: { name: 'staysmart-hotels', connected: false, tools: [] },
      }),
    }),
  )
  await page.goto('/')

  await expect(page.getByText('API degraded')).toBeVisible()
})
