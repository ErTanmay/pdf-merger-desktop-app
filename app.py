#!/usr/bin/env python3
"""
PDF Toolkit - Professional PDF Utility Suite
==============================================
Features:
  - Merge PDFs (with reordering: Move Up / Move Down)
  - Compress PDF (Low / Medium / High compression levels)
  - Split PDF (by page ranges, or one file per page)
  - Extract Pages (custom page ranges into a new PDF)
  - Rotate Pages (90 / 180 / 270 degrees, all or selected pages)
  - Password Protect PDF
  - Unlock (Decrypt) PDF
  - Modern ttk UI with progress bar and status feedback

Dependencies:
  pip install pypdf pymupdf pillow

Run:
  python pdf_toolkit.py
"""

import os
import io
import threading
import traceback

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from pypdf import PdfReader, PdfWriter
import fitz  # PyMuPDF

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

APP_AUTHOR = "Tanmay Lokhande"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def parse_page_ranges(text, total_pages):
    """
    Parse a string like '1-3,5,7-9' into a sorted list of unique
    0-indexed page numbers. Raises ValueError on bad input.
    """
    text = text.strip()
    if not text:
        raise ValueError("Page range cannot be empty.")
    pages = set()
    parts = text.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2:
                raise ValueError(f"Invalid range: '{part}'")
            start, end = bounds[0].strip(), bounds[1].strip()
            if not start.isdigit() or not end.isdigit():
                raise ValueError(f"Invalid range: '{part}'")
            start, end = int(start), int(end)
            if start < 1 or end > total_pages or start > end:
                raise ValueError(f"Range '{part}' out of bounds (1-{total_pages}).")
            for p in range(start, end + 1):
                pages.add(p - 1)
        else:
            if not part.isdigit():
                raise ValueError(f"Invalid page number: '{part}'")
            p = int(part)
            if p < 1 or p > total_pages:
                raise ValueError(f"Page {p} out of bounds (1-{total_pages}).")
            pages.add(p - 1)
    return sorted(pages)


def human_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


# ----------------------------------------------------------------------
# Main Application
# ----------------------------------------------------------------------

