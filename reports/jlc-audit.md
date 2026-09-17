# JLC sourcing snapshot

This is a **cached September 16–17, 2026 snapshot**, reconciled with the current
106-component BOM. It is not a fresh catalogue check or an assembly quote.
Older substitution discussions and quotes are preserved in
`backups/pre-input-power-refresh/reports/jlc-audit.md`.

- 37 fitted BOM lines; 33 unique LCSC parts: 16 Basic, 17 Extended.
- 86 SMT placements; 323 SMT joints. U24 is DNP; J6–J8 ship unpopulated.
- Cached components: $39.3877/board at quantity-10 catalogue tiers.
- Assumed Extended setup fee: 17 × $3 = $51/order. Actual fees, minimum purchases,
  attrition, fabrication and other order costs require a real quote.

The GPS/ELRS supply change adds no components and changes no placement coordinates.
C8/C65's schematic text still says 10 V X7R while C96446 is mapped as 25 V X5R;
reconcile that label with the selected part before ordering.

## Selected parts

| Refs | Unique line | LCSC | Class | Stock | $@10 | Qty | Joints | Note |
|---|---|---|---|---|---|---|---|---|
| R7,R27,R52 | 100k / 1% [R_0402_1005Metric] | C25741 | Basic | 11,172,803 | 0.0025 | 3 | 6 | Basic; same part as the 100k line (Q1 gate pull-down, VBAT sense top, U7 EN) |
| U7 | AP63203WU-7 [TSOT-23-6] | C780769 | Extended | 25,030 | 1.0546 | 1 | 6 | fixed 3.3 V / 2 A synchronous buck, TSOT26; JLC Extended (no Basic synchronous buck exists) |
| Q1 | AO3401A [SOT-23] | C15127 | Basic | 445,757 | 0.0943 | 1 | 3 | JLC Basic; the 5V_IN side of the OR (drain 5V_IN, source V5_SYS, gate USB_VBUS) |
| D1 | 1N5819WS [D_SOD-323] | C191023 | Basic | 5,466,933 | 0.0138 | 1 | 2 | JLC Basic; the USB side of the OR (anode USB_VBUS, cathode V5_SYS) |
| L2 | 4.7u [L_Changjiang_FTC404030S] | C39676083 | Extended | 4,407 | 0.2571 | 1 | 0 | Isat 6.0 A worst case (30% drop), Irms 4.0 A (40 C), DCR 46 mOhm max; AP63203 Sec 10 licenses 2.2-10 uH, and this is the part the removed AP63205 stage already sourced |
| R28,R29 | 10k / 1% [R_0402_1005Metric] | C25744 | Basic | 27,497,679 | 0.0031 | 2 | 4 | Basic; same part as the 10k line |
| C13,C30,C31,C32,C33,C34,C35,C36,C37,C38,C40,C42,C43,C44,C48,C49,C50,C52,C54,C56,C60,C64,C78,C79 | 100n / 16 V X7R [C_0402_1005Metric] | C1525 | Basic | 30,932,149 | 0.0045 | 24 | 48 |  |
| J4 | USB_C_PROGRAM_POWER [USB_C_Receptacle_HRO_TYPE-C-31-M-12] | C165948 | Extended | 223,000 | 0.1858 | 1 | 20 |  |
| R4,R5 | 5.1k / 1% [R_0402_1005Metric] | C25905 | Basic | 7,263,573 | 0.0025 | 2 | 4 | Basic |
| C7,C25,C59,C62 | 1u / 10 V X7R 0402 [C_0402_1005Metric] | C52923 | Basic | 8,974,715 | 0.0099 | 4 | 8 | X5R not X7R; 25V rating improves DC-bias vs the 10V spec (C62 is the U24 socket bypass: 1 uF is the APS6404L PSRAM requirement, Sec 16.4) |
| C19 | 100u / 6.3 V polymer [CP_EIA-3528-21_Kemet-B] | C79109 | Extended | 44,908 | 0.6881 | 1 | 2 | exact spec MPN 6TPE100MAZB, ESR 35mR <= 40mR |
| C10,C11 | 22u / 10 V X5R 0603 GRM188R61A226ME15 [C_0603_1608Metric] | C86295 | Extended | 1,430,308 | 0.0430 | 2 | 4 | no Basic 22uF 0603 above 6.3V |
| R10 | 100k [R_0402_1005Metric] | C25741 | Basic | 11,172,803 | 0.0025 | 1 | 2 | Basic; MCU_RUN pull-up |
| U12 | TPS7A2033PDBVR [SOT-23-5] | C2862740 | Extended | 52,678 | 0.2197 | 1 | 5 |  |
| C8,C65 | 10u / 10 V X7R 0603 [C_0603_1608Metric] | C96446 | Basic | 4,484,275 | 0.0542 | 2 | 4 | X5R not X7R; 25V rating cuts DC-bias loss on the 5V rail |
| J6 | IO array signal column (innermost) [PinHeader_1x14_P2.54mm_Vertical_IORow] | C2905490 | Extended | 3,933 | 0.1064 | 1 | 14 | THT; recommended UNPOPULATED, see audit |
| J7 | IO array power column (5V / 3V3 per row) [PinHeader_1x14_P2.54mm_Vertical_IORow] | C2905490 | Extended | 3,933 | 0.1064 | 1 | 14 | THT; recommended UNPOPULATED, see audit |
| J8 | IO array GND column (board edge) [PinHeader_1x14_P2.54mm_Vertical_IORow] | C2905490 | Extended | 3,933 | 0.1064 | 1 | 14 | THT; recommended UNPOPULATED, see audit |
| U20 | RP2354B [QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm] | C39843328 | Extended | 4,162 | 1.4624 | 1 | 81 |  |
| C39,C41,C45 | 4.7u / 10 V X5R 0402 [C_0402_1005Metric] | C23733 | Basic | 3,015,346 | 0.0166 | 3 | 6 |  |
| R20 | 33 / 1% [R_0402_1005Metric] | C25105 | Basic | 1,986,424 | 0.0041 | 1 | 2 | Basic |
| L20 | 3.3u [L_Murata_DFE201610P] | C48783272 | Extended | 11,890 | 0.0311 | 1 | 2 | AOTA-B201610S3R3 not on JLC; APS201610M3R3F is the same 2016 land |
| R22,R23 | 27 / 1% [R_0402_1005Metric] | C2909343 | Extended | 104,236 | 0.0021 | 2 | 4 | no Basic 27R; cheapest in stock |
| R21,R53,R56 | 1k / 1% [R_0402_1005Metric] | C11702 | Basic | 11,624,304 | 0.0022 | 3 | 6 | Basic; same part as the 1k line |
| C46,C47 | 18p / 50 V C0G [C_0402_1005Metric] | C541431 | Extended | 128,089 | 0.0045 | 2 | 4 | no Basic 18pF in 0402; this is the cheapest qualifying part and is +-1%, tighter than the +-5% it replaces |
| Y1 | 12 MHz TAXM12M4RFBCCT2T [Crystal_SMD_3225-4Pin_3.2x2.5mm] | C133337 | Extended | 53,533 | 0.0763 | 1 | 4 | ABM8-272-T3 not on JLC; CL 12 pF is matched by the 18 pF C46/C47 |
| R24,R54 | 1k [R_0402_1005Metric] | C11702 | Basic | 11,624,304 | 0.0022 | 2 | 4 | Basic |
| R25,R26 | 4.7k [R_0402_1005Metric] | C25900 | Basic | 17,785,997 | 0.0029 | 2 | 4 | Basic |
| SW1 | RESET (RUN to GND) [SW_SPST_B3U-1000P] | C231329 | Extended | 171,182 | 0.1866 | 1 | 2 |  |
| SW2 | BOOTSEL (via R24) [SW_SPST_B3U-1000P] | C231329 | Extended | 171,182 | 0.1866 | 1 | 2 | same part as SW1 |
| R30 | 15k / 1% [R_0402_1005Metric] | C25756 | Basic | 1,661,319 | 0.0019 | 1 | 2 | Basic |
| R55 | 100 / 1% [R_0402_1005Metric] | C25076 | Basic | 3,222,082 | 0.0037 | 1 | 2 | Basic |
| D20 | WS2812C-2020 RGB [LED_WS2812B-2020_PLCC4_2.0x2.0mm] | C2976072 | Extended | 45,438 | 0.1020 | 1 | 4 |  |
| U21 | ICM-45686 6-axis IMU [InvenSense_LGA-14_2.5x3mm_P0.5mm_ICM45686] | C22459454 | Extended | 3,872 | 10.1002 | 1 | 14 |  |
| U22 | BMP581 barometer [Bosch_LGA-10_2x2mm_BMP581] | C5362283 | Extended | 1,775 | 2.4076 | 1 | 10 |  |
| U23 | ADXL375 high-g accelerometer [Analog_LGA-14_3x5mm_P0.8mm_ADXL375] | C579466 | Extended | 223 | 21.1438 | 1 | 14 | only 223 in stock at $21.14 |
| R35,R36,R37,R38,R39,R40,R41,R48,R50,R51 | 10k [R_0402_1005Metric] | C25744 | Basic | 27,497,679 | 0.0031 | 10 | 20 | Basic |
| U24 | DNP: W25Q32JVSNIQ [SOIC-8_3.9x4.9mm_P1.27mm] | - | NOT FOUND | - | - | 1 | 8 | DNP, not assembled and deliberately has no LCSC number. If it is ever fitted: W25Q32JVSNIQ C5355146 (SOIC-8 150 mil) or APS6404L-SQN-SN C5360304 (SOP-8 150 mil). FIT ONE PART ONLY. |
| J11 | microSD [microSD_HC_Molex_104031-0811] | C585350 | Extended | 11,587 | 0.6637 | 1 | 14 |  |
| C26 | 2.2u / 16 V X5R 0603 [C_0603_1608Metric] | C23630 | Basic | 3,151,022 | 0.0181 | 1 | 2 | TPS7A2033 needs >=1 uF effective; 0402 1 uF derates below that at 3.3 V bias (SBVS338H Sec 7.1.1) |
| D21 | LED white 0603 [LED_0603_1608Metric] | C2290 | Basic | 1,021,007 | 0.0122 | 1 | 2 | USB VBUS-present indicator; no Basic/Preferred blue LED exists at JLC (checked 2026-09-17), white chosen |

## Tools

`tools/jlc/find_part.py` searches Basic/Preferred/Extended candidates and filters
package and electrical attributes. `lcsc_map.csv` records selected parts;
`audit.py` totals their class, cached stock and costs. This does not establish
that an alternative is electrically interchangeable.

```sh
python3 tools/jlc/find_part.py --q "100nF 0402" --pkg 0402 --attr-val Capacitance=100nF
python3 tools/jlc/audit.py --refresh
python3 tools/jlc/export_jlc.py
```

The last command exports `jlc-bom.csv` and `jlc-cpl.csv`; schematic netlist and PCB
must first be current. Check package orientation in JLC's preview. The exporter
can leave files after reporting a missing-part error, and BOM/CPL mismatches are
warnings rather than a failing exit status.

## Manufacturing status

Current project: four layers, 1.6 mm, ENIG, top-side SMT, with optional backside
U24 left unpopulated. Routing remains unfinished. No fabrication set is supplied
by this audit. Use current PCB settings and the finished layout for the actual
quote; old board dimensions and routing counts were removed from this report.
