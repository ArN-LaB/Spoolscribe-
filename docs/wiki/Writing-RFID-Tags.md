# Writing RFID Tags

SpoolScribe generates an **OpenSpool JSON payload** describing a spool. Writing
that payload onto a physical **NFC/RFID tag** is done with an NFC writer.

> SpoolScribe produces the data. The actual tag-writing depends on your hardware
> and the tag format your reader expects.

## The payload

A generated file looks like:

```json
{
  "protocol": "openspool",
  "version": "1.0",
  "type": "PLA",
  "color_hex": "91C500",
  "brand": "Polymaker",
  "min_temp": 190,
  "max_temp": 230,
  "bed_min_temp": 60,
  "bed_max_temp": 60,
  "diameter": 1.75,
  "density": 1.34,
  "sku": "PA03006",
  "product": "Panchroma PLA Silk",
  "color_name": "Silk Lime"
}
```

This follows the [OpenSpool](https://github.com/spuder/OpenSpool) convention.

## Writing to a tag

Typical options:

- A phone NFC app that writes NDEF/JSON records.
- A USB NFC reader/writer (e.g. PN532-based) with your own script.
- Any tooling your Snapmaker U1 firmware fork documents.

Match the tag type and record format expected by your reader.

See [[Snapmaker U1 & paxx12|Snapmaker-U1-and-paxx12]] for the firmware side.
