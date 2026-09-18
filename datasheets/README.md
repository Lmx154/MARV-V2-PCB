# Component datasheets

The PDFs here retain their manufacturers' or publishers' rights and terms;
they are **not** relicensed under CC0 or 0BSD. Only this project-authored index
is CC0. See [third-party notices](../THIRD_PARTY.md).

Local copies of the manufacturer datasheet for every non-passive part on the board (ICs, discrete
semiconductors, the crystal, connectors/sockets with a specific vendor part, and modules). Purpose:
give any worker a fast, offline reference — `pdftotext <file>.pdf - | less` (or `pdfinfo`) instead of
re-fetching from the web on every question about pinout, decoupling or the application circuit.
Plain passives (R/L/C, ferrite beads), test points and mounting hardware are excluded; see
`power_bom.csv` / freshly generated `build/assembly/jlc-bom.csv` for those.

Two datasheets (`W25Q32JV.pdf`, `APS6404L.pdf`) both cover U24: it is one SOIC-8 socket that takes
either part (DNP by default; see `qspi_expansion.kicad_sch`).

| Refdes | Part | Manufacturer | File | Source URL | Date fetched | Relevant section/page |
|---|---|---|---|---|---|---|
| U20 | RP2354B (RP2350 family, on-package flash) | Raspberry Pi Ltd | `RP2350.pdf` | https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf | 2026-09-17 | Sec 6.3.8 "External components and PCB layout requirements", p.453 (core-regulator L/C network) |
| U21 | ICM-45686 | TDK InvenSense | `ICM-45686.pdf` | https://www.lcsc.com/datasheet/lcsc_datasheet_2411220643_TDK-InvenSense-ICM-45686_C22459454.pdf (manufacturer page is a gated download form; fetched the LCSC-hosted copy) | 2026-09-17 | Bypass-capacitor table (VDD/VDDIO, 0.1 uF X7R), p.34 |
| U22 | BMP581 | Bosch Sensortec | `BMP581.pdf` | https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp581-ds004.pdf | 2026-09-17 | Pin-out, Figure 22, p.46 |
| U23 | ADXL375BCCZ | Analog Devices | `ADXL375.pdf` | https://www.analog.com/media/en/technical-documentation/data-sheets/ADXL375.PDF | 2026-09-17 | "Power Supply Decoupling", p.26 |
| U7 | AP63203WU-7 | Diodes Incorporated | `AP63203.pdf` | https://www.diodes.com/assets/Datasheets/AP63200-AP63201-AP63203-AP63205.pdf | 2026-09-17 | Figure 21 "Typical Application Circuit of AP63203/AP63205", p.9 (external-component table referenced as "Table 2" in `tools/build_power.py`) |
| U12 | TPS7A2033PDBVR | Texas Instruments | `TPS7A2033.pdf` | https://www.ti.com/lit/ds/symlink/tps7a20.pdf | 2026-09-17 | Sec 7.2 "Typical Application" / Figure 7-4, p.30; Sec 7.4 "Layout", p.31 |
| U24 (fit option A) | W25Q32JVSNIQ (32 Mbit QSPI NOR) | Winbond | `W25Q32JV.pdf` | https://www.winbond.com/resource-files/W25Q32JV%20RevJ%2012242024%20Plus.pdf | 2026-09-17 | Figure 1a, 8-pin SOIC 150-mil pin assignment (package code SN), p.6 |
| U24 (fit option B) | APS6404L-SQN-SN (8 MB QSPI PSRAM) | AP Memory | `APS6404L.pdf` | https://www.apmemory.com/tw/downloadFiles/0324112120g3605268 | 2026-09-17 | Table 1 "Ordering Information" (confirms `-SQN-SN` suffix), p.7 |
| D20 | WS2812C-2020-V1 | Worldsemi | `WS2812C-2020.pdf` | https://www.lcsc.com/datasheet/lcsc_datasheet_2202221130_Worldsemi-WS2812C-2020-V1_C2976072.pdf (LCSC-hosted) | 2026-09-17 | Features / pin function / reflow profile, p.1-2 |
| Q1 | AO3401A | Alpha & Omega Semiconductor | `AO3401A.pdf` | https://www.aosmd.com/pdfs/datasheet/AO3401A.pdf | 2026-09-17 | Pin configuration and electrical characteristics table, p.1-2 |
| D1 | 1N5819WS | Guangdong Hottech | `1N5819WS.pdf` | https://www.lcsc.com/datasheet/lcsc_datasheet_Guangdong-Hottech-1N5819WS_C191023.pdf (LCSC-hosted) | 2026-09-17 | Electrical characteristics (VF, IR), p.1-2 |
| Y1 | 12 MHz TAXM12M4RFBCCT2T | Shenzhen Yajingxin Electronics | `TAXM12M4RFBCCT2T.pdf` | https://www.lcsc.com/product-detail/C133337.html (manufacturer spec sheet, LCSC-hosted) | 2026-09-17 | Specification table (12.000 MHz, CL = 12 pF), p.1 |
| J4 | USB-C receptacle TYPE-C-31-M-12 | Korean Hroparts Elec (HRO Electronics) | `TYPE-C-31-M-12.pdf` | https://www.lcsc.com/product-detail/C165948.html (manufacturer drawing, LCSC-hosted) | 2026-09-17 | Pinout table (A1-A12/B1-B12) and PCB land pattern, p.1 |
| J11 | Molex 47219-2001 / 472192001, C164170, locking hinged microSD | Molex | `472192001.pdf`; `472192001-drawing.pdf` | https://www.es.co.th/Schemetic/PDF/472192001.PDF (Molex part datasheet, generated 2025-04-07); https://cdn.promelec.ru/upload/items/2020/09/01/472192001_sd.pdf (Molex drawing mirror) | 2026-09-17 | Datasheet pp.1–3: hinge type, 8 contacts, no detect switch; drawing p.1: pad layout and pin numbering |
| SW1, SW2 | B3U-1000P tactile switch | Omron | `B3U-1000P.pdf` | https://omronfs.omron.com/en_US/ecb/products/pdf/en-b3u.pdf | 2026-09-17 | Ratings and characteristics table, p.1-2 |

