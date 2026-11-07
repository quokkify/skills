export const title = 'Fixture walkthrough';
export const covers = { clicks: 'button works' };
export const notShown = ['error states'];
export const questions = ['Is Beta the right default?'];

export async function steps({ page, kit }) {
  await kit.caption('Click the button');
  await page.click('#go');
  await page.fill('#name', 'Ada');
  await page.selectOption('#kind', 'b');
  await page.setInputFiles('#file', kit.fixture('sample.pdf'));
  await kit.caption('<b>Привет</b> "мир"', 3500);
  await kit.shot('end');
}
