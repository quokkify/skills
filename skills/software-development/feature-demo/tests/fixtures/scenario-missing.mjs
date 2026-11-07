export const title = 'Missing locator';
export const covers = {};
export const notShown = [];
export const questions = [];

export async function steps({ page }) {
  await page.click('#nope', { timeout: 1000 });
}
