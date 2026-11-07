export const title = 'Secret leak';
export const covers = {};
export const notShown = [];
export const questions = [];

export async function steps({ page, kit }) {
  await page.fill('#name', 's3cr3t-value');
  await kit.hold(300);
}
