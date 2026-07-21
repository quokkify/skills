---
name: game-performance-troubleshooting
description: Use when troubleshooting game smoothness, FPS drops, stutter, lag, ping, or packet loss on Windows PCs and laptops, especially when the user shares an in-game overlay or screenshot.
---

# Game Performance Troubleshooting

## When to Use

Use this for reports of character movement stutter, poor smoothness, freezes, input delay, high ping, or packet loss.
- screenshots showing FPS/ping overlays in a game client

## Core Rule

Separate **rendering performance** from **network performance** before giving fixes.

| Symptom / indicator | Likely class | First fixes |
|---|---|---|
| FPS / к/с low or jumping | device/settings/thermal/power | cap FPS, lower graphics, power mode, charger, cooling |
| Ping/ms high or jumping | network/route/Wi‑Fi | Ethernet, 5 GHz Wi‑Fi, stop downloads, reboot router, check packet loss |
| High FPS + stable ping but still stutter | frame pacing/input/driver/overlay | FPS cap near refresh rate, fullscreen, V-Sync test, disable overlays |
| Characters teleport/rubber-band | packet loss/network | ping test, Ethernet, router/ISP path |

## Workflow

1. Ask for or read **both FPS and ping/ms** from the overlay. If an image is provided, inspect it.
2. Normalize localized overlay labels: distinguish frames per second from milliseconds of network latency before diagnosing.
3. If FPS is very high but the user says it “drops”, focus on **stability**, not peak FPS. Test a cap near the display refresh rate because stable frame pacing can feel better than uncapped spikes; exact options vary by game version and display.
4. If network is suspected, suggest quick packet-loss tests and connection fixes, but do not insist it is internet when the user is pointing at the frame-rate indicator.
5. Keep the answer practical and short: give the next 3–5 actions, not a long theory dump.

## Generic Windows game-client path

Menu labels and shortcuts vary by game version. Confirm them against current official documentation.

- Enable the game's FPS/latency overlay if available.
- Test fullscreen versus borderless mode.
- Reduce shadows, effects, anti-aliasing, and environment detail one category at a time.
- Test V-Sync on and off if tearing or uneven pacing remains.
- Set a frame-rate cap appropriate to the display and hardware rather than copying a fixed number.
- On laptops, connect approved power, select the intended Windows power mode, close unrelated heavy applications, and keep cooling vents unobstructed.

## Network quick path

- Prefer Ethernet over Wi‑Fi.
- If Wi‑Fi, prefer 5 GHz and sit closer to router.
- Stop downloads/streams/cloud sync on all household devices.
- Disable VPN first; only test gaming VPN/routing tools after basic checks.
- On Windows, test the default gateway first (`ipconfig` shows it), then a neutral external endpoint chosen for the user's network: `ping <target> -n 50`.
- ICMP loss or latency alone does not prove loss on the game's actual route because routers may filter or deprioritize ping traffic. Correlate it with in-game telemetry and, when possible, the publisher's route diagnostics.

## Pitfalls

- Do not equate “character jerks” with internet if FPS/к/с is visibly dropping.
- Do not equate a high peak FPS screenshot with smooth play; frame drops and frame pacing matter.
- Do not over-prescribe graphics settings when the overlay shows stable FPS but ping is spiking.
- When the user corrects the diagnosis, acknowledge and pivot immediately.

## Verification

Ask the user to test one change at a time for 5 minutes and report:

- FPS range (min/max or whether it drops)
- ping range
- whether the game became smoother