class PDFToolkitApp(tk.Tk):
    PRIMARY = "#2563eb"
    PRIMARY_DARK = "#1d4ed8"
    BG = "#f3f4f6"
    SURFACE = "#ffffff"
    TEXT = "#111827"
    MUTED = "#6b7280"
    SUCCESS = "#16a34a"
    DANGER = "#dc2626"

    def __init__(self):
        super().__init__()
        self.title(f"PDF Toolkit — Merge, Compress & More  |  Developed by {APP_AUTHOR}")
        self.geometry("900x650")
        self.minsize(820, 600)
        self.configure(bg=self.BG)

        self._build_style()
        self._build_layout()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("TFrame", background=self.BG)
        style.configure("Surface.TFrame", background=self.SURFACE)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Surface.TLabel", background=self.SURFACE, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=self.BG, foreground=self.TEXT,
                         font=("Segoe UI", 18, "bold"))
        style.configure("SubHeader.TLabel", background=self.SURFACE, foreground=self.TEXT,
                         font=("Segoe UI", 13, "bold"))
        style.configure("Muted.TLabel", background=self.SURFACE, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Status.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 9))

        style.configure("TNotebook", background=self.BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 8), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", self.SURFACE)],
                  foreground=[("selected", self.PRIMARY)])

        style.configure("Accent.TButton", background=self.PRIMARY, foreground="white",
                         font=("Segoe UI", 10, "bold"), padding=8, borderwidth=0)
        style.map("Accent.TButton", background=[("active", self.PRIMARY_DARK)])

        style.configure("TButton", padding=6, font=("Segoe UI", 9))
        style.configure("TRadiobutton", background=self.SURFACE, font=("Segoe UI", 10))
        style.configure("TEntry", padding=4)
        style.configure("Horizontal.TProgressbar", troughcolor=self.BG, background=self.PRIMARY)

    def _build_layout(self):
        header = ttk.Frame(self, style="TFrame")
        header.pack(fill="x", padx=20, pady=(16, 4))
        title_col = ttk.Frame(header, style="TFrame")
        title_col.pack(side="left")
        ttk.Label(title_col, text="📄 PDF Toolkit", style="Header.TLabel").pack(anchor="w")
        ttk.Label(title_col, text=f"Developed by {APP_AUTHOR}",
                  style="Status.TLabel").pack(anchor="w")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self.tabs = {}
        self._add_tab(ViewTab(self.notebook, self), "🔍 View")
        self._add_tab(MergeTab(self.notebook, self), "🔗 Merge")
        self._add_tab(CompressTab(self.notebook, self), "🗜 Compress")
        self._add_tab(SplitTab(self.notebook, self), "✂ Split")
        self._add_tab(ExtractTab(self.notebook, self), "📑 Extract")
        self._add_tab(RotateTab(self.notebook, self), "↻ Rotate")
        self._add_tab(ProtectTab(self.notebook, self), "🔒 Protect")
        self._add_tab(UnlockTab(self.notebook, self), "🔓 Unlock")

        # Shared status bar + progress bar
        footer = ttk.Frame(self, style="TFrame")
        footer.pack(fill="x", padx=20, pady=(0, 16))
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").pack(side="left")
        self.progress = ttk.Progressbar(footer, mode="determinate", length=300,
                                         style="Horizontal.TProgressbar")
        self.progress.pack(side="right")

        credit = ttk.Frame(self, style="TFrame")
        credit.pack(fill="x", padx=20, pady=(0, 10))
        ttk.Label(credit, text=f"© {APP_AUTHOR} — PDF Toolkit",
                  style="Status.TLabel").pack(side="right")

    def _add_tab(self, frame, label):
        self.notebook.add(frame, text=label)

    # ------------------------------------------------------------------
    # Shared UI helpers used by every tab
    # ------------------------------------------------------------------
    def set_status(self, text, color=None):
        self.status_var.set(text)

    def set_progress(self, value, maximum=100):
        self.progress["maximum"] = maximum
        self.progress["value"] = value
        self.update_idletasks()

    def run_task(self, func, on_success=None, on_error=None):
        """Run `func` in a background thread so the UI stays responsive."""

        def wrapper():
            try:
                self.set_progress(0)
                result = func()
                self.set_progress(100)
                self.set_status("Done.")
                if on_success:
                    self.after(0, lambda: on_success(result))
            except Exception as e:
                traceback.print_exc()
                self.set_progress(0)
                self.set_status("Failed.")
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
                if on_error:
                    self.after(0, lambda: on_error(e))

        threading.Thread(target=wrapper, daemon=True).start()


# ----------------------------------------------------------------------
# Reusable widget builders
# ----------------------------------------------------------------------

def card(parent):
    frame = ttk.Frame(parent, style="Surface.TFrame", padding=20)
    frame.pack(fill="both", expand=True, padx=4, pady=4)
    return frame


def file_picker_row(parent, label_text, var, browse_cmd, row):
    ttk.Label(parent, text=label_text, style="Surface.TLabel").grid(
        row=row, column=0, sticky="w", pady=6)
    entry = ttk.Entry(parent, textvariable=var, width=55)
    entry.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
    ttk.Button(parent, text="Browse…", command=browse_cmd).grid(row=row, column=2, pady=6)
    return entry


# ----------------------------------------------------------------------
# TAB 0: View
# ----------------------------------------------------------------------

class ViewTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app
        self.doc = None
        self.page_index = 0
        self.zoom = 1.4
        self.tk_img = None

        body = card(self)
        ttk.Label(body, text="View PDF", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Open a PDF and preview its pages before running an operation.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        self.input_var = tk.StringVar()
        file_picker_row(form, "PDF file:", self.input_var, self.browse_input, 0)

        if not PIL_AVAILABLE:
            ttk.Label(body, text="Pillow is required to preview pages. Install with: pip install pillow",
                      style="Muted.TLabel").pack(anchor="w", pady=(12, 0))
            return

        toolbar = ttk.Frame(body, style="Surface.TFrame")
        toolbar.pack(fill="x", pady=(12, 8))
        ttk.Button(toolbar, text="◀ Prev", command=self.prev_page).pack(side="left")
        self.page_label_var = tk.StringVar(value="Page 0 / 0")
        ttk.Label(toolbar, textvariable=self.page_label_var, style="Surface.TLabel").pack(
            side="left", padx=12)
        ttk.Button(toolbar, text="Next ▶", command=self.next_page).pack(side="left")
        ttk.Button(toolbar, text="Zoom In +", command=lambda: self.change_zoom(0.25)).pack(
            side="left", padx=(24, 0))
        ttk.Button(toolbar, text="Zoom Out −", command=lambda: self.change_zoom(-0.25)).pack(
            side="left", padx=4)

        canvas_frame = ttk.Frame(body, style="Surface.TFrame")
        canvas_frame.pack(fill="both", expand=True)
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, bg="#e5e7eb", highlightthickness=0)
        vscroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        hscroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)
            self.load_pdf(p)

    def load_pdf(self, path):
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(path)
            self.page_index = 0
            self.app.set_status(f"Loaded {os.path.basename(path)} ({len(self.doc)} pages).")
            self.render_page()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open PDF:\n{e}")

    def render_page(self):
        if not self.doc:
            return
        page = self.doc[self.page_index]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_img)
        self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))
        self.page_label_var.set(f"Page {self.page_index + 1} / {len(self.doc)}")

    def prev_page(self):
        if self.doc and self.page_index > 0:
            self.page_index -= 1
            self.render_page()

    def next_page(self):
        if self.doc and self.page_index < len(self.doc) - 1:
            self.page_index += 1
            self.render_page()

    def change_zoom(self, delta):
        if not self.doc:
            return
        self.zoom = max(0.25, min(4.0, round(self.zoom + delta, 2)))
        self.render_page()


# ----------------------------------------------------------------------
# TAB 1: Merge
# ----------------------------------------------------------------------

class MergeTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app
        self.files = []

        body = card(self)
        ttk.Label(body, text="Merge PDFs", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Add two or more PDFs, reorder as needed, then merge.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        list_frame = ttk.Frame(body, style="Surface.TFrame")
        list_frame.pack(fill="both", expand=True)

        self.listbox = tk.Listbox(list_frame, height=12, selectmode=tk.SINGLE,
                                   font=("Segoe UI", 10), activestyle="dotbox")
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        scroll.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)

        btn_col = ttk.Frame(list_frame, style="Surface.TFrame")
        btn_col.pack(side="left", fill="y", padx=(10, 0))
        ttk.Button(btn_col, text="Add PDFs", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btn_col, text="Remove", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btn_col, text="Move Up ↑", command=lambda: self.move(-1)).pack(fill="x", pady=2)
        ttk.Button(btn_col, text="Move Down ↓", command=lambda: self.move(1)).pack(fill="x", pady=2)
        ttk.Button(btn_col, text="Clear All", command=self.clear_all).pack(fill="x", pady=2)

        out_frame = ttk.Frame(body, style="Surface.TFrame")
        out_frame.pack(fill="x", pady=(16, 0))
        out_frame.columnconfigure(1, weight=1)
        self.output_var = tk.StringVar()
        file_picker_row(out_frame, "Output file:", self.output_var, self.browse_output, 0)

        ttk.Button(body, text="Merge PDFs", style="Accent.TButton",
                   command=self.merge).pack(anchor="e", pady=(16, 0))

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.listbox.insert(tk.END, os.path.basename(p))

    def remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.listbox.delete(idx)
        del self.files[idx]

    def move(self, direction):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.files):
            return
        self.files[idx], self.files[new_idx] = self.files[new_idx], self.files[idx]
        text = self.listbox.get(idx)
        self.listbox.delete(idx)
        self.listbox.insert(new_idx, text)
        self.listbox.selection_set(new_idx)

    def clear_all(self):
        self.files.clear()
        self.listbox.delete(0, tk.END)

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def merge(self):
        if len(self.files) < 2:
            messagebox.showerror("Error", "Please add at least two PDF files.")
            return
        output = self.output_var.get().strip()
        if not output:
            messagebox.showerror("Error", "Please choose an output file.")
            return

        def task():
            self.app.set_status("Merging PDFs…")
            writer = PdfWriter()
            total = len(self.files)
            for i, f in enumerate(self.files):
                writer.append(f)
                self.app.set_progress(int((i + 1) / total * 90), 100)
            with open(output, "wb") as fp:
                writer.write(fp)
            writer.close()
            return output

        self.app.run_task(task, on_success=lambda out: messagebox.showinfo(
            "Success", f"Merged {len(self.files)} files into:\n{out}"))


