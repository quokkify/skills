export const title = 'Env secret leak';
export const covers = {};
export const notShown = [];
export const questions = [];

export async function steps({ page, kit }) {
  await page.fill('#name', 's3cr3t-env');
  await kit.hold(300);
}
