# Use SpoolScribe v0.8.1

[Overview](../README.md) · [Documentation](README.md) · [Stable release](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.1) · [Release policy](RELEASE_POLICY.md)

The [visual tour](wiki/Visual-Tour.md) shows actual English-interface screenshots.
The same workflows are available in all four application languages.

## Interface language

SpoolScribe supports English, French, Spanish and Simplified Chinese. Automatic
uses a supported system language, otherwise English. Choose a language in
**Settings → Interface**, save, then restart now or later. Data, favourites and
preferences are retained. Filament names and external technical diagnostics are
not translated.

## Find and remember a filament

The main search covers manufacturers, products, materials and colours. Sidebar
searches narrow manufacturer/material lists. Materials stay alphabetically
ordered rather than moving according to their counts.

Hover over a manufacturer to reveal its favourite button, or use the context
menu. The name selects the manufacturer; browsing does not change favourites.
The same star is used for filament details and grid cards. Manufacturer and
filament favourite filters combine with other criteria and are remembered;
they filter results without deleting saved favourites. **Clear** resets all
three searches, filters and selection, while favourites remain intact.
Polymaker is the initial choice in a first session.

Manufacturer, material and data-state sections collapse independently with a
click or Space on the heading. A closed section still shows its active choice.
**Filters** reports the criteria and offers collapse/expand-all actions. Folding
changes presentation only: filter criteria, page, sorting, selection and
favourites remain intact; open/closed state is saved. Manufacturer/material
counts respect other filters; data-state counts cover the complete catalogue.
Lists have bounded heights and use the same restrained selection accent.

List/grid controls are beside the results. In list view, click a column heading
to sort, again to reverse; the context menu selects primary/secondary sort and
columns. Grid cards emphasise colour, retain readable product/manufacturer,
show diameter and a spool, and explicitly label incomplete/suspect data.
A manufacturer fixed by filtering is visually quieter. Keyboard focus is dotted,
distinct from selection; card stars remain clickable. Click an already selected
item, empty space or Escape to deselect. Pagination appears when needed.

## Read the filament details

One identity block combines logo, product, material and colour. The parallel
spool illustration shows flanges, spokes and winding based on the selected HEX.
Unknown/ambiguous colour stays neutral with a question mark; the illustration
invents no catalogue value and does not replace explicit colour selection.

Nozzle, bed, diameter and density are grouped. **Edit…** opens an in-card draft,
keeping identity and saved-value tiles visible and marking changed fields.
**Save a copy** creates a personal `Product @Personal` copy; its suffix can be
changed, for example to `@U1`. Cancelling writes nothing. Only edited fields
become confirmed corrections; an emptied field means unknown.

A personal HEX can be corrected. For a flagged colour, explicitly confirming the
shown HEX accepts it without changing it. Source data stays intact, and personal
values survive refreshes. Reusing the same suffix/reference updates its existing
copy. Before changing details/variant, clearing the selection through filters,
importing settings or closing, a dirty draft prompts save/discard/continue.
A dirty draft blocks export and preview.

**Details and sources** expands references/provenance and scrolls them into view.
Hover over a parameter to understand its use for the selected printer. Adapt
temperatures to the slicer and bed: a JSON value does not mean the printer will
automatically apply it.

The label-parameter panel groups nozzle, bed, diameter, density and colour.
Minimum/maximum ranges stay separate; effective, adjusted, unknown and suspect
values are labelled. A common source is shown once. **Value origins** exposes
per-field references, applicable Orca values and personal-copy provenance,
together with what the selected format actually retains. Unknown is never
presented as a difference. The reset arrow restores a reference only in the
personal copy; a suspect reference is not automatically restored. HEX is a
declared colour, not a measurement. OFD/SMDB identifiers are source identifiers,
not manufacturer articles. Data-state filters assess information, not physical
filament quality.

Printer details and filament editing/source details are mutually exclusive.
Opening either closes the other; closing one does not reopen its counterpart.
Dirty-draft save/discard/continue handling still applies. Preparation status and
export action remain visible, and the panels share edges and content-aware heights.

## Compare colours

The sidebar colour section groups a swatch/code and **Compare**. It works
without a filament selection and changes no record. The colour action in the
filament details opens the same section using that filament's colour.
Grid cards show a compact **Delta E** beside the diameter; smaller means closer
declared colour. The maximum-distance control opens colour settings.

The initial limit is **10**. Presets **3**, **10**, **20**, **all colours** or a
custom **0–200** value are saved/exported with preferences. They are exploration
ranges, not printed-colour certification thresholds. Distant results are hidden
and counted separately from non-comparable records.

Ranking uses list/grid results and respects sidebar filters; ties are resolved
by manufacturer, product, colour and reference. Unknown, conflicted, multicolour
and translucent entries are excluded and counted. Silk, metallic, glow and other
effects remain ranked but labelled. Delta E00 compares source-declared screen
colours; it does not predict printed appearance.

