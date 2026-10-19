# Buttons

Button designs (`assets/d_*.svg`, 50 mm punch diameter, 38 mm motif diameter; see [specs.md](specs.md)) and a script that turns them into A4 print sheets.

## Requirements

- [Inkscape](https://inkscape.org/) 1.x. The script looks for it in the `INKSCAPE` environment variable, then on `PATH`, then in `/Applications/Inkscape.app`.
- `pdflatex` with the `graphicx`, `geometry` and `eso-pic` packages (included in a standard TeX Live / MacTeX install).
- For `--jpg` / `make jpg` only: `pdftoppm` (from poppler) or, if that isn't installed, `gs` (Ghostscript).
- Python 3.9 or newer. Only the standard library is used, so no `pip install` or `uv sync` is needed.

## Usage

1. Edit [buttons.csv](buttons.csv) and set how many copies of each design you want:

   ```csv
   design,count
   d_mqt,15
   d_mqsf,30
   # lines starting with # are ignored
   ```

   A design can be written as `d_mqt`, `mqt` or `d_mqt.svg`. Designs that aren't in the CSV get 0 copies, and the script lists them when it runs.

2. Generate the sheets with the default options:

   ```sh
   make           # buttons.csv -> buttons_print.pdf
   make preview   # -> buttons_preview.pdf (see below)
   make jpg       # buttons_print.pdf, rendered/buttons_print_p<N>.jpg at 600 dpi, and buttons_print_jpg.pdf
   make all       # all of the above
   make clean     # delete build/, rendered/ and all generated PDFs
   ```

   `make` only rebuilds when an `assets/d_*.svg`, `buttons.csv` or `make_sheets.py` has changed since the last build. Use `make -B` to rebuild anyway.

   The preview places one copy of every design and ignores `buttons.csv`. It also makes the hidden `btn-innerboundary` layer visible, so you can check that each motif stays inside it. It is for checking the designs, not for printing buttons.

   For other options, run the script directly:

   ```sh
   python3 make_sheets.py                 # same as make
   python3 make_sheets.py --min-gap 8     # more space between designs
   python3 make_sheets.py -c other.csv -o other.pdf
   python3 make_sheets.py --preview       # same as make preview
   python3 make_sheets.py --jpg           # print sheets and JPGs in one run (same result as make jpg)
   python3 make_sheets.py --jpg 300       # JPGs at 300 dpi instead
   python3 make_sheets.py --jpg-only      # only the JPG step, from the existing buttons_print.pdf (what make jpg runs)
   python3 make_sheets.py --preview --jpg # rendered/buttons_preview_p<N>.jpg and buttons_preview_jpg.pdf
   python3 make_sheets.py --init-csv 0    # write a fresh CSV template (won't overwrite an existing one)
   ```

   Run `python3 make_sheets.py --help` to see all options.

3. **Print `buttons_print.pdf` at "Actual size" / 100 %, not "fit to page"**, or the designs won't come out at 50 mm.

   `make jpg` also makes a raster version, for printers that render the vector PDF badly. Each page is saved as a JPG in `rendered/` (at 600 dpi, each A4 page is 4961 × 7016 px). The JPGs are then combined into `buttons_print_jpg.pdf`, with one full A4 page per JPG. pdflatex embeds the JPGs as they are, without compressing them again. Print this PDF at "Actual size" / 100 % as well. Each run first deletes the old `<name>_p<N>.jpg` files in `rendered/`, so pages left over from a longer earlier run don't stay around. `rendered/` is in `.gitignore`.

## How it works

1. It checks that every `assets/d_*.svg` is 50 × 50 mm and stops with an error if one isn't.
2. It re-renders every SVG to `build/pdf/*.pdf` with Inkscape, each time it runs. The PDF covers the SVG's page area, and text is converted to outlines, so fonts can't go missing when printing.
3. It places the designs at their original size, with no scaling, on A4 pages using pdflatex. Each design is stored once in the PDF and reused for every copy, so the file stays small and fully vector.

## Layout

- With the defaults (at least 5 mm to the paper edge, at least 5 mm between designs) you get 3 × 5 = 15 buttons per A4 page.
- Spare space is spread evenly: about 15 mm horizontally and about 7.8 mm vertically, both between designs and at the paper edges. This leaves room to position the punch when cutting. You can change the minimums with `--min-margin` and `--min-gap`.
- Designs are placed in CSV order and fill the pages one after another, so one page can hold more than one design.

## Notes and limitations

- Each SVG's 50 mm page is exactly what gets printed, and the design itself shows the cutting edge. The script adds no outline circles, crop marks, labels or scale bar.
- Temporary files (rendered PDFs, LaTeX files) go in `build/`, and the preview's go in `build/preview/`. The preview renders modified copies of the SVGs from `build/preview/svg/`, so your original files are never changed. The output goes to `buttons_print.pdf` unless you pass `-o`.
- Adding cut-guide circles, labels or a scale bar would be easier with a Python PDF library such as PyMuPDF. That would also remove the pdflatex dependency.
