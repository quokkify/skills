# Delayed notifications in the Parcel Tracker service

Notifications about parcel status changes arrived up to forty minutes late on one morning.

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-03-02 08:10 | Delivery latency alert fired |
| 2026-03-02 08:24 | On-call engineer paused the batch importer |
| 2026-03-02 08:51 | Queue drained, latency back to normal |

## Root cause

The batch importer published status events faster than the notification workers could consume them.

## Follow-ups

- Rate-limit the importer.
- Add an alert on queue depth.
