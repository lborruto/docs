# FormD T1 V2.1 SFF Build

Compact small-form-factor gaming PC built following the [Eiga Works FormD T1 5090 Air guide](https://eigaworks.com/builds/formd-t1-5090-air/).

![FormD T1 V2.1](https://i.imgur.com/Zpf1zas.jpeg)
*Photo credit: [Eiga Works](https://eigaworks.com/)*

## Parts List

| Component | Part |
|---|---|
| CPU | AMD Ryzen 7 9800X3D |
| CPU Cooler | Thermalright AXP90-X47 Full Copper |
| Cooler Fan | Noctua NF-A9x14 HS-PWM chromax.black.swap |
| Motherboard | ASUS ROG STRIX B850-I GAMING WIFI (Mini ITX, AM5) |
| RAM | Patriot Venom 64 GB (2x32 GB) DDR5-6000 CL30 |
| Storage | Samsung 990 Pro 2 TB (M.2 PCIe 4.0 x4 NVMe) |
| GPU | NVIDIA GeForce RTX 5080 Founders Edition 16 GB |
| Case | FormD T1 V2.1 |
| Case Add-ons | T1 GPU Travel Kit, T1 PCIe SS200 Gen5 Riser, T1 Essentials Pack |
| PSU | Corsair SF1000 (2024) 80+ Platinum, SFX |
| Exhaust Fans | 2x Phanteks T30-120 |
| Contact Frame | Thermal Grizzly AM5 Contact Frame |
| Backplate | Thermal Grizzly AM5 Short Backplate |
| Thermal Paste | Thermal Grizzly Duronaut |
| Cables | Custom Black Teflon cables from [CablesterCustom](https://www.etsy.com/shop/CablesterCustom) (24P 170mm, CPU 8P 290mm, GPU 12V2X6 300mm) |
| Screws | 12x M3 flat head 4mm, 16x M3 countersunk 5mm, 11x M3 countersunk 8mm |

[PCPartPicker list](https://fr.pcpartpicker.com/list/HMfNQy)

## Build Guide

This build follows the Eiga guide which targets the RTX 5090 FE, but uses an **RTX 5080 FE** instead. The assembly process is identical since both cards share the same Founders Edition dual-slot cooler design. Same screws as the guide.

- [Index](https://eigaworks.com/builds/formd-t1-5090-air/)
- [Prep](https://eigaworks.com/builds/formd-t1-5090-air/prep/)
- [Assembly](https://eigaworks.com/builds/formd-t1-5090-air/assembly/)
- [Software Setup](https://eigaworks.com/builds/formd-t1-5090-air/setup/)
- [Thermals](https://eigaworks.com/builds/formd-t1-5090-air/thermals/)

## GPU Undervolt (RTX 5080 FE)

Using MSI Afterburner (Beta with RTX 50 series support).

**Method:** Set Core Clock offset to **-250 MHz**, open Curve Editor (Ctrl+F), drag the **950mV** point to target frequency, flatten everything to the right with **Shift + click-drag in empty space** then **Shift+Enter twice**.

| | Stock | Undervolted (950mV/2900 + 1000mem) |
|---|---|---|
| Core Clock | 2742 MHz | 2830 MHz |
| Memory | 1875 MHz | 2000 MHz |
| Voltage | 1.004V | 0.934V |
| Power | 251W | 251W |
| GPU Temp | 62.3°C | 61.4°C |
| VRAM Temp | 72.3°C | 72.4°C |

**+88 MHz over stock** at the same power draw, 1°C cooler. For reference, the RTX 5080 FE in open-air reviews (GamersNexus) runs 65-67°C -- our T1 build undervolted runs 61-63°C.

## CPU BIOS Optimization (9800X3D)

### The Problem

Battlefield 6 (128 players): CPU averaging **97°C at 108W**, hitting the 95°C thermal throttle. EXPO auto-voltages dangerously high: VSOC 1.272V, VDDIO 1.376V.

### BIOS Settings (ASUS ROG STRIX B850-I, BIOS 1644)

**Use the AMD Overclocking path, NOT Ai Tweaker for PBO/CO.** The same PBO options also exist under `Ai Tweaker -> Precision Boost Overdrive`; keep those on Auto so limits are only set in one place.

`Advanced -> AMD Overclocking -> [Accept Disclaimer] -> Precision Boost Overdrive`

| Setting | Stock | Optimized |
|---|---|---|
| PBO | Auto | **Advanced** |
| PBO Limits | Auto | **Manual** |
| PPT Limit | 162W | **90000 (90W)** |
| TDC Limit | 120A | **75000 (75A)** |
| EDC Limit | 180A | **110000 (110A)** |
| PBO Scalar | Auto | **Manual, 1X** |
| Platform Thermal Throttle Limit | 95°C | **85°C** |
| Curve Optimizer | Disabled | **All Cores, Negative, 30** |

`Ai Tweaker`

| Setting | Stock | Optimized |
|---|---|---|
| CPU SOC Voltage (VDDSOC Voltage Override) | Auto (1.272V) | **Manual, 1.200V** |
| CPU VDDIO / MC Voltage | Auto (1.376V) | **1.300V** |
| DIGI+ Power Control -> CPU Load-line Calibration | Auto | **Level 1** |

`Advanced -> AMD CBS -> CPU Common Options`

| Setting | Stock | Optimized |
|---|---|---|
| Global C-state Control | Auto | **Enabled** |

**Notes:**
- On the B850-I, PPT values are entered in **mW** and TDC/EDC in **mA** (e.g. 90000 for 90W).
- The BIOS keeps values typed into PPT/TDC/EDC even when PBO Limits is set back to **Auto**; they are simply ignored. Check HWiNFO's `CPU PPT Limit [%]` to confirm which limit is actually active.
- Save BIOS profiles to a **FAT32** USB stick (`Tool -> ASUS User Profile`); the BIOS rejects NTFS.

### Why These Settings

- **Thermal Throttle 85°C**: CPU gently reduces boost to stay under 85°C instead of hitting the 95°C wall. Safety net for hot days and GPU-heated case air.
- **PPT 90W**: Caps power at the source, so less heat to remove before the thermal limit is even reached. Costs ~1.7% in Cinebench multi-core, nothing in single-core (one boosting core uses far less than 90W), and BF6 already runs around 85W. Mostly trims the short spikes that ramp the fan.
- **TDC 75A / EDC 110A**: Consistent with the 90W cap; never the limiting factor in testing (PPT is hit first).
- **Curve Optimizer -30**: Reduces voltage at every frequency point. Same clocks, less heat. -20 to -30 lowered average VID by ~30mV. Diminishing returns past -25 (see Stability Testing).
- **VSOC 1.20V**: EXPO auto was 1.272V -- too high for X3D safety (never exceed 1.3V)
- **VDDIO/MC 1.30V**: EXPO auto was 1.376V -- unnecessarily high for DDR5-6000
- **LLC Level 1**: Prevents voltage overshoots that can damage X3D chips

### Stability Testing (Curve Optimizer)

Tool: [CoreCycler](https://github.com/sp00n/corecycler) (default config, Prime95, ~6 min per core). Loads one core at a time at max boost, which is where an overly aggressive CO fails. A core that errors is skipped early, so a full 6 min on every core means no errors. WHEA errors checked in `Event Viewer -> Windows Logs -> System`, filtered on source **WHEA-Logger** (Event ID 19 = corrected, 18 = fatal; core = Processor APIC ID / 2).

| | CO -25 | CO -30 |
|---|---|---|
| Iterations | 2 | 1.6 |
| CoreCycler errors | 0 | 0 |
| WHEA errors | 0 | 0 |
| Tested core clock | 5225 MHz | 5225 MHz |
| Avg VID | 1.20V | 1.17V |
| Package Power avg | 68.9W | 66.1W |
| CPU Temp avg / max | 81.3°C / 86.0°C | 80.4°C / 85.0°C |
| Thermal throttling (HTC) | No | No |

*Both runs were logged with Windows CPU idle disabled (all cores held in C0), which inflated package power and temps by ~30W during a single-core test. See below.*

**Status:** -30 passed short runs. Still to do: one overnight CoreCycler run (6-8h), a WHEA check the next morning, then a week of normal use (watch for crashes at idle, on wake from sleep, on loading screens). Fallback if anything fails: -25 (validated), or Per Core with only the failing core at 25.

## Windows Power Plan

The active plan was **optimizerDuck PowerPlan** (installed by an optimization tool), which sets **Processor idle disable** on AC. Every core stayed in C0 at full clock 100% of the time (0% C1/C6 residency), even when idle.

Check current state (admin terminal):

```
powercfg /qh SCHEME_CURRENT SUB_PROCESSOR IDLEDISABLE
```

`Current AC Power Setting Index: 0x00000001` = idle disabled, `0x00000000` = idle enabled.

Toggle (applies instantly, no reboot):

```
:: Enable idle (kept)
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR IDLEDISABLE 0
powercfg /setactive SCHEME_CURRENT

:: Disable idle
powercfg /setacvalueindex SCHEME_CURRENT SUB_PROCESSOR IDLEDISABLE 1
powercfg /setactive SCHEME_CURRENT
```

To show the setting in the classic Advanced power settings UI: `powercfg -attributes SUB_PROCESSOR IDLEDISABLE -ATTRIB_HIDE`

### Idle Disabled vs Enabled -- Battlefield 6

Same scene, game restarted between runs, HWiNFO + PresentMon logging. Menus, loading screens and the first minute excluded (~5 min and ~7 min of gameplay). One run each; the idle-enabled run was done second in an already warm case (motherboard 56°C vs 52°C).

| | Idle disabled (C0) | Idle enabled | Change |
|---|---|---|---|
| FPS avg | 195 | 191 | -2% (run-to-run noise) |
| 1% low | 139.8 | 140.4 | same |
| 0.1% low | 135.3 | 136.5 | same |
| Frame time 99th pct | 6.99 ms | 6.92 ms | same |
| Worst spike (0.1% high max) | 56.6 ms | 14.1 ms | better with idle |
| CPU Package Power | 87.1W | 84.4W | -2.7W |
| CPU Temp avg | 85.9°C | 85.4°C | -0.5°C |
| Time at thermal limit | 92% | 80% | -12 pts |

**Decision: idle enabled.** No smoothness benefit from disabling idle on this system. BF6 keeps all 8 cores busy anyway (C1 ~25%, no C6), so the in-game saving is small; the big saving (~30W) is at the desktop and in light loads.

Optimization tools can re-apply their plan on update or reinstall. If temps rise for no reason, re-check with `powercfg /qh`.

## Fan Control

Adapted from Eiga's FanControl config (originally for 5090 FE), swapping GPU identifiers from GB202-A to GB203-A.

**CPU Fan** (Noctua NF-A9x14, driven by CPU Tctl/Tdie):

| Temp | Fan % |
|---|---|
| 50-60°C | 30% |
| 60-70°C | 35% |
| 70-80°C | 40% |
| 80-92°C | 45% |
| 92°C+ | 50% |

**Exhaust Fans** (2x Phanteks T30, driven by a Mix sensor -- max of GPU temp and CPU temp with -15°C offset):

| Temp | Fan % |
|---|---|
| 50-60°C | 40% |
| 60-65°C | 50% |
| 65-75°C | 60% |
| 75°C+ | 70% |

GPU fans left on **Auto** (firmware control). FanControl and MSI Afterburner both set to start with Windows minimized.

**Observation:** this curve is silence-first. The CPU fan tops out around 1450 RPM, and in BF6 the CPU sits on the 85°C limit 80-92% of the time, averaging ~4980 MHz instead of 5225 MHz. Performance impact is small (GPU ~94% loaded), but if lower CPU temps are wanted, raise only the top steps, e.g.:

| Temp | Eiga | Candidate |
|---|---|---|
| 70-80°C | 40% | 45% |
| 80-85°C | 45% | 60% |
| 85°C+ | 50% | 75% |

Adding a few seconds of response time and 3-5°C hysteresis also stops the fan chasing X3D temperature spikes.

## Thermals

### Cinebench R23 (10-minute Multi-Core)

*Optimized column: CO -20, 90W PPT cap.*

| | Stock | Optimized | Change |
|---|---|---|---|
| **Score** | ~20,000 | 19,650 | -1.7% |
| **CPU Temp avg** | 95.0°C | 81.0°C | **-14°C** |
| **CPU Temp max** | 95.6°C | 83.2°C | **-12.4°C** |
| **Package Power avg** | 110.3W | 89.4W | **-20.9W** |
| **Package Power max** | 138.6W | 90.0W | **-48.6W** |
| **SoC Power** | 16.2W | 12.7W | -3.5W |
| **VSOC** | 1.272V | 1.20V | -72mV |
| **VDDIO** | 1.376V | 1.30V | -76mV |
| **Bottleneck** | Thermal (95°C wall) | PPT (99.4%) | -- |

### Battlefield 6 (128 Players)

*Optimized column: CO -20, no PPT cap (PPT % is relative to the stock ~162W limit), idle disabled.*

| | Stock | Optimized | Change |
|---|---|---|---|
| **CPU Temp avg** | 97°C | 82°C | **-15°C** |
| **CPU Temp max** | 97°C | 86.9°C | **-10°C** |
| **Package Power avg** | 108W | 84.7W | **-23.3W** |
| **Core Clock avg** | -- | 5064 MHz | Boosting freely |
| **PPT Used** | -- | 52% | Nowhere near limit |

**Current config** (CO -30, 90W PPT, idle enabled) -- see the idle test above:

| Metric | Value |
|---|---|
| FPS avg / 1% low / 0.1% low | 191 / 140.4 / 136.5 |
| CPU Temp avg / max | 85.4°C / 86.5°C |
| Package Power avg | 84.4W (94% of PPT) |
| Core Clock avg | 4990 MHz |
| Time at 85°C thermal limit | 80% |
| GPU Load avg | 94% |

### 3DMark Time Spy
*Run details: [3dmark](https://www.3dmark.com/3dm/155416414)*

| Metric | Score |
|---|---|
| **Overall** | **27,511** |
| Graphics | 31,888 |
| CPU | 15,476 |

**GPU** (950mV undervolt + 1000 memory):

| Metric | Avg | Max |
|---|---|---|
| GPU Clock | 2727 MHz | 2805 MHz |
| GPU Temp | 61.4°C | 67.7°C |
| VRAM Temp | 64.5°C | 72.0°C |
| GPU Power | 274.6W | 326.4W |
| TDP Used | 76.8% | 91.0% |
| Fan Speed | 40% | 43% |

**CPU** (CO -20, 85°C thermal limit, no PPT cap):

| Metric | Avg | Max |
|---|---|---|
| Core Clock | 4678 MHz | 5225 MHz |
| CPU Temp | 69.5°C | 86.5°C |
| Package Power | 60.5W | 110.4W |
| PPT Used | 37.3% | 68.2% |

Graphics score of 31,888 is within the normal range for a stock RTX 5080 FE (30,229-32,642 per reviews), confirming the 950mV undervolt has no performance penalty in 3DMark. CPU barely breaks a sweat at 69.5°C average.

### Summary

- **GPU:** +88 MHz over stock, same power, 1°C cooler
- **CPU:** 15°C cooler than stock in BF6, 90W PPT cap costs 1.7% in Cinebench multi-core, nothing measurable in games
- **Curve Optimizer:** -30 all cores, 0 errors so far (overnight validation pending)
- **Voltages:** VSOC 1.272V -> 1.20V, VDDIO 1.376V -> 1.30V (safer for X3D longevity)
- **Windows:** CPU idle re-enabled; disabling it gave no smoothness gain in BF6
- **Remaining limiter:** the silence-first CPU fan curve (CPU at the 85°C limit most of the time in BF6)

## TODO

- [ ] Overnight CoreCycler at CO -30 + WHEA check
- [ ] One week of normal use at CO -30
- [ ] Memory test after the VSOC/VDDIO changes (TestMem5 anta777 extreme or OCCT memory, ~1h)
- [ ] Save a new BIOS profile once -30 is validated
- [ ] Optional: test the candidate CPU fan curve in BF6 with the same protocol
- [ ] BIOS: stay on 1644 until a non-beta release brings something relevant (1804 is beta; 1681+ cannot be rolled back)
