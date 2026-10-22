// Seed for the Playwright test agents: a fresh sandbox HOME with the trailmate example registered
// as project "alpha", served in registry mode on a free port.
import { test, expect, openCanvas } from './tests/fixtures';

test.describe('Seed', () => {
  test('seed', async ({ page, sandbox }) => {
    const srv = await sandbox.serveRegistry();
    await openCanvas(page, srv.origin + '/alpha/trailmate/');
    await expect(page.locator('.board')).toHaveCount(6);
    // generate code here.
  });
});
