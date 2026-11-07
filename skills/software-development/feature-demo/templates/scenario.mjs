// Scenario for one feature demo. The owner approves it before recording; it is published
// next to the video on the `demos` branch, not committed to the main branch.
export const title = 'ORD-42 — Export orders to CSV';

// Acceptance criterion -> where the video shows it.
export const covers = {
  'AC-1': 'step 2: Export button on the orders list',
  'AC-2': 'step 3: downloaded file lists the filtered orders',
};

// Acceptance criteria or behavior the video does not show, with the reason.
export const notShown = ['AC-3 (export of more than 10 000 rows): not reproducible with demo data'];

// Open product questions for the reviewer.
export const questions = ['Should the export include cancelled orders?'];

export async function steps({ page, kit }) {
  await kit.chapter('Orders list');
  await kit.caption('Orders are filtered by status "Paid"');
  await page.getByRole('link', { name: 'Orders' }).click();
  await page.getByLabel('Status').selectOption('paid');
  await kit.shot('01-filtered');

  await kit.chapter('Export');
  await kit.caption('The new Export button downloads the filtered list');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  await download;
  await kit.caption('The file contains only the paid orders');
  await kit.shot('02-exported');
  await kit.caption('');
}
