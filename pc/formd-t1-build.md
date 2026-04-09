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

[PCPartPicker list](https://fr.pcpartpicker.com/list/w2PFfp)

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

### BIOS Settings (ASUS ROG STRIX B850-I)

**Use the AMD Overclocking path, NOT Ai Tweaker for PBO/CO:**
`Advanced -> AMD Overclocking -> [Accept Disclaimer] -> Precision Boost Overdrive`

| Setting | Stock | Optimized |
|---|---|---|
| PBO | Auto | **Advanced** |
| PBO Limits | Auto | **Auto** (no PPT cap -- thermal limit is enough for gaming) |
| PBO Scalar | Auto | **Manual, 1X** |
| Thermal Throttle Limit | 95°C | **85°C** |
| Curve Optimizer | Disabled | **All Cores, Negative, 20** |
| CPU SOC Voltage | Auto (1.272V) | **Manual, 1.200V** |
| CPU VDDIO/MC | Auto (1.376V) | **1.300V** |
| CPU LLC | Auto | **Level 1** |
| Global C-States | Auto | **Enabled** |

**Note:** On the B850-I, PPT/TDC/EDC values must be entered in **mW and mA** (e.g. 90000 for 90W).

### Why These Settings

- **Thermal Throttle 85°C**: CPU gently reduces boost to stay under 85°C instead of hitting the 95°C wall
- **Curve Optimizer -20**: Reduces voltage at every frequency point. Same performance, less heat. Single biggest efficiency gain
- **VSOC 1.20V**: EXPO auto was 1.272V -- too high for X3D safety (never exceed 1.3V)
- **VDDIO/MC 1.30V**: EXPO auto was 1.376V -- unnecessarily high for DDR5-6000
- **LLC Level 1**: Prevents voltage overshoots that can damage X3D chips
- **No PPT cap**: Gaming rarely pushes above 85-90W, so a PPT cap only limits single-core burst boosts unnecessarily

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

## Thermals

### Cinebench R23 (10-minute Multi-Core)

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

| | Stock | Optimized | Change |
|---|---|---|---|
| **CPU Temp avg** | 97°C | 82°C | **-15°C** |
| **CPU Temp max** | 97°C | 86.9°C | **-10°C** |
| **Package Power avg** | 108W | 84.7W | **-23.3W** |
| **Core Clock avg** | -- | 5064 MHz | Boosting freely |
| **PPT Used** | -- | 52% | Nowhere near limit |

### Summary

- **GPU:** +88 MHz over stock, same power, 1°C cooler
- **CPU:** 15°C cooler, 23W less power, 1.7% score loss
- **Voltages:** VSOC 1.272V -> 1.20V, VDDIO 1.376V -> 1.30V (safer for X3D longevity)