# ----------------------------------------------------------------------
# TAB 2: Compress
# ----------------------------------------------------------------------

class CompressTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app

        body = card(self)
        ttk.Label(body, text="Compress PDF", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Reduce file size by cleaning structure and recompressing images.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        file_picker_row(form, "Input PDF:", self.input_var, self.browse_input, 0)
        self.output_var = tk.StringVar()
        file_picker_row(form, "Output PDF:", self.output_var, self.browse_output, 1)

        ttk.Label(body, text="Compression Level:", style="Surface.TLabel").pack(anchor="w", pady=(16, 4))
        self.level_var = tk.StringVar(value="medium")
        level_frame = ttk.Frame(body, style="Surface.TFrame")
        level_frame.pack(anchor="w")
        ttk.Radiobutton(level_frame, text="Low (safest, smallest reduction)",
                         variable=self.level_var, value="low").pack(anchor="w", pady=2)
        ttk.Radiobutton(level_frame, text="Medium (balanced quality & size)",
                         variable=self.level_var, value="medium").pack(anchor="w", pady=2)
        ttk.Radiobutton(level_frame, text="High (max compression, recompresses images)",
                         variable=self.level_var, value="high").pack(anchor="w", pady=2)

        if not PIL_AVAILABLE:
            ttk.Label(body, text="Note: Pillow not installed — High level will fall back to Medium.",
                      style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

        ttk.Button(body, text="Compress PDF", style="Accent.TButton",
                   command=self.compress).pack(anchor="e", pady=(20, 0))

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)
            if not self.output_var.get():
                base, ext = os.path.splitext(p)
                self.output_var.set(f"{base}_compressed{ext}")

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def compress(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()
        level = self.level_var.get()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not out:
            messagebox.showerror("Error", "Please choose an output file.")
            return

        def task():
            self.app.set_status(f"Compressing ({level})…")
            original_size = os.path.getsize(src)
            doc = fitz.open(src)

            if level == "high" and PIL_AVAILABLE:
                seen_xrefs = set()
                total_pages = len(doc)
                for page_index in range(total_pages):
                    page = doc[page_index]
                    for img in page.get_images(full=True):
                        xref = img[0]
                        if xref in seen_xrefs:
                            continue
                        seen_xrefs.add(xref)
                        try:
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            pil_img = Image.open(io.BytesIO(image_bytes))
                            if pil_img.mode in ("RGBA", "P", "LA"):
                                pil_img = pil_img.convert("RGB")
                            buf = io.BytesIO()
                            pil_img.save(buf, format="JPEG", quality=45, optimize=True)
                            page.replace_image(xref, stream=buf.getvalue())
                        except Exception:
                            pass  # skip images that can't be recompressed safely
                    self.app.set_progress(int((page_index + 1) / total_pages * 70), 100)

            save_kwargs = dict(garbage=4, clean=True, deflate=True,
                                deflate_images=True, deflate_fonts=True)
            if level == "low":
                save_kwargs = dict(garbage=1, clean=True, deflate=True)
            elif level == "medium":
                save_kwargs = dict(garbage=3, clean=True, deflate=True, deflate_images=True)

            self.app.set_progress(85, 100)
            doc.save(out, **save_kwargs)
            doc.close()
            new_size = os.path.getsize(out)
            return original_size, new_size

        def on_success(result):
            orig, new = result
            saved = max(0, orig - new)
            pct = (saved / orig * 100) if orig else 0
            messagebox.showinfo(
                "Compression Complete",
                f"Original size: {human_size(orig)}\n"
                f"New size: {human_size(new)}\n"
                f"Reduced by: {pct:.1f}%"
            )

        self.app.run_task(task, on_success=on_success)


# ----------------------------------------------------------------------
# TAB 3: Split
# ----------------------------------------------------------------------

class SplitTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app

        body = card(self)
        ttk.Label(body, text="Split PDF", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Split a PDF into multiple files by page or by custom ranges.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        file_picker_row(form, "Input PDF:", self.input_var, self.browse_input, 0)
        self.outdir_var = tk.StringVar()
        file_picker_row(form, "Output folder:", self.outdir_var, self.browse_outdir, 1)

        self.mode_var = tk.StringVar(value="every_page")
        mode_frame = ttk.Frame(body, style="Surface.TFrame")
        mode_frame.pack(anchor="w", pady=(16, 4), fill="x")
        ttk.Radiobutton(mode_frame, text="Split into one PDF per page",
                         variable=self.mode_var, value="every_page",
                         command=self.toggle_mode).pack(anchor="w", pady=2)
        ttk.Radiobutton(mode_frame, text="Split by custom ranges (e.g. 1-3,4-6,7-10)",
                         variable=self.mode_var, value="ranges",
                         command=self.toggle_mode).pack(anchor="w", pady=2)

        self.ranges_var = tk.StringVar()
        self.ranges_entry = ttk.Entry(body, textvariable=self.ranges_var, width=50, state="disabled")
        self.ranges_entry.pack(anchor="w", pady=(4, 0))

        ttk.Button(body, text="Split PDF", style="Accent.TButton",
                   command=self.split).pack(anchor="e", pady=(20, 0))

    def toggle_mode(self):
        self.ranges_entry.config(state="normal" if self.mode_var.get() == "ranges" else "disabled")

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)

    def browse_outdir(self):
        p = filedialog.askdirectory()
        if p:
            self.outdir_var.set(p)

    def split(self):
        src = self.input_var.get().strip()
        outdir = self.outdir_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not outdir:
            messagebox.showerror("Error", "Please choose an output folder.")
            return

        def task():
            self.app.set_status("Splitting PDF…")
            reader = PdfReader(src)
            total_pages = len(reader.pages)
            base = os.path.splitext(os.path.basename(src))[0]
            created = []

            if self.mode_var.get() == "every_page":
                for i in range(total_pages):
                    writer = PdfWriter()
                    writer.add_page(reader.pages[i])
                    out_path = os.path.join(outdir, f"{base}_page{i + 1}.pdf")
                    with open(out_path, "wb") as fp:
                        writer.write(fp)
                    created.append(out_path)
                    self.app.set_progress(int((i + 1) / total_pages * 100), 100)
            else:
                ranges_text = self.ranges_var.get().strip()
                if not ranges_text:
                    raise ValueError("Please enter page ranges, e.g. 1-3,4-6,7-10")
                groups = [g.strip() for g in ranges_text.split(",") if g.strip()]
                for idx, group in enumerate(groups):
                    pages = parse_page_ranges(group, total_pages)
                    writer = PdfWriter()
                    for p in pages:
                        writer.add_page(reader.pages[p])
                    out_path = os.path.join(outdir, f"{base}_part{idx + 1}.pdf")
                    with open(out_path, "wb") as fp:
                        writer.write(fp)
                    created.append(out_path)
                    self.app.set_progress(int((idx + 1) / len(groups) * 100), 100)
            return created

        self.app.run_task(task, on_success=lambda files: messagebox.showinfo(
            "Success", f"Created {len(files)} file(s) in:\n{outdir}"))


# ----------------------------------------------------------------------
# TAB 4: Extract Pages
# ----------------------------------------------------------------------

class ExtractTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app

        body = card(self)
        ttk.Label(body, text="Extract Pages", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Pull specific pages out into a brand new PDF.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        file_picker_row(form, "Input PDF:", self.input_var, self.browse_input, 0)
        self.output_var = tk.StringVar()
        file_picker_row(form, "Output PDF:", self.output_var, self.browse_output, 1)

        ttk.Label(body, text="Pages to extract (e.g. 1-3,5,7-9):",
                  style="Surface.TLabel").pack(anchor="w", pady=(16, 4))
        self.pages_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.pages_var, width=50).pack(anchor="w")

        ttk.Button(body, text="Extract Pages", style="Accent.TButton",
                   command=self.extract).pack(anchor="e", pady=(20, 0))

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)
            if not self.output_var.get():
                base, ext = os.path.splitext(p)
                self.output_var.set(f"{base}_extracted{ext}")

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def extract(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()
        pages_text = self.pages_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not out:
            messagebox.showerror("Error", "Please choose an output file.")
            return

        def task():
            self.app.set_status("Extracting pages…")
            reader = PdfReader(src)
            total_pages = len(reader.pages)
            pages = parse_page_ranges(pages_text, total_pages)
            writer = PdfWriter()
            for i, p in enumerate(pages):
                writer.add_page(reader.pages[p])
                self.app.set_progress(int((i + 1) / len(pages) * 100), 100)
            with open(out, "wb") as fp:
                writer.write(fp)
            return len(pages)

        self.app.run_task(task, on_success=lambda n: messagebox.showinfo(
            "Success", f"Extracted {n} page(s) to:\n{out}"))


# ----------------------------------------------------------------------
# TAB 5: Rotate
# ----------------------------------------------------------------------

class RotateTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app

        body = card(self)
        ttk.Label(body, text="Rotate Pages", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Rotate all pages or a selected range.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        file_picker_row(form, "Input PDF:", self.input_var, self.browse_input, 0)
        self.output_var = tk.StringVar()
        file_picker_row(form, "Output PDF:", self.output_var, self.browse_output, 1)

        ttk.Label(body, text="Rotation angle:", style="Surface.TLabel").pack(anchor="w", pady=(16, 4))
        self.angle_var = tk.StringVar(value="90")
        angle_frame = ttk.Frame(body, style="Surface.TFrame")
        angle_frame.pack(anchor="w")
        for angle in ("90", "180", "270"):
            ttk.Radiobutton(angle_frame, text=f"{angle}°", variable=self.angle_var,
                             value=angle).pack(side="left", padx=(0, 12))

        ttk.Label(body, text="Pages (leave blank for all, or e.g. 1-3,5):",
                  style="Surface.TLabel").pack(anchor="w", pady=(16, 4))
        self.pages_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.pages_var, width=50).pack(anchor="w")

        ttk.Button(body, text="Rotate Pages", style="Accent.TButton",
                   command=self.rotate).pack(anchor="e", pady=(20, 0))

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)
            if not self.output_var.get():
                base, ext = os.path.splitext(p)
                self.output_var.set(f"{base}_rotated{ext}")

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def rotate(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()
        angle = int(self.angle_var.get())
        pages_text = self.pages_var.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not out:
            messagebox.showerror("Error", "Please choose an output file.")
            return

        def task():
            self.app.set_status("Rotating pages…")
            reader = PdfReader(src)
            total_pages = len(reader.pages)
            target_pages = (set(parse_page_ranges(pages_text, total_pages))
                             if pages_text else set(range(total_pages)))
            writer = PdfWriter()
            for i, page in enumerate(reader.pages):
                if i in target_pages:
                    page.rotate(angle)
                writer.add_page(page)
                self.app.set_progress(int((i + 1) / total_pages * 100), 100)
            with open(out, "wb") as fp:
                writer.write(fp)
            return len(target_pages)

        self.app.run_task(task, on_success=lambda n: messagebox.showinfo(
            "Success", f"Rotated {n} page(s) by {angle}°.\nSaved to:\n{out}"))


# ----------------------------------------------------------------------
# TAB 6: Password Protect
# ----------------------------------------------------------------------

class ProtectTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app

        body = card(self)
        ttk.Label(body, text="Password Protect PDF", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Encrypt a PDF so it requires a password to open.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        file_picker_row(form, "Input PDF:", self.input_var, self.browse_input, 0)
        self.output_var = tk.StringVar()
        file_picker_row(form, "Output PDF:", self.output_var, self.browse_output, 1)

        ttk.Label(body, text="Password:", style="Surface.TLabel").pack(anchor="w", pady=(16, 4))
        self.pw_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.pw_var, show="•", width=30).pack(anchor="w")

        ttk.Label(body, text="Confirm Password:", style="Surface.TLabel").pack(anchor="w", pady=(10, 4))
        self.pw2_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.pw2_var, show="•", width=30).pack(anchor="w")

        ttk.Button(body, text="Protect PDF", style="Accent.TButton",
                   command=self.protect).pack(anchor="e", pady=(20, 0))

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)
            if not self.output_var.get():
                base, ext = os.path.splitext(p)
                self.output_var.set(f"{base}_protected{ext}")

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def protect(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()
        pw = self.pw_var.get()
        pw2 = self.pw2_var.get()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not out:
            messagebox.showerror("Error", "Please choose an output file.")
            return
        if not pw:
            messagebox.showerror("Error", "Please enter a password.")
            return
        if pw != pw2:
            messagebox.showerror("Error", "Passwords do not match.")
            return

        def task():
            self.app.set_status("Encrypting PDF…")
            self.app.set_progress(30)
            reader = PdfReader(src)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            self.app.set_progress(60)
            writer.encrypt(pw)
            self.app.set_progress(85)
            with open(out, "wb") as fp:
                writer.write(fp)
            return out

        self.app.run_task(task, on_success=lambda o: messagebox.showinfo(
            "Success", f"Password-protected PDF saved to:\n{o}"))


# ----------------------------------------------------------------------
# TAB 7: Unlock
# ----------------------------------------------------------------------

class UnlockTab(ttk.Frame):
    def __init__(self, notebook, app):
        super().__init__(notebook)
        self.app = app

        body = card(self)
        ttk.Label(body, text="Unlock (Decrypt) PDF", style="SubHeader.TLabel").pack(anchor="w")
        ttk.Label(body, text="Remove password protection from a PDF you have access to.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(body, style="Surface.TFrame")
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.input_var = tk.StringVar()
        file_picker_row(form, "Input PDF:", self.input_var, self.browse_input, 0)
        self.output_var = tk.StringVar()
        file_picker_row(form, "Output PDF:", self.output_var, self.browse_output, 1)

        ttk.Label(body, text="Current Password:", style="Surface.TLabel").pack(anchor="w", pady=(16, 4))
        self.pw_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.pw_var, show="•", width=30).pack(anchor="w")

        ttk.Button(body, text="Unlock PDF", style="Accent.TButton",
                   command=self.unlock).pack(anchor="e", pady=(20, 0))

    def browse_input(self):
        p = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if p:
            self.input_var.set(p)
            if not self.output_var.get():
                base, ext = os.path.splitext(p)
                self.output_var.set(f"{base}_unlocked{ext}")

    def browse_output(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf",
                                          filetypes=[("PDF files", "*.pdf")])
        if p:
            self.output_var.set(p)

    def unlock(self):
        src = self.input_var.get().strip()
        out = self.output_var.get().strip()
        pw = self.pw_var.get()
        if not src or not os.path.isfile(src):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not out:
            messagebox.showerror("Error", "Please choose an output file.")
            return

        def task():
            self.app.set_status("Unlocking PDF…")
            self.app.set_progress(30)
            reader = PdfReader(src)
            if reader.is_encrypted:
                result = reader.decrypt(pw)
                if result == 0:
                    raise ValueError("Incorrect password.")
            self.app.set_progress(60)
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            self.app.set_progress(85)
            with open(out, "wb") as fp:
                writer.write(fp)
            return out

        self.app.run_task(task, on_success=lambda o: messagebox.showinfo(
            "Success", f"Unlocked PDF saved to:\n{o}"))


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

if __name__ == "__main__":
    app = PDFToolkitApp()
    app.mainloop()
