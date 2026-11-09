# Search results show stale prices after a catalog update

|  |  |
|---|---|
| Service | Catalog Search |
| Environment | production |
| Version | 5.2.1 |
| Reporter | Bob |

## Summary

After a bulk price update, search results keep showing the old prices for up to an hour.

## Steps to reproduce

1. Update the price of any product in the catalog admin.
2. Search for the product by name.
3. Compare the price in the results with the product page.

## Expected

The search result shows the new price within one minute.

## Actual

The search result shows the old price; the product page shows the new one.

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:02 | Bulk price update started |
| 14:05 | Update finished |
| 15:01 | Search shows new prices |

## Hypotheses

1. The search index refresh job skips documents updated in bulk.
2. The result cache is keyed without the price version.
