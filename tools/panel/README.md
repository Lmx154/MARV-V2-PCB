# Manufacturing panel tools

`MARV-V2-panel.kicad_pcb` is the saved 72 x 72 mm V-cut frame around the finished
board (see [panel notes](../../reports/manufacturing-panel.md)). These scripts
re-sync it from `MARV-V2.kicad_pcb` and check the result. They never route or
move source items: the panel keeps every source item verbatim except the four
straight Edge.Cuts segments.

Run everything from the repository root with the KiCad 10 Python (`import pcbnew`
must work) and `kicad-cli` on the path. Outputs go under `build/panel/`, which is
untracked. Close the PCB editor first and save the source board.

| Script | Purpose |
|---|---|
| `make_panel.py` | Rebuild the panel from the source board; the USB-C pocket is re-derived from J4. Dry run writes `build/panel/MARV-V2-panel.kicad_pcb`; `--apply` overwrites the saved panel |
| `verify_sync.py [panel]` | Panel keeps every source footprint, track, via and zone unchanged |
| `copper_clearance.py [panel]` | Minimum copper-to-V-score distance on all four copper layers (JLC needs 0.40 mm) |
| `check_pocket.py [panel ...]` | USB-C pocket against J4's courtyard |
| `merge_bom.py [bom.csv]` | One BOM line per LCSC part (default `production/bom.csv`); JLC skips repeated lines |
| `check_positions.py [dir]` | `bom.csv` and `positions.csv` in `dir` (default `production/`) against the source board |
| `annotate_panel.py` | Redraw `images/pcb/marv-v2-panel-annotated.png`: a top render of the panel with the four V-scores (read from the panel's `User.1` lines) and a legend. Needs Pillow |
| `make_manifest.py` | `order-manifest.json` with SHA-256 hashes and check results. Dry run writes `build/panel/order-manifest.json`; `--apply` overwrites `production/order-manifest.json` |

## Refresh sequence

```sh
mkdir -p build/panel

# 1. Sync the panel (overwrites MARV-V2-panel.kicad_pcb), then copy the rules
python3 tools/panel/make_panel.py --apply
cp MARV-V2.kicad_dru MARV-V2-panel.kicad_dru
sed 's/"filename": "MARV-V2.kicad_pro"/"filename": "MARV-V2-panel.kicad_pro"/' MARV-V2.kicad_pro > MARV-V2-panel.kicad_pro

# 2. Checks
python3 tools/panel/verify_sync.py
python3 tools/panel/copper_clearance.py > build/panel/copper-clearance.json
python3 tools/panel/check_pocket.py
kicad-cli pcb drc --severity-all --format json -o build/panel/drc-panel.json MARV-V2-panel.kicad_pcb
kicad-cli pcb drc --schematic-parity --severity-all --format json -o build/panel/drc-source.json MARV-V2.kicad_pcb
kicad-cli sch erc --severity-all --format json -o build/panel/erc-source.json MARV-V2.kicad_sch

# 3. Fabrication Toolkit CLI (writes production/; the options match fabrication-toolkit-options.json)
REPO=$PWD
(cd ~/.local/share/kicad/10.0/3rdparty/plugins && python3 -m com_github_bennymeg_JLC-Plugin-for-KiCad.cli \
  --path "$REPO/MARV-V2-panel.kicad_pcb" --autoTranslate --excludeDNP --user1VCut --nonInteractive)

# 4. Strip the drill-map drawings from the upload ZIP, merge BOM lines that share an
#    LCSC number (JLC leaves repeated lines unplaced), then check the CSVs
zip -d production/MARV-V2-panel.zip '*drl_map*'
python3 tools/panel/merge_bom.py
python3 tools/panel/check_positions.py
(cd production && sha256sum MARV-V2-panel.zip bom.csv positions.csv > SHA256SUMS)

# 5. Manifest
python3 tools/panel/make_manifest.py --apply

# 6. Panel image for the report (writes images/pcb/marv-v2-panel-annotated.png)
python3 tools/panel/annotate_panel.py
```

Expect: `verify_sync.py` lists only the four removed source outline lines and the
panel-only tooling, fiducial, outline and V-cut items; the panel DRC counts equal
the source DRC counts with 0 unconnected items; minimum clearance at least 0.40 mm.
The Fabrication Toolkit runs with the options saved in
`fabrication-toolkit-options.json`. Then review JLCPCB's CAM and assembly previews
and update [reports/manufacturing-panel.md](../../reports/manufacturing-panel.md)
if the figures change.

`make_manifest.py` keeps the hand-entered facts in the manifest (ERC result,
V-score positions, limitations); edit the script if those change.

## Dry run (changes nothing tracked or in `production/`)

Everything above can run against a copy in `build/panel/`. The Fabrication Toolkit
writes `production/` beside the board it is given, so give it the copy:

```sh
python3 tools/panel/make_panel.py                          # without --apply: build/panel/MARV-V2-panel.kicad_pcb
cp MARV-V2-panel.kicad_pro MARV-V2-panel.kicad_dru fp-lib-table build/panel/
ln -sfn ../../MARV_Packages.pretty build/panel/MARV_Packages.pretty
python3 tools/panel/verify_sync.py build/panel/MARV-V2-panel.kicad_pcb
python3 tools/panel/copper_clearance.py build/panel/MARV-V2-panel.kicad_pcb > build/panel/copper-clearance.json
python3 tools/panel/check_pocket.py build/panel/MARV-V2-panel.kicad_pcb
kicad-cli pcb drc --severity-all --format json -o build/panel/drc-panel.json build/panel/MARV-V2-panel.kicad_pcb
# ... drc-source.json and erc-source.json as in step 2, then:
REPO=$PWD
(cd ~/.local/share/kicad/10.0/3rdparty/plugins && python3 -m com_github_bennymeg_JLC-Plugin-for-KiCad.cli \
  --path "$REPO/build/panel/MARV-V2-panel.kicad_pcb" --autoTranslate --excludeDNP --user1VCut --nonInteractive --noBackup)
zip -d build/panel/production/MARV-V2-panel.zip '*drl_map*'
python3 tools/panel/check_positions.py build/panel/production
python3 tools/panel/make_manifest.py                       # build/panel/order-manifest.json; hashes production/ read-only
```