## UNKNOWN

None — all 15 non-passive parts resolved to a verified manufacturer (or manufacturer-authorized
distributor mirror) PDF. Three parts required a fallback from the manufacturer's own site to an
LCSC-hosted copy after the manufacturer link was gated or blocked outbound `curl`/`wget` requests
(see the Source URL column: ICM-45686, WS2812C-2020, 1N5819WS, TAXM12M4RFBCCT2T and
TYPE-C-31-M-12 all use the LCSC-hosted PDF; every other file is the manufacturer's own domain).
Every file was confirmed to start with `%PDF`, exceed 50 kB (the smallest are the two single-sheet
mechanical connector drawings, `TYPE-C-31-M-12.pdf` at ~116 kB and `104031-0811.pdf` at ~100 kB), and
contain the exact part number on an early page via `pdftotext`/`pdfinfo` (and, for `TYPE-C-31-M-12.pdf`,
a rendered-page visual check since that drawing is almost all vector graphics with little extractable
text).

## Locking microSD replacement

J11 now uses Molex 47219-2001 / LCSC C164170. Its manufacturer datasheet and
one-page mechanical drawing are stored above. Both files were verified as PDFs.
The official drawing endpoint timed out during download, so manufacturer content
was retrieved from distributor mirrors. Official drawing URL:
https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/472/47219/472192001_sd.pdf

Molex describes the hinged lid and slide-to-lock sequence in its card-socket
brochure: https://www.content.molex.com/dxdam/literature/987651-8263.pdf
The old `104031-0811.pdf` is retained while the saved PCB still uses that socket's
land pattern. Remove it with the old footprint after the owner updates J11.

---

Original MARV V2 documentation: [CC0 1.0](../LICENSES/CC0-1.0.txt). No attribution required; provided as-is. [Licensing and third-party exceptions](../LICENSE.md).
