export const title = 'Login order';
export const covers = {};
export const notShown = [];
export const questions = [];

export async function steps({ page }) {
  if (!page.recordingStartedAfterLogin) throw new Error('recording started before login');
}
