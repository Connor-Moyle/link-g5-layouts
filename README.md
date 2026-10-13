# Link G5 PCLink layout

A 14-tab layout for Link ECU's PCLink (G4X / G5), built for a 1920x1080 screen with the
ECU Settings panel pinned open (a 1700 x 964 page).

> Unofficial. Not made by or affiliated with Link Engine Management.

## Use it

Copy `Connor E30 v2.llf5` into your PCLink `Layouts` folder (e.g. `C:\Link G5\PCLink G5\Layouts`),
then in PCLink: Layout menu -> open layout.

PCLink saves the loaded layout when it exits, so keep a copy if you rearrange things.

## Tabs

| Tab | What is on it |
|---|---|
| Basics | Configuration, Fuel Main, Ignition Main, Trigger Setup, RPM Limit, engine/status lists, dials, plot |
| Config | Input and output lists, sensor setup, injectors, fuel pump, fan, tacho |
| Ignition Tune | Ignition Table 1 + 3D view, ECT/IAT trim tables, ignition trims, plot |
| Fuel Tune | Fuel Table 1 + 3D view, dead time, accel, overrun, warm-up and IAT trim, plot |
| Timing | Triggers, calibrate (base timing), firing order, dwell, arming thresholds, plot |
| CAN Bus | CAN menu, keypad and all 12 buttons, every CAN input/output value, bus status, CAN lambda, PDM |
| Boost | Boost setup, wastegate duty and trim tables, MAP limit, plot |
| Idle | Idle setup, actuator, idle ignition, offset / target / base position tables, plot |
| Cold Start | Crank, post-start and warm-up enrichment, hold and decay tables, pre-crank prime, plot |
| MotorSport | Anti-lag and its tables, launch control |
| Limits | RPM, MAP, speed and GP limits with their tables |
| Lambda | Closed loop lambda, long term trims, AFR/lambda target table, plot |
| Mixture Map, Logging | Link's own pages, resized |

It was laid out around a turbo 4-cylinder tune (open loop boost, CAN lambda, CAN keypad, anti-lag).
Panels for features your tune has switched off will look empty, and a few lists show values your
ECU may not use.

## Regenerate / adapt

`make_layout.py` builds the file and refuses to write it if a menu or value is missing from the
tune, a panel overlaps another, or anything runs off the page. It needs `pclink.py` from
[open-source-link-g5](https://github.com/Connor-Moyle/open-source-link-g5) and your own PCLink install:

```
set PCLINK_TOOLS=path\to\open-source-link-g5
python make_layout.py "C:\Link G5\PCLink G5\Layouts\My layout.llf5"
```

Edit `W, H` at the top for a different screen, `TUNE` for your tune, and the `pages[...]` blocks to
change what goes where (`x, y, width, height` in pixels).

MIT licensed.
