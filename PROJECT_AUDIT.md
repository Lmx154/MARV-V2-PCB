# Project inventory and simplification audit

Reviewed 2026-09-17 against the saved schematic and PCB, with three Luna agents
scanning the old docs/tools while the main review checked wiring and simulation.

The board is now the simple architecture the owner requested: external regulated
5 V, USB OR, system 3.3 V buck, and a small separate sensor LDO. GPS/ELRS power
has been moved to system 3.3 V; servos retain external 5 V.

## Where it went wrong

1. **An assumption became an architecture change.** The old DESIGN_SPEC explicitly
   records that an onboard pack buck was added because the ESC lacked a BEC,
   despite the owner's external-BEC requirement. Commit `cab59bc` added the pack
   stage; `3664082` reversed it. This is documented scope drift, not speculation
   about the agent's intentions.
2. **Implementation machinery became the authority.** The schematic generator
   says to edit code instead of sheets; the PCB generator rebuilds from scratch.
   This creates a second design to maintain when the owner works in KiCad.
   Before this cleanup there were 21 Python tools totaling about 11,870 lines.
3. **Optimization outgrew the requirement.** Placement packing, pin-assignment
   optimization, multistage routing, plane stitching, custom regulator loops,
   capacitor sweeps and negative controls accumulated. Some are useful tools,
   but they are not flight-controller requirements. The old docs even justified
   shrinking C19 using a switchover simulation for a mux that was later removed.
4. **The simulation judged assumptions as though they were requirements.** The old
   runner reproduced 4 failures out of 18 checks. Two checks expected the BEC's
   low-resistance path to win with USB present, contrary to Q1's gate wiring.
   Its LDO model admitted it could not test the capacitor stability limit it
   discussed. Passing an invented control loop did not validate the real IC.
5. **The rollback was incomplete in prose.** About 31,000 words across the seven
   main documents mixed current facts, historical decisions and pending work.
   Examples: PCB called empty despite copper; old L3 and TPS2121 tasks remained;
   VBAT_SENSE was called GPIO40 in one paragraph but is GPIO41; C8's text and
   sourced dielectric/voltage rating disagreed; simulation notes said the white
   LED lacked an MPN even though the sourcing map had one.

## What is current

| Area | Verified state / action |
| --- | --- |
| Schematic | 12 pages including root; 106 components, 95 nets. Raw VBAT reaches only J3.9 and R27. |
| Hardware changes in this refresh | J7 power pins 1–4 changed to V3V3_SYS; corresponding schematic notes, checker tables and PCB captions updated. Analog power topology unchanged. |
| PCB | Routing cleanup removed 131 track segments, 134 vias and 5 generated copper zones. All footprint/pad definitions, placement, outline and board settings preserved byte-for-byte. The board is ready for owner routing. |
| Active simulation | One input-network deck, seven named source/load cases, one short runner. Regulators represented by combined input demand. |
| Old simulation | Historical documentation and result summaries retained. Obsolete runners, decks, model copies and generated logs removed. |
| JLC exports | 37 BOM lines / 86 assembled placements; U24 DNP; J6–J8 excluded for customer assembly. The rail change does not change purchased parts or placement coordinates. |

## Tool inventory

| Tools / files | Purpose | How to treat them |
| --- | --- | --- |
| `simulate_power_input.py`, `simulations/power_input.cir` | Input OR voltage/current behavior | Active simulation; run when input topology, sources or demand change. |
| `check_power_netlist.py` | Pins, rails, connector map, footprint coverage | Useful wiring check; updated for approved IO power change. |
| `netlist_fingerprint.py` | Connectivity comparison independent of drawing layout | Useful when reviewing schematic edits. |
| `audit_footprints.py` | Footprint, pad and 3D-file availability | Useful reference check; does not prove physical fit. |
| `relink_pcb_paths.py` | Repairs schematic-to-footprint identity paths | Maintenance only; default modifies PCB. Use `--dry-run` for inspection. |
| `tools/jlc/find_part.py` | Searches and filters candidate parts, ranks Basic then Preferred then Extended | The Basic-part comparison tool; retain. |
| `tools/jlc/jlc_api.py` | JLC catalogue queries and local response cache | Retain; cache does not expire automatically. |
| `tools/jlc/bom_lines.py` | Groups BOM by specification and footprint | Retain; joint counts are a hardcoded footprint table. |
| `tools/jlc/audit.py` | Class/stock/price lookup and cost totals from the map | Retain; not an electrical-equivalence checker or a full assembly quote. |
| `tools/jlc/export_jlc.py` | Assembly BOM and placement export | Retain; angles need preview. It writes files before reporting missing-part failure; BOM/CPL mismatches only print warnings. |
| `tools/jlc/lcsc_map.csv` | Chosen LCSC parts keyed by spec/footprint | Sourcing record, not permission to substitute parts automatically. |

