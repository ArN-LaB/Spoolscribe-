# Show the QR first; print only when needed

[User guide](USER_GUIDE.md) · [SSQR1 contract](QR_FORMAT.md)

The default workflow is digital: choose no paper or printer. A Companion
implementation must decode SSQR1 and write its NFC message. Official downloads
will be announced on the [Companion page](COMPANION.md).

## Choose for the intended use

| Use | SpoolScribe choice | Check |
| --- | --- | --- |
| Show or share a digital code | None — on-screen QR, PNG/SVG | No printer needed; a generic reader displays SSQR1 text |
| Attach a label to a spool | A sufficiently wide label or custom medium | Actual printable width, driver resolution, quiet zone and scan result |
| Desktop laser/inkjet printer | A4 or custom dimensions | Technology-compatible sheet, actual-size printing without automatic scaling; A4 mode does not provide a multi-label sheet template |

Commercial label dimensions are not a universal QR standard. For example,
[Avery square labels](https://www.avery.com/products/labels/shape/square-labels)
include 2 × 2 inches (**50.8 × 50.8 mm**), distinct from the generic 50 × 50 mm
preset. Enter your exact medium dimensions and margins.

The **62 × 100 mm** option shows *Brother DK-11202* as an example and asks you to
check printer compatibility. It is a documented commercial reference, not a
universal product code inferred from dimensions. No particular reference is
automatically assigned to generic 50 × 50 or 100 × 150 mm media.
[Brother brochure](https://www.brother.eu/-/media/product-downloads/uk/ql1100-ql110nwb-brochure.pdf),
reviewed 5 November 2026.

## A4 sheets: use the reference printed on the box

In the QR window, **Label sizes and references… → Paper references** lists
informative examples. Dimensions alone do not determine a universal code:
material, labels per sheet, margins and sales region also matter. No comparative
evidence supports describing these as best sellers.

| Example | Technology | Commercial dimensions/layout | Official template or page |
| --- | --- | --- | --- |
| Avery L7165 | Laser | 99.1 × 67.7 mm; 8 per A4 | [L7165 template](https://www.avery.co.uk/template-l7165), precise geometry 99.06 × 67.73 mm |
| Avery J8165 | Inkjet | 99.1 × 67.7 mm; 8 per A4 | [J8165-100](https://www.avery.fr/produit/etiquettes-dexpedition-j8165-100), software code J8165 |
| Brother DK-11202 | Compatible label printer | 62 × 100 mm roll | [Brother page](https://store.brother.co.uk/supplies/label-printers/labels/dk/dk11202); not an A4 sheet |

Save PNG/SVG, open the exact box-specified template in your normal software,
place the image and print at actual size. Test alignment on plain paper first.
SpoolScribe's **A4 page** mode prints one QR on a page, **not a pre-positioned
label sheet**. Template, driver and tray management stay outside the app.
Keep the QR quiet zone. A dense code may need a larger medium even with the right
commercial reference. Sources reviewed 5 November 2026; no physical printing claimed.

## Documented printer families

These are examples with specifications suitable for wider QR labels, not
SpoolScribe SSQR1 certification, popularity rankings or physical acceptance tests.
Your system driver and QR density remain decisive.

| Family | Relevant manufacturer specifications | Medium to examine |
| --- | --- | --- |
| Brother QL-800 / QL-810W / QL-820NWB | Standard 300 × 300 dpi, rolls up to 62 mm, stated printable width 58 mm | DK-11202 62 × 100 mm or suitable continuous roll; check driver margins |
| Zebra ZD421 | 203 dpi or optional 300 dpi; check variant and printable width | Wider media, for example around 100 × 150 mm; enter actual dimensions |
| Laser/inkjet | Depends on model and driver | Compatible adhesive sheet; printing QR requires no RFID hardware |

Primary references: [Brother QL](https://www.brother.eu/-/media/product-downloads/devices/nordics/eu_en/labelling-machines/ql_800_leaflet_english_single_pages.pdf),
[DK-11202](https://store.brother.co.uk/supplies/label-printers/labels/dk/dk11202),
[Zebra ZD421](https://www.zebra.com/us/en/products/printers/desktop/zd400-series/zd421.html).
Reviewed 4 November 2026. No proprietary driver or direct Bluetooth implementation
was added: the application uses installed printers through the system dialog.

## Why size depends on the message

The calculation uses the generated QR, not the printer brand. It retains four
white modules on each side and whole printer dots per module.
[DENSO WAVE](https://www.qrcode.com/en/howto/cell.html) recommends at least four
dots per module for stable use. Reduced three-dot mode is an explicit choice
requiring a scan test.

A version-15 QR has 77 modules per side, 85 including quiet zones. At four dots
per module it needs about **42.5 mm at 203 dpi** or **28.8 mm at 300 dpi**.
These are geometric minima, not scan guarantees. The selected driver is checked
again after the print dialog.

## Protection and checking

**Standard (M)** suits the normal workflow. **Enhanced (Q)** adds redundancy and
may make a denser/larger code. It is not a guaranteed percentage of surface you
can obscure: [error correction](https://www.qrcode.com/en/about/error_correction.html)
concerns encoded data and depends on the damage. Keep the code sharp, contrasted
and complete. Attach a label only after checking it scans. No physical printer,
scanner, phone or RFID-writing test is claimed here.
