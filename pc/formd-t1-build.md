# FormD T1 V2.1 SFF Build

Compact small-form-factor gaming PC built following the [Eiga Works FormD T1 5090 Air guide](https://eigaworks.com/builds/formd-t1-5090-air/).

## Parts List

| Component | Part |
|---|---|
| CPU | AMD Ryzen 7 9800X3D |
| CPU Cooler | Thermalright AXP90-X47 |
| Motherboard | ASUS ROG STRIX B850-I GAMING WIFI (Mini ITX, AM5) |
| RAM | Patriot Venom 64 GB (2x32 GB) DDR5-6000 CL30 |
| Storage | Samsung 990 Pro 2 TB (M.2 PCIe 4.0 x4 NVMe) |
| GPU | NVIDIA GeForce RTX 5080 Founders Edition 16 GB |
| Case | FormD T1 V2.1 |
| PSU | Corsair SF1000 (2024) 80+ Platinum, SFX |
| Exhaust Fans | 2x Phanteks T30-120 |
| Cables | Custom Black Teflon cables from [CablesterCustom](https://www.etsy.com/shop/CablesterCustom) |

[PCPartPicker list](https://fr.pcpartpicker.com/list/w2PFfp)

## Build Guide

This build follows the Eiga guide which targets the RTX 5090 FE, but uses an **RTX 5080 FE** instead. The assembly process is identical since both cards share the same Founders Edition dual-slot cooler design. Same screws as the guide.

- [Prep](https://eigaworks.com/builds/formd-t1-5090-air/prep/)
- [Assembly](https://eigaworks.com/builds/formd-t1-5090-air/assembly/)
- [Software Setup](https://eigaworks.com/builds/formd-t1-5090-air/setup/)
- [Thermals](https://eigaworks.com/builds/formd-t1-5090-air/thermals/)

## Thermals

Reference thermals from the Eiga guide (RTX 5090 FE, 22C ambient, 38 dBA at 50cm):

| Game | GPU Avg | CPU Avg | RAM Max |
|---|---|---|---|
| Star Wars Outlaws (4K DLSS Performance) | 71C | 68C | 59C |
| ARC Raiders (4K DLSS Quality, 1hr) | 63C | 82C | 62C |

The guide uses an undervolt profile targeting 890mV on the GPU and per-core negative Curve Optimizer values (-10 to -20) on the 9800X3D.

With the RTX 5080 FE (lower TDP than 5090), thermals should be equal or better.
