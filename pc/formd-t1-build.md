# FormD T1 V2.1 SFF Build

Compact small-form-factor gaming PC built following the [Eiga Works FormD T1 5090 Air guide](https://eigaworks.com/builds/formd-t1-5090-air/).

![FormD T1 V2.1](https://i.imgur.com/Zpf1zas.jpeg)

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

- [Prep](https://eigaworks.com/builds/formd-t1-5090-air/prep/)
- [Assembly](https://eigaworks.com/builds/formd-t1-5090-air/assembly/)
- [Software Setup](https://eigaworks.com/builds/formd-t1-5090-air/setup/)
- [Thermals](https://eigaworks.com/builds/formd-t1-5090-air/thermals/)

## Thermals

Reference thermals from the Eiga guide (5090 FE undervolted @ 885mV, +3000 MHz memory / 9800X3D Curve Shaper -20 Max, 100W PPT / 20C ambient, 37 dBA @ 50cm):

| Game | Settings | GPU Avg | GPU Max | CPU Avg | CPU Max |
|---|---|---|---|---|---|
| Star Wars Outlaws | 4K, RT Ultra, DLSS Perf, X4 MFG (20min) | 69C | 72.5C | 60C | 68C |
| Doom: The Dark Ages | 4K, Ultra/Nightmare, DLSS Perf (30min) | 63C | 65C | 65C | 75C |
| Baldur's Gate 3 | 4K, DLSS Quality (3 run avg) | 63C | 65C | 77C | 80.5C |
| God of War Ragnarok | 4K Medium, DLSS Perf (3 run avg) | 63C | 63C | 69C | 75C |

With the RTX 5080 FE (lower TDP than 5090), thermals should be equal or better.
