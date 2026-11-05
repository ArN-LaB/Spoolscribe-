# Find a filament from colour values

[Help home](Home.md) · [Filaments](Filaments-and-Favourites.md) · [Settings](Settings.md)

## Start with a HEX code

Enter a code or pick a swatch in **Colours**, then click **Compare**. Your other
filters still apply. The closest declared catalogue colours appear first.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-search.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-search.png" alt="Compare declared screen colours" width="1100"></a>
</p>
<p align="center"><strong>Compare declared screen colours</strong><br><sub>A smaller ΔE means a closer match.</sub></p>

**Maximum ΔE 3** means **ΔE ≤ 3**, not “around 3” or a percentage. A value 3.04
is excluded at 3 and included at 10. Displayed distances are rounded upward to
the hundredth; the threshold uses the calculated value. Effects, gloss and
transparency can change the printed result. **Remove** clears the colour comparison.
Change the limit through **Maximum difference** or **Settings → Colours**.

## Use Lab, RGB or a file

The **Lab, RGB or file…** button is for values copied from another application,
a document or a measuring device. Desktop does not control a device or take a measurement.

| Your values | Choose | What to check |
| --- | --- | --- |
| HEX or RGB | sRGB HEX or 8-bit RGB | RGB uses integers 0–255. Do not enter Display P3/Adobe RGB as sRGB. |
| L*, a*, b* | CIELAB | Copy the illuminant and observer from the source. Do not guess them. |
| Text copied from an application | Paste | Review the interpreted set. Editing the text invalidates the previous interpretation. |
| CSV/TSV file | Import | Confirm encoding, separator, decimals and mapped columns before saving. |

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-lab.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-lab.png" alt="Enter documented Lab values" width="800"></a>
</p>
<p align="center"><strong>Enter documented Lab values</strong><br><sub>D65 and 2° are required for indicative catalogue comparison.</sub></p>

Unknown conditions, D50 or 10° can be **saved**, but cannot be ranked against the
catalogue. D65/2° is not inferred from a device’s name. Optional sample information
helps you recognise an entry later; it does not turn a declared HEX into a physical measurement.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-paste.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-paste.png" alt="Review copied values" width="800"></a>
</p>
<p align="center"><strong>Review copied values</strong><br><sub>Choose the intended set before saving or searching.</sub></p>
<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-import.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-import.png" alt="Check a file before import" width="850"></a>
</p>
<p align="center"><strong>Check a file before import</strong><br><sub>The input file is never modified.</sub></p>

## Reuse device entry settings explicitly

Under optional information, record the device and documented conditions, then
**Save these settings…**. At a later entry, select the preset and click **Use these
settings**. A default only proposes the preset: it does not silently apply it.
Calibration, sample preparation, date and colour coordinates are never reused.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/device-preset.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/device-preset.png" alt="Remember entry settings" width="800"></a>
</p>
<p align="center"><strong>Remember entry settings</strong><br><sub>A device preset is not a driver or a calibration.</sub></p>

## Save and find a reference again

**Saved** keeps the original values and conditions. Select an entry to search,
rename, link to an exact filament reference, detach or delete it. Registry backup
restoration is explicit. Measurements and device presets live beside the user
catalogue, not inside the installer or the settings export.

<p align="center">
  <a href="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-saved.png"><img src="https://raw.githubusercontent.com/ArN-LaB/Spoolscribe-/main/docs/images/colour-saved.png" alt="Keep identifiable reference values" width="800"></a>
</p>
<p align="center"><strong>Keep identifiable reference values</strong><br><sub>Equal colour values can still be different saved references.</sub></p>

[Full scientific limits and file bounds](https://github.com/ArN-LaB/Spoolscribe-/blob/main/docs/COLOUR_MEASUREMENTS.md).
No USB/Bluetooth driver, instrument certification or proprietary device format support is implied.
