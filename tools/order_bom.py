#!/usr/bin/env python3
"""Generate distributor order lists for a set of boards.

Totals every assembled part over the boards' PCBs (the same footprint fields
as tools/fab.py: Manufacturer, MPN, Value; DNP, excluded-from-BOM and
board-only footprints are skipped) and writes, for one set of boards:

  docs/orders/digikey-rev<REV>.csv   DigiKey BOM Manager upload
  docs/orders/mouser-rev<REV>.xlsx   Mouser BOM tool upload, in the column
                                     layout of Mouser's BOM template
  docs/orders/mouser-rev<REV>.csv    the same rows as CSV (readable diffs)
  docs/orders/mouser-rev<REV>-simple.xlsx   the same lines in five columns
                                     only (no duplicate columns to map)

MPNs pass through fab.MPN_FIXUPS first. Mouser spellings, Mouser part
numbers and parts not bought from Mouser are set below and in
tools/mouser_pn.csv (MPN -> Mouser part number, from Mouser's own BOM
check, so the upload matches without guessing).

Usage:
  tools/order_bom.py --rev A [boards/<name> ...]
  (default boards: the six ordered with rev A)
"""

import argparse
import csv
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fab import MPN_FIXUPS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BOARDS = ["core", "can-card", "io-card", "serial-card", "can-ssr", "probe-helper"]
CODE = {"core": "CO", "can-card": "CC", "io-card": "IO", "serial-card": "SE",
        "can-ssr": "SS", "probe-helper": "PH"}

# Mouser lists these MPNs under another spelling.
MOUSER_MPN = {"W6100-L": "W6100L"}
# Not stocked by Mouser: bought from DigiKey.
MOUSER_SKIP = {"T821110A1R100CEU"}

# Columns of the five-column Mouser upload.
MOUSER_SIMPLE_COLS = ["Mouser Part Number", "Manufacturer Part Number", "Manufacturer",
                      "Quantity", "Description"]

# Columns of Mouser's BOM template (MouserBomTemplate.xls); we fill the inputs.
MOUSER_COLS = ["Mfr Part Number (Input)", "Manufacturer Part Number", "Mouser Part Number",
               "Manufacturer Name", "Description", "Quantity 1", "Unit Price 1", "Quantity 2",
               "Unit Price 2", "Quantity 3", "Unit Price 3", "Quantity 4", "Unit Price 4",
               "Quantity 5", "Unit Price 5", "Order Quantity", "Order Unit Price", "Min./Mult.",
               "Availability", "Lead Time in Days", "Lifecycle", "NCNR", "RoHS", "Pb Free",
               "Package Type", "Datasheet URL", "Product Image", "Design Risk"]


def board_parts(board):
    """{(manufacturer, mpn, value): qty} for one board's PCB."""
    import pcbnew
    pcb = ROOT / "boards" / board / "hardware" / f"{board}.kicad_pcb"
    parts = {}
    for fp in pcbnew.LoadBoard(str(pcb)).GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_BOARD_ONLY or fp.IsExcludedFromBOM() or fp.IsDNP():
            continue

        def field(n):
            return fp.GetFieldText(n) if fp.HasField(n) else ""

        mpn = field("MPN")
        if not mpn:
            print(f"warning: {board} {fp.GetReference()} has no MPN", file=sys.stderr)
            continue
        key = (field("Manufacturer"), MPN_FIXUPS.get(mpn, mpn), fp.GetValue())
        parts[key] = parts.get(key, 0) + 1
    return parts


def collect(boards):
    """[(qty, mfr, mpn, description, [(board, qty), ...])], one line per MPN."""
    lines = {}
    for b in boards:
        for (mfr, mpn, value), n in board_parts(b).items():
            line = lines.setdefault(mpn, {"mfr": mfr, "value": value, "boards": {}})
            line["boards"][b] = line["boards"].get(b, 0) + n
    out = []
    for mpn, line in lines.items():
        per = [(b, line["boards"][b]) for b in boards if b in line["boards"]]
        out.append((sum(n for _, n in per), line["mfr"], mpn, line["value"], per))
    return sorted(out, key=lambda r: (r[3].lower(), r[2]))


def write_xlsx(path, rows):
    """Minimal one-sheet .xlsx (inline strings), standard library only."""
    def col(i):
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    def cell(ref, v):
        if isinstance(v, int):
            return f'<c r="{ref}"><v>{v}</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'

    body = "".join(
        f'<row r="{r + 1}">' + "".join(cell(f"{col(c)}{r + 1}", v) for c, v in enumerate(row) if v != "") + "</row>"
        for r, row in enumerate(rows))
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f'<sheetData>{body}</sheetData></worksheet>')
    files = {
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        "xl/worksheets/sheet1.xml": sheet,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))   # fixed time: stable output
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rev", required=True, help="revision the order is for (file names only)")
    ap.add_argument("boards", nargs="*", help="boards/<name> (default: the six rev A boards)")
    args = ap.parse_args()
    boards = [Path(b).name for b in args.boards] or BOARDS
    lines = collect(boards)
    out = ROOT / "docs" / "orders"
    rev = args.rev

    with (out / f"digikey-rev{rev}.csv").open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["Quantity", "Manufacturer Part Number", "Manufacturer", "Description", "Customer Reference"])
        for qty, mfr, mpn, desc, per in lines:
            w.writerow([qty, mpn, mfr, desc, " ".join(f"{b}:{n}" for b, n in per)])

    mouser_pn = {}
    pn_file = Path(__file__).resolve().parent / "mouser_pn.csv"
    for row in csv.DictReader(pn_file.open(newline="")):
        mouser_pn[row["MPN"]] = row["Mouser Part Number"]
    rows = [MOUSER_COLS]
    for qty, mfr, mpn, desc, per in lines:
        if mpn in MOUSER_SKIP:
            continue
        m = MOUSER_MPN.get(mpn, mpn)
        where = " ".join(f"{CODE.get(b, b)}{n}" for b, n in per)
        row = dict.fromkeys(MOUSER_COLS, "")
        row.update({"Mfr Part Number (Input)": m, "Manufacturer Part Number": m,
                    "Mouser Part Number": mouser_pn.get(m, ""), "Manufacturer Name": mfr,
                    "Description": f"{desc} [{where}]", "Quantity 1": qty, "Order Quantity": qty})
        rows.append([row[c] for c in MOUSER_COLS])
    write_xlsx(out / f"mouser-rev{rev}.xlsx", rows)
    ix = {c: i for i, c in enumerate(MOUSER_COLS)}
    write_xlsx(out / f"mouser-rev{rev}-simple.xlsx", [MOUSER_SIMPLE_COLS] + [
        [r[ix["Mouser Part Number"]], r[ix["Manufacturer Part Number"]], r[ix["Manufacturer Name"]],
         r[ix["Quantity 1"]], r[ix["Description"]]] for r in rows[1:]])
    with (out / f"mouser-rev{rev}.csv").open("w", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows(rows)

    print(f"{len(lines)} lines, {sum(r[0] for r in lines)} parts; Mouser: {len(rows) - 1} lines, "
          f"{sum(1 for r in rows[1:] if r[2])} with a Mouser part number")


if __name__ == "__main__":
    main()
