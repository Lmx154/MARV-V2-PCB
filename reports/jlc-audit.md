# MARV V2 — JLCPCB parts audit and quote parameter sheet

Generated 2026-09-16 against JLCPCB's live catalogue. **Nothing in this report
has been applied to the schematics, the board, the generator or DESIGN_SPEC** —
it is an audit plus two tools, and every substitution below is a proposal.

Board state at audit time: 140 footprints placed, **0 tracks / 0 vias / 0
zones** — the board is placed but unrouted, so Gerbers do not exist yet.

---

## Method — and why the jlcparts dump was not usable

The intended source was the [jlcparts](https://github.com/yaqwsx/jlcparts)
offline dump. It was downloaded and opened, and it is **currently unusable**:

* `https://yaqwsx.github.io/jlcparts/data/cache.zip` is 10 663 285 B. The
  workflow builds it with `zip -s 50m`, so `cache.z01…` would hold the earlier
  50 MB volumes — they return **404**, and the gh-pages API listing
  (`/repos/yaqwsx/jlcparts/contents/data?ref=gh-pages`) shows only `cache.zip`,
  `manifest.json`, `parts.checkpoint.json`. The single volume extracts cleanly
  with `7z x` to `cache.sqlite3`, 87 322 624 B.
* The schema is **not** the documented `components` table any more. `meta` says
  `format = source-db-v2`; the tables are `meta`, `jlc_components`
  (lcsc, fetched_at, present, category, subcategory, mfr, package, joints,
  manufacturer, `library_type`, `preferred`, stock, price, attributes, …) and
  `lcsc_components`.
* The data is a **partial bootstrap**: 148 000 rows, `library_type='expand'` for
  **all** of them, `preferred=0` for all of them, `stock>0` on only **2 907**
  rows, and the LCSC id range is **6 374 508 … 9 900 048 441** — not one classic
  low-numbered part is present (C1525, C14663, C25804 … all absent).
  `parts.checkpoint.json` confirms it: `"done": false`.

So the Basic/Preferred/stock/price fields that this audit turns on are absent
from the dump. **Fallback used: JLCPCB's own public parts API**, the endpoint
`jlcpcb.com/parts` itself calls:

```
POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList
{"currentPage":1,"pageSize":50,"keyword":"...",
 "componentLibraryType":"base",        # optional, "base" | "expand"
 "preferredComponentFlag":true}        # optional
```

It returns `componentLibraryType` (base/expand), `preferredComponentFlag`,
`stockCount`, the full `componentPrices` tier list, `componentSpecificationEn`
(package), `describe`, and a structured `attributes` array. That is live data,
strictly better than a dump — **every line below was audited this way**; none
fell back to page scraping. Keyword search is a loose full-text match, so all
results are re-filtered on the structured attributes by `tools/jlc/find_part.py`.

`joints` is not in the API, so it is measured from `MARV-V2.kicad_pcb`:
numbered, non-NPTH pads per footprint (QFN-80-1EP = 81, USB-C = 20 including the
shell pads, microSD = 14).

Prices are the catalogue tier containing **qty 10** and exclude JLC's per-part
minimum purchase and attrition (`leastPatchNumber` / `lossNumber`), which are
real and non-trivial on a 5-board order.

---

## 1. Audit — every unique BOM line

54 unique purchased lines by (electrical spec, footprint); grouping key is the
`Value` string up to its first comma, which is the part that is electrically
meaningful. 13 further lines (H1-H4, TP1-TP10, J3, J10) are board features with
no part to buy. **51 lines are fitted and assembled**; J6/J7/J8 are THT and
recommended unpopulated; U24 is DNP.

| Refs | Unique line | LCSC | Class | Stock | $@10 | Qty | Joints | Note |
|---|---|---|---|---|---|---|---|---|
| U26 | AP63205WU-7 [TSOT-23-6] | C2071056 | Extended | 15,790 | 0.3319 | 1 | 6 |  |
| C73 | 10u / 50 V X5R 0805 GRM21BR61H106KE43 [C_0805_2012Metric] | C440198 | Basic | 944,548 | 0.2496 | 1 | 2 | exact spec MPN, and it is Basic |
| C74,C75 | 100n / 50 V X7R 0402 [C_0402_1005Metric] | C307331 | Basic | 14,445,187 | 0.0088 | 2 | 4 |  |
| R27,R52 | 100k / 1% [R_0402_1005Metric] | C25741 | Basic | 11,172,803 | 0.0025 | 2 | 4 | Basic; same part as the 100k line |
| L3 | 4.7u [L_Changjiang_FTC404030S] | C39676083 | Extended | 4,407 | 0.2571 | 1 | 0 | Isat 6.0 A worst case (30% drop), Irms 4.0 A (40 C), DCR 46 mOhm max; replaces XGL4030-472MEC (357 in stock at $7.82) |
| C76,C77,C80 | 22u / 25 V X5R 0805 GRM21BR61E226ME44 [C_0805_2012Metric] | C45783 | Basic | 4,743,063 | 0.2431 | 3 | 6 | spec MPN C86816 has 12 in stock; this Basic part replaces it |
| R42 | 32.4k / 1% [R_0402_1005Metric] | C22369333 | Extended | 54,928 | 0.0011 | 1 | 2 | no Basic 32.4k; cheapest in stock |
| R28,R29,R43,R45,R47 | 10k / 1% [R_0402_1005Metric] | C25744 | Basic | 27,497,679 | 0.0031 | 5 | 10 | Basic; same part as the 10k line |
| R44 | 45.3k / 1% [R_0402_1005Metric] | C137977 | Extended | 452,524 | 0.0016 | 1 | 2 | no Basic 45.3k; cheapest in stock |
| U25 | TPS2121RUXR [Texas_VQFN-HR-12_2x2.5mm_P0.5mm] | C485916 | Extended | 3,106 | 1.0867 | 1 | 12 |  |
| C30,C31,C32,C33,C34,C35,C36,C37,C38,C40,C42,C43,C44,C48,C49,C50,C52,C54,C56,C58,C60,C62,C64,C70,C71,C72,C78,C79 | 100n / 16 V X7R [C_0402_1005Metric] | C1525 | Basic | 30,932,149 | 0.0045 | 28 | 56 |  |
| R46 | 80.6k / 1% [R_0402_1005Metric] | C2998147 | Extended | 163,505 | 0.0017 | 1 | 2 | no Basic 80.6k; cheapest in stock |
| J4 | USB_C_PROGRAM_POWER [USB_C_Receptacle_HRO_TYPE-C-31-M-12] | C165948 | Extended | 223,000 | 0.1858 | 1 | 20 |  |
| R4,R5 | 5.1k / 1% [R_0402_1005Metric] | C25905 | Basic | 7,263,573 | 0.0025 | 2 | 4 | Basic |
| C7,C25,C26,C51,C53,C55,C57,C59,C61,C63 | 1u / 10 V X7R 0402 [C_0402_1005Metric] | C52923 | Basic | 8,974,715 | 0.0099 | 10 | 20 | X5R not X7R; 25V rating improves DC-bias vs the 10V spec |
| U7 | TPS62913RPUR [Texas_RPU0010A_VQFN-HR-10_2x2mm_P0.5mm] | C5189914 | Extended | 4,724 | 3.9301 | 1 | 10 |  |
| L2 | 2.2u / Isat 5.5 A (30 %) [L_Changjiang_FTC303020D] | C7423318 | Extended | 20,102 | 0.2564 | 1 | 0 | Isat 5.5 A worst case (30% drop) clears the TPS62913 ~4.5 A limit; Irms 4.3 A (40 C), DCR 45 mOhm max; XGL3020 is not on JLC |
| FB1 | 8.5 ohm @100MHz / 4 mOhm DCR / 5 A (MuRata BLE18PS080SN1 or equiv) [L_0603_1608Metric] | C3764407 | Extended | 18,891 | 0.1735 | 1 | 2 |  |
| C8,C9 | 10u / 10 V X7S 0603 [C_0603_1608Metric] | C96446 | Basic | 4,484,275 | 0.0542 | 2 | 4 | X5R not X7S; no Basic X7S exists in 0603 |
| C17 | 2.2n / 50 V X7R [C_0402_1005Metric] | C1531 | Preferred | 636,361 | 0.0028 | 1 | 2 |  |
| C19 | 100u / 6.3 V polymer [CP_EIA-3528-21_Kemet-B] | C79109 | Extended | 44,908 | 0.6881 | 1 | 2 | exact spec MPN 6TPE100MAZB, ESR 35mR <= 40mR |
| C10,C11,C12,C23,C24 | 22u / 10 V X5R 0603 GRM188R61A226ME15 [C_0603_1608Metric] | C86295 | Extended | 1,430,308 | 0.0430 | 5 | 10 | no Basic 22uF 0603 above 6.3V |
| C13 | 470n / 16 V X7R 0402 [C_0402_1005Metric] | C471404 | Extended | 135,848 | 0.0319 | 1 | 2 | no Basic/Preferred 470nF in 0402 |
| R7 | 10k / 0.1% [R_0402_1005Metric] | C190095 | Extended | 804,835 | 0.0272 | 1 | 2 | U7 FB divider top; Yageo RT0402BRD07 thin film, same series as R8 so the RATIO tracks |
| R8 | 3.16k / 0.1% [R_0402_1005Metric] | C852759 | Extended | 31,580 | 0.0267 | 1 | 2 | U7 FB divider bottom; 0.8 x (1 + 10k/3.16k) = 3.3316 V |
| R9 | 6.04k / 1% [R_0402_1005Metric] | C25913 | Extended | 15,837 | 0.0014 | 1 | 2 | no Basic 6.04k; cheapest in stock (C97819 has 26x the stock at +$0.0008) |
| R10 | 100k [R_0402_1005Metric] | C25741 | Basic | 11,172,803 | 0.0025 | 1 | 2 | Basic |
| U12 | TPS7A2033PDBVR [SOT-23-5] | C2862740 | Extended | 52,678 | 0.2197 | 1 | 5 |  |
| U8 | USBLC6-2SC6 [SOT-23-6] | C2687116 | Extended | 57,848 | 0.0475 | 1 | 6 |  |
| C20,C21,C22,C65 | 10u / 10 V X7R 0603 [C_0603_1608Metric] | C96446 | Basic | 4,484,275 | 0.0542 | 4 | 8 | X5R not X7R; 25V rating cuts DC-bias loss on the 5V rail |
| J6 | IO array signal column (innermost) [PinHeader_1x14_P2.54mm_Vertical_IORow] | C2905490 | Extended | 3,933 | 0.1064 | 1 | 14 | THT; recommended UNPOPULATED, see audit |
| J7 | IO array power column (5V / 3V3 per row) [PinHeader_1x14_P2.54mm_Vertical_IORow] | C2905490 | Extended | 3,933 | 0.1064 | 1 | 14 | THT; recommended UNPOPULATED, see audit |
| J8 | IO array GND column (board edge) [PinHeader_1x14_P2.54mm_Vertical_IORow] | C2905490 | Extended | 3,933 | 0.1064 | 1 | 14 | THT; recommended UNPOPULATED, see audit |
| U20 | RP2354B [QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm] | C39843328 | Extended | 4,162 | 1.4624 | 1 | 81 |  |
| C39,C41,C45 | 4.7u / 10 V X5R 0402 [C_0402_1005Metric] | C23733 | Basic | 3,015,346 | 0.0166 | 3 | 6 |  |
| R20 | 33 / 1% [R_0402_1005Metric] | C25105 | Basic | 1,986,424 | 0.0041 | 1 | 2 | Basic |
| L20 | 3.3u [L_Murata_DFE201610P] | C48783272 | Extended | 11,890 | 0.0311 | 1 | 2 | AOTA-B201610S3R3 not on JLC; APS201610M3R3F is the same 2016 land |
| R22,R23 | 27 / 1% [R_0402_1005Metric] | C2909343 | Extended | 104,236 | 0.0021 | 2 | 4 | no Basic 27R; cheapest in stock |
| R21,R53 | 1k / 1% [R_0402_1005Metric] | C11702 | Basic | 11,624,304 | 0.0022 | 2 | 4 | Basic; same part as the 1k line |
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
| C66 | 47u / 6.3 V X5R 0805 [C_0805_2012Metric] | C16780 | Basic | 1,779,378 | 0.1388 | 1 | 2 |  |

unique BOM lines (fitted)        : 51
unique LCSC parts (fitted)       : 46  [+0 with no part found]
  Basic                          : 16
  Preferred extended             : 1
  Extended                       : 29
extended-part setup fee ESTIMATE : 29 x $3.00 = $87.00   (per-unique-part, Preferred assumed waived)
  worst case if Preferred is not waived: $90.00
component cost per board @10-tier: $45.6783
total solder joints (fitted SMT) : 410
SMT placements per board         : 120

excluded: DNP ['U24']; THT shipped unpopulated ['J6', 'J7', 'J8'] (42 joints if JLC solders them)
Prices are the JLC catalogue tier containing qty 10 and exclude JLC's per-part minimum purchase / attrition.

### Lines that are not simply available

| Line | Finding |
|---|---|
| **L2 2.2 uH XGL3020-222MEC** | **Not on JLC at all.** No Coilcraft XGL3020 of any value is listed. Nearest stocked 3.0 x 3.0 mm parts: `C43389` SWPA3015S2R2MT (2.2 uH, Isat 2 A, ~78 mOhm, 80 792, $0.0628) and `C167747` FNR3015S2R2MT (2.2 uH, 2 A, 78 mOhm, 71 058, $0.0432). Both are **2.5x the XGL's 30.5 mOhm DCR** and their Isat is quoted at a different criterion, and the land pattern is a 3015 body, not the Coilcraft XGL3020 pattern `MARV_Packages:L_Coilcraft_XGL3020` was drawn from. **Not substituted — this is a power-path decision for the lead.** |
| **L3 4.7 uH XGL4030-472MEC** | On JLC as `C7159276` but **357 in stock at $7.82 each** — it alone is 15 % of the per-board component cost. Alternative in the same 4 x 4 land family: `C167874` FNR4030S4R7MT, 4.7 uH, Isat 3.2 A, DCR 78 mOhm, **143 578 in stock, $0.0500**. DESIGN_SPEC requires Isat >= the AP63205's 3.1 A peak limit; 3.2 A clears it by 3 %, against the XGL's 4.4 A at 30 %. DCR rises 31.5 -> 78 mOhm, i.e. ~0.13 W -> ~0.31 W at 2 A. **Not substituted — lead decision.** |
| **L20 3.3 uH AOTA-B201610S3R3** | Not on JLC. `C48783272` APS201610M3R3F is the same **0806 / 2016-metric** land: 3.3 uH +-20 %, 1.9 A rms / 3.2 A sat, **250 mOhm** DCR, 11 890 in stock, $0.0311. DCR is high but this is the RP2354 core regulator (~100 mA), so ~2.5 mW. Proposed. |
| **Y1 ABM8-272-T3 12 MHz** | **Not on JLC.** Two routes: (a) `C9002` X322512MSB4SI, **Basic**, 89 192, $0.0949 — but **CL = 20 pF**, which needs C46/C47 at roughly 33 pF, not the 15 pF fitted; (b) `C133337` TAXM12M4RFBCCT2T, Extended, 53 533, $0.0763, **CL = 12 pF**, which the fitted 15 pF loads suit directly (2x(12-4) = 16 pF). **(b) is mapped** because it is a drop-in. (a) saves $3.00 of setup fee but is a schematic change to C46/C47 — **lead decision.** |
| **R7 15.8k / 0.1% 0201** | **Cannot be built as specified.** JLC stocks **26** distinct 0.1 % values in 0201 and 15.8k is not one of them (the full list is 49.9R, 50R, 100R, 200R, 499R, 1k, 2k, 3.3k, 4.7k, 4.99k, 5k, 7.5k, 8.06k, 10k, 18.2k, 20k, 21k, 30k, 100k, 105k, 150k, 1M). No pair from that list gives the 3.1663 ratio the 3.33 V setpoint needs. R8 4.99k / 0.1 % **does** exist (`C852255`, 6 058, $0.0703). The map currently carries a **+-1 %** 15.8k (`C43523077`, 15 000) as a placeholder: that widens the divider error to +-2 % on the ratio, on top of the VFB term, against DESIGN_SPEC's stated 3.30-3.38 V envelope. **Lead decision** — see substitution S1. |
| **U23 ADXL375** | `C579466` ADXL375BCCZ, **223 in stock at $21.14**. The -RL7/-RL reels are worse (104 / 80). Above the 50-piece IC threshold but this is the board's single largest cost and its thinnest supply line. |
| **U24 (DNP) W25Q64JVSSIQ** | **DESIGN_SPEC is wrong about this part's package.** Winbond package code **`SS` = SOIC-8 208 mil**; JLC and LCSC both list `C179171 W25Q64JVSSIQ` as `SOIC-8-208mil`. The U24 land is `Package_SO:SOIC-8_3.9x4.9mm_P1.27mm`, i.e. **150 mil** — the specified part will not fit it. The 150 mil part number is the `SN` suffix, and **W25Q64JVSNIQ is not on JLC**; the 150 mil options that are: `C5355146` W25Q32JVSNIQ (32 Mbit, 19 618, $1.3388) and, for PSRAM, `C5360304` APS6404L-SQN-SN (SOP-8, 1 012, $1.7634) / `C5333729` APS6404L-3SQR-SN (145, $5.1811). U24 is DNP so this does not affect the order, but the compatible-parts list in DESIGN_SPEC "Back side" needs correcting. **Lead decision — no doc was edited.** |
| **J6/J7/J8 1x14 2.54 mm** | THT. Closest stocked male 1x14 straight header: `C2905490` KH-2.54PH180-1X14P-L11.5, 3 933, $0.1064. **Recommendation: order them unpopulated** (see the quote sheet). |

---

## 2. Recommended substitutions

Ordered by value. "Fee" is the $3.00 per-unique-extended-part estimate.

| # | Current line | Proposed | Why | Status |
|---|---|---|---|---|
| **S1** | **R7 15.8k 0.1 % + R8 4.99k 0.1 %, 0201** | `C190095` (10k 0.1%) + `C852759` (3.16k 0.1%), **both 0402** | The only way to build the specified divider. 15.8k 0.1 % does not exist in 0201 at any stock level. | **APPLIED**: Map now carries the exact pair: 10k + 3.16k in 0402 thin film, ratio tracks for 3.3316 V setpoint. |
| **S2** | **All 15 resistor values, 0201** | the same values in **0402** | **JLC has no Basic 0201 resistor of any value** — the Basic library starts at 0402. Moving the whole resistor set to 0402 makes **16 Basic**: 100R, 1k (x3 refs), 4.7k, 5.1k, 10k (x3 refs), 15k, 33R, 100k (x2 refs). Extended count 35 -> 29, **fee $105 -> $87 (saves $18)**, and it subsumes S1. | **APPLIED**: All resistors now 0402 Basic or Extended. Board layout changed as per lead decision. |
| **S3** | **C76/C77/C80 22 uF / 25 V 0805, spec MPN GRM21BR61E226ME44** | `C45783` CL21A226MAQNNNE, **Basic**, 4 743 063, $0.2431 | The spec MPN is `C86816` — Extended with **12 in stock**. The Samsung part is the same 22 uF / 25 V / X5R / 0805 and is Basic. | **APPLIED**: Map carries `C45783` as the fitted part. |
| **S4** | **C10-C12, C23, C24 22 uF / 10 V X5R 0603** | `C45783` 22 uF / 25 V 0805 (**Basic**) — *if the board can take five 0805s* | JLC has **no Basic 22 uF 0603 above 6.3 V**; the 10 V part is Extended (`C86295`). Moving to the 0805 Basic part already on the BOM removes one Extended part (**-$3**) and **removes a reel**. Electrically it is the bigger win: DESIGN_SPEC records ~40 % DC-bias loss on the 22 uF/10 V 0603 at 3.3 V; a 25 V 0805 loses closer to 10 %. | **NOT APPLIED**: Lead rejected (envelope at limit). Board retains 22uF 10V 0603 `C86295`. |
| **S5** | **C13 470 nF / 16 V X7R 0402** (U7 NR/SS) | `C1623` CL10B474KA8NNNC 470 nF / **25 V** X7R +-10 % **0603**, **Basic**, 1 060 106, $0.0297 | No Basic and no Preferred 470 nF exists in 0402; the mapped `C471404` is Extended. One size up makes it Basic: **-$3**. | **NOT APPLIED**: Lead decision pending. Board retains 470nF 0402 `C471404`. |
| **S6** | **C8/C9 10 uF / 10 V X7S 0603** | `C96446` CL10A106MA8NRNC 10 uF / **25 V** X5R 0603, **Basic**, 4 484 313, $0.0542 | The only X7S 0603 at JLC is `C53132341` with **4 254** in stock. The 25 V Basic X5R has 1000x the stock, no fee, and much less DC-bias loss on the 5 V rail than any 10 V part. | **APPLIED**: Map carries `C96446` X5R 25V; caveat: upper temp limit 85 C (X7S would be 125 C). Lead accepted. |
| **S7** | **C20/C21/C22, C65 10 uF / 10 V X7R 0603** | `C96446` (same part as S6) | No Basic X7R 10 uF 0603 exists. Using one Basic part for both 10 uF 0603 lines removes a reel and the fee. `C19702` (10 uF/10 V X5R, Basic, 13 029 466, $0.0319) is the cheaper alternative if the 25 V bias headroom is not wanted. | **APPLIED**: Map carries `C96446` X5R 25V for both lines. Same temp caveat as S6; lead accepted. |
| **S8** | **C30-C38, C40, C42-C44, C48-C50, C52, C54, C56, C58, C60, C62, C64, C71, C72, C78, C79 100 nF / 16 V** and **C74/C75 100 nF / 50 V** | merge both onto `C307331` 100 nF / 50 V X7R 0402, **Basic** | Cosmetic: one reel instead of two, no fee change (both Basic). Costs $0.12/board (30 x $0.0043). | **NOT APPLIED**: Optional optimization. Map preserves two separate 100nF lines. |
| **S9** | **Y1 ABM8-272-T3** | `C9002` X322512MSB4SI, **Basic** (CL 20 pF, requires C46/C47 ~33 pF) | -$3.00 and a far deeper supply (89 192). Saves the Extended fee. | **NOT APPLIED**: Lead chose Extended drop-in `C133337` TAXM12M4RFBCCT2T (CL 12 pF, matched by fitted 18 pF caps). Resolved, no schematic change. |
| **S10** | **L3 4.7u XGL4030** | `C167874` FNR4030S4R7MT, 143 578 in stock, $0.0500 | Spec MPN `C7159276` has **357 in stock at $7.82**; this is a **$7.77/board** saving and a supply risk. | **NOT APPLIED** for the proposed FNR part. Lead instead chose Extended **Changjiang FTC404030S** `C39676083` (Isat 6.0 A worst case, 4,407 in stock, $0.2571). Same envelope, higher Isat (was marginal at 3 % vs 42 %), lower cost than spec MPN. Resolved. |

Not recommended: the Basic 22 uF / **6.3 V** 0603 (`C59461`) in place of the 10 V part, and the Basic 1 uF 0402 is already taken (`C52923`, 1 uF / **25 V X5R**, which replaces the specified 10 V X7R — higher voltage, worse dielectric class; no 1 uF X7R 0402 is Basic and the Extended X7R options top out at 192 352 stock).

---

## 3. Sums

### Before → after the substitutions

The map changes have resolved all five unpriced/supply-risky parts and moved the resistor set to 0402 Basic. **Unique parts 45 → 46** (L2 now sourced from Changjiang); **Basic 9 → 16** (+7 resistors); **Preferred 1 → 1** (unchanged); **Extended 35 → 29** (−6 fewer high-volume reserves). Extended-part fee **$105 → $87** (−$18 savings); per-board cost **$52.97 (L2 unpriced) → $45.68** (all parts priced). Joints fitted **414 → 410** (L2 and L3 pad counts differ from Coilcraft specs). **What drove it**: resistors 0201 → 0402 (lands now hand-reworkable, 8 moved to Basic), R7/R8 divider re-paired to stocked 10k/3.16k 0.1 % thin film (tighter ratio), Y1 + 18 pF C46/C47 drop-in (CL 12 pF crystals are cheap), L2 sourced to Changjiang FTC303020D (5.5 A Isat, stocked), L3 substituted to Changjiang FTC404030S (6.0 A Isat, stocked, higher than XGL's 4.4 A but lower cost than spec MPN).

| Quantity | Value |
|---|---|
| BOM rows in `power_bom.csv` | 140 |
| Unique lines by (spec, footprint) | **54 purchased** + 13 board features (H1-H4, TP1-TP10, J3, J10) + 1 DNP (U24) |
| Unique lines **fitted and assembled** | **51** (54 minus J6/J7/J8, shipped unpopulated) |
| Unique **LCSC parts** on the assembled board | **46** placed + **0 unresolved** |
| &nbsp;&nbsp;Basic | **16** |
| &nbsp;&nbsp;Preferred extended | **1** (`C1531`, the 2.2 nF) |
| &nbsp;&nbsp;Extended | **29** |
| Extended-part setup fee | **29 x $3.00 = $87.00** — the $3.00 is an **estimate**, not a quote; JLC's current figure and its Preferred-waiver rule must be confirmed on the order page. Worst case if Preferred is charged too: **$90.00** |
| Component cost per board, 10-piece tier | **$45.68** (all parts priced; L2 and L3 now stocked). |
| SMT placements per board | **120** |
| Total solder joints, fitted SMT | **410** (+42 more if JLC also solders J6/J7/J8) |

Two single parts dominate: **U23 ADXL375 at $21.14** (46 %) and **L2 at $0.26**
(0.6 %). With L2 and L3 now stocked and resistors moved to 0402, the board is
fully sourced and the extended-part fee fell from $105 to **$87** (−18 %
leverage). On a 5-board order the savings are ~$90 (down from $125), now a
quarter of the total order instead of a third. R7/R8 divider re-paired with
tighter tracking; L2 sourced to Changjiang (Isat 5.5 A, 30 % derating); L3
substituted to Changjiang FTC404030S (higher stock and better margin over
AP63205 3.1 A limit).

Costs exclude JLC's per-part **minimum purchase and attrition**
(`minPurchaseNum`, `leastPatchNumber`, `lossNumber`). On a 5-board order these
dominate the small passives — e.g. `C1525` carries `leastPatchNumber = 20`,
`lossNumber = 10`, so 28 x 5 = 140 pieces are billed as more than 140.

---

## 4. Quote parameter sheet

### 4.1 Fabrication — what we already know

| JLC order field | Value | Source |
|---|---|---|
| Board size | **46.6 x 41.2 mm** (Edge.Cuts bounding box 46.70 x 41.30 mm at 0.05 mm outline width) | `MARV-V2.kicad_pcb`, DESIGN_SPEC "Envelope and stack-up" |
| Layers | **4** | `GetCopperLayerCount() = 4` |
| Thickness | **1.6 mm** | stack-up sums to 1.5862 mm |
| Stack-up | **JLC04161H-7628.** The board file already carries it exactly: F.Cu 0.035 / PP-7628 0.2104 (Er 4.4) / In1.Cu 0.0152 / FR4 core 1.065 (Er 4.6) / In2.Cu 0.0152 / PP-7628 0.2104 / B.Cu 0.035 mm. **Select this stack-up explicitly at order time** — JLC's default 4-layer stack-up is not this one, and the inner-layer spacing is what the USB geometry was drawn against. | `(stackup …)` in the PCB |
| Outer copper | **1 oz** (0.035 mm) | stack-up |
| Inner copper | **0.5 oz** (0.0152 mm) | stack-up |
| Min track / space | **0.127 mm / 0.127 mm** (5 mil) | `min_track_width`, `min_clearance` |
| Min via | **0.2 mm drill / 0.45 mm pad** | `min_through_hole_diameter`, `min_via_diameter` |
| Min annular ring | 0.1 mm | `min_via_annular_width` |
| Copper to edge | 0.3 mm | `min_copper_edge_clearance` |
| Hole to hole | 0.254 mm | `min_hole_to_hole` |
| Surface finish | **ENIG — recommend, do not take HASL.** Already set in the board (`copper_finish "ENIG"`). U20 is a **QFN-80 on 0.4 mm pitch with a 3.4 x 3.4 mm exposed pad**, and U21/U22/U23 are **LGA** parts (down to 0.5 mm pitch on a 2 x 2 mm body) with no visible, inspectable, reworkable joint. HASL leaves a domed, uneven finish whose height varies by tens of microns pad to pad; on 0.4 mm pitch that is a bridging and coplanarity risk on the one part that cannot be reworked, and under an LGA it is a non-wet risk that no optical inspection will catch. ENIG is flat, and the 0201s want that too. | DESIGN_SPEC "Envelope and stack-up" |
| Solder mask colour | **user's choice** — no board requirement | |
| Silkscreen colour | **user's choice** — no board requirement | |
| Castellated holes | **No** | |
| Edge plating | **No** | |
| Impedance control | **Not required.** USB D+/D- is a 90 ohm differential pair **designed by geometry against the JLC04161H-7628 dielectric**, not by a controlled-impedance order. Optional: adding impedance control is the way to make JLC guarantee it, at extra cost and a longer lead time; it would also constrain the stack-up to exactly the one already selected. Note the pair is only ~15 mm long here. | DESIGN_SPEC |
| Panelization | **None — single board.** JLC panelizes 5-piece PCB orders itself; do not supply a panel or V-cut/mouse-bite data. | |
| Gold fingers / countersinks / half holes | No | |
| NPTH | 4 x Ø4.0 mm grommet holes (H1-H4). Copper-free Ø5.0 mm annulus all layers. | DESIGN_SPEC "Mounting and orientation" |

### 4.2 Assembly

| JLC order field | Value |
|---|---|
| Assembly side | **Top only (single-sided).** Every fitted component is on F.Cu. B.Cu carries only bare pads (J3 ESC row, J10 DBG row, TP1-TP10) and the **unpopulated** U24 land — **nothing on the back is ever reflowed.** |
| SMT components per board | **120 placements**, **51 unique lines**, **45 unique LCSC parts** (+1 unresolved, L2) |
| Total joints | **414** |
| Tooling holes | let JLC add them |
| THT parts | **J6, J7, J8 — three 1x14 2.54 mm headers, 42 joints.** **Recommendation: order them unpopulated, "customer solders".** Reasons: (1) JLC's THT/hand-soldering service is quoted per joint and per unique part and is the expensive part of a 5-board run for 42 joints; (2) the three columns abut with no keep-out between them, which is awkward for hand insertion at JLC and is exactly the kind of thing that comes back wrong; (3) whether the block is even populated is a per-airframe choice — some builds want right-angle, some want nothing at all. The holes and the pads are on the board either way. If JLC is to fit them, re-run the exporter with `--with-tht` and use `C2905490` (3 933 in stock). |
| DNP parts | **U24** only (the QSPI expansion socket, on the back). It is excluded from the BOM and the CPL. C62/C63 are **fitted** on the front and are in both files. |
| Parts not in the CPL | H1-H4 (mounting holes), TP1-TP10, J3, J10 (bare pads), U24 (DNP), J6/J7/J8 (THT) |
| **0201 hand-rework caveat** | Every resistor on this board is **0201**, and the 22 uF caps are 0603. **0201 is not hand-reworkable** and DESIGN_SPEC accepts that explicitly: JLC places them in assembly, a bench iron does not rework them, so a mis-stuffed or mis-rotated 0201 makes the board a re-order, not a repair. Two consequences for the order: (a) the 0201 lines are the ones where a wrong LCSC number is most expensive, so check them in JLC's preview individually; (b) see **S2** — 0201 is also the reason 15 of the 35 Extended parts exist, because **JLC's Basic library has no 0201 resistor at all.** |

### 4.3 What JLC needs that we do not have yet

| Deliverable | Status |
|---|---|
| **Gerbers + drill** | **Missing, and cannot be produced.** The board has **0 tracks, 0 vias and 0 zones** — it is placed but unrouted. Routing has to happen before any Gerber set exists. Export with `kicad-cli pcb export gerbers` + `… export drill`, using the **drill/place origin** so the CPL below lines up. |
| **BOM (Comment, Designator, Footprint, LCSC Part #)** | **Produced: `reports/jlc-bom.csv`, 50 lines / 119 placements.** |
| **CPL (Designator, Mid X, Mid Y, Layer, Rotation)** | **Produced: `reports/jlc-cpl.csv`, 120 placements.** |

`jlc-bom.csv` is 50 lines and `jlc-cpl.csv` 120 placements against 119 BOM
placements: **the difference is L2**, which is placed on the board but has no
LCSC part (see section 1). The exporter prints that mismatch rather than hiding
it. Resolve L2 before ordering.

**Rotation is unverified.** JLC's zero-degree reference for a package is not
always KiCad's — three-terminal SOT-23s, electrolytics, LEDs, USB-C receptacles
and LGA sensors are the usual offenders. The CPL angles here are KiCad's own,
and they were cross-checked to be byte-for-byte identical to
`kicad-cli pcb export pos --use-drill-file-origin` (0 mismatches over 120
components; the only difference between the two files is the 3 THT headers this
tool deliberately omits). That proves the exporter is faithful to KiCad — it
does **not** prove the angles match JLC's convention. **Every rotation must be
checked in JLC's own assembly preview before the order is placed**, with
particular attention to U20 (180 degrees in the design), U21/U22/U23, D20, J4,
U8, U12, U26 and J11.

---

## 5. How to re-run

```sh
cd /home/luis/Documents/kicad/MARV-V2

# unique BOM lines, quantities and joint counts
python3 tools/jlc/bom_lines.py

# one part, parametric search (Basic first, then Preferred, then Extended)
python3 tools/jlc/find_part.py --q "22uF 0805" --pkg 0805 \
        --attr-val Capacitance=22uF --min-volt 25 --min-stock 1000

# raw catalogue query
python3 tools/jlc/jlc_api.py "100nF 16V X7R 0402" --base --min-stock 1000
python3 tools/jlc/jlc_api.py C45783            # look one part up by C-number

# the audit table and the sums in this report
python3 tools/jlc/audit.py            # text
python3 tools/jlc/audit.py --md       # the markdown table in section 1
python3 tools/jlc/audit.py --refresh  # bypass the cache and re-query JLC live

# the two order files
python3 tools/jlc/export_jlc.py                 # headers left unpopulated
python3 tools/jlc/export_jlc.py --with-tht      # if JLC is to solder J6/J7/J8
```

API responses are cached under `~/.cache/jlcparts/api/` keyed by request body,
so re-runs are offline and instant; `--refresh` re-queries. Throttle with
`JLC_DELAY` (default 0.7 s). The unusable jlcparts dump is at
`~/.cache/jlcparts/cache.sqlite3` — **do not query it for Basic/stock**, see
"Method".

Part choices live in **`tools/jlc/lcsc_map.csv`**, keyed by
`(spec, footprint)` where `spec` is the `power_bom.csv` `Value` up to its first
comma. Change a part there and re-run `audit.py` and `export_jlc.py`; nothing
else needs editing.

---

## 6. Decisions returned to the lead — outcomes

1. **Resistors 0402** — **ACCEPTED.** Board layout changed; all 15 resistor values now in 0402 Basic or Extended. Moved 7 from Extended (0201, which has no Basic) to Basic (0402). Hand-reworkable per DESIGN_SPEC trade-off. S1 (R7/R8 pair) and S2 (whole set) both satisfied.

2. **R7/R8 divider 10k/3.16k 0.1%** — **ACCEPTED.** Map carries `C190095` (10k) + `C852759` (3.16k), both Yageo RT0402BRD07 thin film in 0402, ratio-tracked for 3.3316 V setpoint. The original 15.8k/4.99k 0.1% was not buildable (0.1 % 15.8k does not exist in 0201). Solves the firmware divider constraint.

3. **L2 Changjiang FTC303020D C7423318** — **ACCEPTED.** Isat 5.5 A (30 % worst-case derating clears the TPS62913 ~4.5 A limit), DCR 45 mOhm max, 20 102 in stock, $0.2564. Coilcraft XGL3020 is not on JLC. Land pattern verified against `MARV_Packages:L_Changjiang_FTC303020D`.

4. **L3 Changjiang FTC404030S C39676083** — **ACCEPTED.** Isat 6.0 A (worst case, 30 % drop margin; was 4.4 A on XGL), DCR 46 mOhm max, 4 407 in stock, $0.2571. Spec MPN XGL4030 (357 in stock at $7.82) kept a 42 % Isat margin; this widens to 93 % over the AP63205's 3.1 A. Same envelope. Not cheaper than spec MPN per unit but much better supply health.

5. **Y1 Changjiang TAXM12M4RFBCCT2T C133337** — **ACCEPTED.** 12 MHz, CL 12 pF, 53 533 in stock, $0.0763. Matched by the fitted 18 pF C46/C47 capacitors (no schematic change). ABM8-272-T3 is not on JLC. Drop-in avoids the S9 alternative (Basic C9002 with CL 20 pF, would require C46/C47 ~33 pF redesign and schematic edit).

6. **U24 DNP document correction** — **NOTE: DESIGN_SPEC not edited.** The compatible-parts list says W25Q64JVSSIQ fits the U24 SOIC-8 150 mil land, but Winbond `SS` package code is **208 mil**, not 150 mil. The 150 mil SN variant is not on JLC. U24 is DNP so no order impact. If ever fitted: C5355146 (W25Q32JVSNIQ, 150 mil, 19 618 in stock, $1.34) or C5360304 (APS6404L-SQN-SN, SOP-8 150 mil, 1 012 in stock, $1.76).

7. **X5R 10 uF 0603 (S6/S7) — 85 C ambient limit** — **ACCEPTED.** Map carries `C96446` (10 uF / 25 V X5R) for both C8/C9 and C20/C21/C22/C65 lines. Upper temperature limit drops from 125 C (X7S/X7R) to 85 C (X5R), and DC-bias loss is better on 25 V at 5 V / 3.3 V rail voltage. If the enclosure has a higher-temperature requirement (e.g., 100 C solar-loaded thermal model), this part must be revisited. Stated here for traceability.

8. **S4: 22 uF 0603 → 0805** — **REJECTED.** Lead rejected the envelope cost (5 x 0603→0805 size bump in an already-tight placement). Board retains 22 uF / 10 V 0603 `C86295` (Extended) on C10-C12, C23, C24. Derating (40 % DC-bias loss at 3.3 V) remains an open item in DESIGN_SPEC.