**Remove** disables comparison and clears unapplied input, becoming inactive
when nothing remains. **Clear** resets all filters without deleting favourites.
An empty field says colour code rather than displaying a fake example colour.
Folding the section keeps the selected colour active, shown in its heading and
filter summary. Results are labelled comparable colours. Colour help separates
results (target, counts and four exclusion cards) from method/limits; without a
target it shows method only, never fictional results.

### Enter Lab/RGB values or import a file

**Lab, RGB or file…** provides three entries: direct HEX/RGB/L*a*b* input,
labelled measurement-text paste, or CSV/TSV import. Pasted text requires a
confirmed primary value set. File import requires confirmed encoding, separator,
decimal convention and columns, then reports valid/to-correct/duplicate counts
before saving.

Measurements live in a local registry separate from the catalogue. They can be
saved, reused as targets, linked to an exact reference or detached without
changing catalogue colours. Each entry has its own draft and actions affect the
visible entry. Editing pasted text withdraws its interpretation. If a file maps
Lab and HEX/RGB, choose the primary set explicitly.

For L*a*b*, enter the device's documented illuminant/observer. **D65 and 2°**
allow indicative proximity to catalogue colours. D50, 10° and unknown conditions
are retained without ranking. Geometry, SCI/SCE, aperture, calibration and sample
material/finish/thickness/backing are optional and initially unknown; enter them
in additional details or file columns. A small distance does not guarantee the
printed result. Entry arrived in v0.7.0; guided workflows and device-entry presets
were refined in v0.8.0.

**Maximum 3 means Delta E ≤ 3**, not a percentage. The existing distance between
`C8E6A0` and `D8EEA3` is **3.035999**: excluded at 3, included at 10. The display
rounds upwards to **3.04**, preventing a boundary exceedance being hidden; the
filter uses the six-decimal computed value, available in the tooltip.

## Choose the actual spool packaging

In **Settings → Spools**, select preferred weight and optionally spool/refill.
The initial choice is **1 kg, either form**. Following the record keeps the
catalogue's proposed reference. A preference selects only a genuinely available
reference; form is used only when the source identifies it. If the weight is
unavailable, the actual reference stays selected and the details explain why.
No weight/refill is invented. A manual in-card choice takes priority for that
group during the session.

When sources disagree on colour, compare swatches and select your spool's shade.
Weight preference never resolves a colour conflict. Packaging is chosen among
the confirmed shade's references. A screen is not a colour measurement; material,
grade, diameter, transparency and multicolour variants remain distinct.

## Prepare an NFC export

The detail footer joins two steps: printer/reader setup with its available photo
and configure action, then label/file format. Specific machines/families use
bundled transparent product photographs, with the actual pictured family example
identified. Generic setups and standalone readers use labelled icons. These
visual references are shared by selection, hardware details and export;
[photograph provenance](PRINTER_VISUALS.md) is documented separately.

The conclusion says the file fits, with available-space gauge, or explains the
blocking input in everyday terms. The gauge includes the chosen reservation;
it does not prove a tag was written/read. Export details separate the prepare/
write/read-back journey from technical size cards and the exact engine diagnostic.

The main action follows readiness: export for NFC, correct characteristics,
specify/confirm colour or adjust the label. JSON/export inspection and reveal-file
actions stay visible. Reveal is enabled only after a successful session export
while that file exists; the last-export line says whether it matches current
selection/options. A file is neither a written tag nor printer acceptance.
Inspection scrolls to the file without enlarging the window. Each export offers
a destination, remembers the last one and confirms the saved path; cancelling
creates nothing. The proposed folder is also configurable in export settings.

For OpenTag3D, export inspection shows raw NDEF, decoded fields and bytes.
Missing explicit targets/mass trigger the single prepare-label action. Later
edits are available through export details and withdraw confirmation. Legacy
writer containers remain in the [OpenTag3D CLI/API](OPENTAG3D.md). The inspected
file equals an export with the same options. Advanced hardware settings retain
OpenSpool essential/full profiles and writing reservations. Another application
writes the tag; complete OpenSpool JSON archives remain in the main menu.

Colour accents are supplementary: purple for colour comparison, blue for
hardware, green for a fitting file and amber for incomplete steps. Labels/actions
always convey the state; colour alone carries no instruction.

### Digital SSQR1 QR and Companion

The digital contract is validated for OpenSpool 1.0/OpenTag3D 2.004, separately
from printing or physical acceptance. **Show QR Code — SpoolScribe Companion**
beside NFC export shares the same colour/draft/setup/capacity/target-value blocks.
It contains **the complete NFC message**, without a server/link. A generic reader
only displays transfer text; chip writing requires a Companion implementation.
Public mobile availability belongs on the [Companion page](COMPANION.md), not an
invented store link.

The QR snapshots opening-time values (timestamp shown). Changing the main window
cannot change its saved/printed content; reopen to include changes. It stays
complete, black on white, in both themes and at all allowed window sizes.
Label preview shows dimensions at an illustrative zoom; the display is not calibrated.

