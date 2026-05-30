# Snapmaker U1 & the paxx12 firmware fork

SpoolScribe exists because the **Snapmaker U1** firmware was opened up by the
**paxx12** community fork, which exposes the printer's onboard **RFID reader**.

## Why this matters

With the RFID reader accessible, the U1 can **read a tag on each spool** and know
exactly what filament is loaded — including spools sitting in:

- **PolyDryer + PolyBox** drying/storage boxes, and
- **AMS-style** multi-material feeders.

No more manually selecting the filament for each slot.

## The workflow

1. **SpoolScribe** generates an OpenSpool payload for a given SKU.
2. You **write** that payload onto an NFC/RFID tag (see
   [[Writing RFID Tags|Writing-RFID-Tags]]).
3. You stick the tag on the spool / spool holder.
4. The **U1 (paxx12 firmware)** reads it and auto-configures the filament.

## Important

- This is a **community hobby setup**, "just for fun".
- It is **not** official Snapmaker or Polymaker functionality.
- Flashing custom firmware is at your own risk. Follow the paxx12 project's own
  instructions and safety notes.

> Links to the firmware fork and hardware specifics belong to those projects;
> this wiki only covers the SpoolScribe side.