The remaining 11 Python tools support ongoing design work. `tools/3d/bbox.py`
inspects STEP geometry; `relink_pcb_paths.py` repairs schematic/PCB associations.
The netlist checker reuses the footprint auditor's parser without a generator dependency.

Removed the legacy schematic generator, compatibility simulation alias, four
one-time STEP generators, archived Python scripts, obsolete simulation code/logs
and Python bytecode. Existing schematic, PCB, footprint and STEP assets are retained.

Removed `tools/setup_pcb.py`, `tools/route_analysis.py`, `tools/route_board.py`,
`tools/stitch_planes.py` and `tools/route_report.py`, along with the obsolete
`reports/stitch-report.json`. Assembly placement export remains available; it
reads existing component coordinates without placing components.

## JLC and routing findings

The cached JLC audit reproduces **33 fitted LCSC parts: 16 Basic and 17 Extended**,
86 placements and 323 SMT joints. Its recorded component estimate is $39.3877 per
board at the catalogue quantity-10 tier, plus an assumed $51 Extended setup fee
per order. These are **cached September 16–17 figures, not a refreshed quote**;
minimum purchase, attrition and other order costs are excluded. The old mixed
report is preserved as sourcing history. No parts were substituted in this refresh.

The removed routing tools grew around incomplete Freerouting power-plane
connections: custom stitching was added, then those nets were excluded from later
routing. The obsolete stitching report listed U20.59, C40.1, C35.1 and C33.2 as
unreachable. This partial routing and its generated copper zones have now been
cleared from the working PCB at the owner's request.

Installed helpers outside the repo: `~/.local/bin/freerouting`, `freerouting-mcp`
and `kicad-dsn` (DSN export/SES import; import can overwrite the board). Freerouting
and Serena are configured MCP servers, but neither had callable tools exposed in
this session. Direct KiCad CLI and Python inspection supplied the needed evidence;
no new plugins or router services were installed or run.

## Files and maintenance

- `DESIGN_SPEC.md` is now the short owner-level design; `README.md` is its entry point.
- `PINOUT.md` holds GPIO details. `LIBRARIES.md`, the project symbols/footprints,
  STEP provenance and `datasheets/` hold component references.
- `power_bom.csv` and `reports/` contain derived artifacts. Export them after changes;
  a timestamp or an old screenshot is not proof that they match the current board.
  The schematic PDF, netlists, DRC/ERC and top SVG were refreshed here; the older
  PNG renders remain historical snapshots. PCB DRC and top SVG were refreshed
  again after routing removal; the obsolete stitching report was deleted.
- `backups/pre-input-power-refresh/` preserves replaced docs, simulation summaries
  and pre-edit hardware. Earlier `backups/` revisions are also historical. Legacy
  code copies were removed from all backup directories.
- `.history/` is editor history; `.serena/` is local indexing/configuration; `.claude/`
  contains a task lock. None is an electrical source of truth.
- Firmware is not implemented in this repository. GPIO possibilities and old thermal
  targets are not evidence of implemented firmware or tested operating limits.

The owner handles all PCB routing; this is recorded in AGENTS.md.

Future workflow: edit the schematic/PCB intentionally, export and check connectivity,
run the small input simulation when relevant, and use JLC search when selecting a
part. Routing and placement utilities have been removed. Add further simulation only for a specific,
observed problem. Do not redesign hardware merely to satisfy their old assumptions.