PNG/SVG save actions use the system dialog; cancelling writes nothing. If adding
an extension points to an existing file, overwrite confirmation is required.
Paper, printing and technical details sit in the lower scrolling area without
shrinking the QR. System printing rechecks accepted page format/resolution and
refuses excessive density. A job handed to the system does not prove a printed
or readable label: scan the actual result.

Each QR starts with **None — on-screen QR**. Optional medium choices include
50 × 50, 62 × 100, 100 × 150 mm, A4 and custom size. Previous dimensions remain
saved for later use; the driver supplies the printable area. Standard (M) or
Enhanced (Q) protection precedes print options. Redundancy may enlarge a code;
it is no scan guarantee. Technical details group message, QR structure, NFC
capacity and optional paper; SHA-256 can be copied separately.
See the [paper/printer guide](PRINTING_GUIDE.md).

## Configure the printer and reader

Open **My hardware** from the main menu. The browser searches brands/models with
available descriptions/photos; choose confirms, cancel preserves the prior setup.
Compose reader, software and installed solution with buttons. USB/network alone
does not confirm a plugin. The fixed summary distinguishes printer identification,
external inventory and standalone reading. Requirements/details groups versions,
drivers and connections.

Category cards cover export-capable setups, USB/network readers, original/
modified software, other RFID formats and integrations needing verification.
They explain their role and count choices matching the current search. Selecting
one filters; cancelling changes nothing. A model may belong to several categories;
filtering never confirms installed hardware/software. Choose an offered format
and NTAG215/216. Consult [setup limits](PRINTER-CONFIGURATIONS.md).

A photo or description does not make proprietary Bambu/Creality/Prusa OpenPrintTag
formats compatible. A fresh installation does not assume U1/paxx12. No firmware
is changed. The bundled printer list remains usable if no remote list exists;
other update errors are reported. See [visual sources](PRINTER_VISUALS.md).

## Refresh, preferences and backups

Refresh uses saved catalogue sources after consent; the first download offers
source selection. Change it in **Settings → Catalogue**. Information controls
expand source scope, counts and limits. The catalogue is not exhaustive: official
values take priority over community sources, and your corrections remain highest.
Disabling a source retains its old records. The report separates source statuses,
counts and expandable technical details. The database control opens the same
presentation with readable dates. Storage/retained-value details use a bounded
140-pixel scrolling area; returning restores the source list. Source-processing
success does not certify colours or resolve every ambiguous match.

Installers contain no catalogue or Orca profiles. The first consented download
creates the database; later downloads follow the chosen cadence, retaining cache
on failure. Restoration suppresses automatic refresh for that session. Filters,
favourites, sorts, columns, layout and export preferences are saved/exported.
Network consent is not imported. Application-update checks offer the official
download; replacement remains manual.

v0.8.1 adds preference-preview import/export, local ZIP backup, restoration
preview and explicit undo. Conflicts remain recoverable until resolved; unknown
third-party objects are retained rather than claimed restored. JSON/ZIP files
are **not encrypted**. See [settings](wiki/Settings.md) and
[backup/restore](wiki/Backup-and-Restore.md) for the complete current workflow.

## Layout, accessibility and project links

Standard controls are 32 logical pixels high; the primary export is 48. View-mode
icons share a 32-pixel group, same-row buttons share heights and paired detail
actions share widths. Menus use consistent content heights/margins. The detail
scrollbar appears only on overflow and the footer follows visible width.
Printer-search cards recalculate text height from available width across repeated
resizes rather than spreading text into spare height. The personal-copy editor
uses one aligned grid for suffix/six characteristics and save/cancel controls.

The splitter remembers panel widths within readability constraints. Down/right
arrows indicate open/closed sections, including hardware. Refresh progress names
the source and step number without implying source success. Settings/help windows
fit their opening screen; long content scrolls while close actions stay visible.
Tabs stay on one line where possible; otherwise visible arrows/wavy clipping
indicate hidden tabs and full titles remain in tooltips. Manufacturer logos gain
a subtle dark-theme halo without changing source images/colours.

Edit and source details are separate views; switching from a dirty draft asks
what to do. The active view replaces the summary to avoid duplicated values.
Temperature ranges share a line and other values retain units. Common provenance
and identical numeric references are not repeated; Orca/personal differences stay
inspectable without changing the actual exported values. A window can grow after
native layout if content scrolls and the screen has space; screen bounds/actions
remain respected and genuinely long content still scrolls.

About offers GitHub and **Support the project · Buy Me a Coffee** at
[arn_lab](https://buymeacoffee.com/arn_lab), opened only on a click. No remote
JavaScript widget is loaded. The destination matches [FUNDING.yml](../.github/FUNDING.yml).
Update checks clear their waiting state when complete. Other RFID/NFC formats
are explained in [NFC formats](FORMATS-NFC.md); paper references are informative
and no multi-label sheet is generated automatically.
