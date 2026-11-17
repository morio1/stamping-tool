"""Cert Stamp Pro desktop application. Run with python app.py."""
import copy
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pymupdf as fitz
from PIL import Image, ImageTk

from stamper import (Placement, apply_stamp, batch_export, discover, inspect,
                     check_area, page_bounds, selected_pages, stamp_bytes)
from archives import import_archives, package_results
from dataclasses import asdict


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cert Stamp Pro | Certificate workspace")
        self.geometry("1280x860")
        self.minsize(1000, 700)
        self.configure(bg="#edf2f7")
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.certificates = []
        self.current = None
        self.page_index = 0
        self.source = tk.StringVar()
        self.source_display = tk.StringVar()
        self.import_session = None
        self.zip_output = tk.BooleanVar(value=True)
        self.output = tk.StringVar()
        self.stamp = tk.StringVar()
        self.signature = tk.StringVar()
        self.operation = tk.StringVar(value="stamp")
        self.field_label = tk.StringVar()
        self.require_approval = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Choose a certificate folder and your stamp image to begin.")
        self.mode = tk.StringVar(value="first")
        self.opacity = tk.DoubleVar(value=0.90)
        self.white = tk.BooleanVar(value=False)
        self.ocr = tk.BooleanVar(value=False)
        self.overlay = tk.BooleanVar(value=True)
        self.photo = None
        self.render_context = None
        self.start_point = None
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", padding=7)
        style.configure("TLabel", background="#edf2f7", font=("Segoe UI", 10))
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        header = tk.Frame(self, bg="#102a43", padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text="CERT STAMP PRO", bg="#102a43", fg="white",
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(header, text="Select a folder. Check the placement. Export stamped copies.",
                 bg="#102a43", fg="#b9d9ed", font=("Segoe UI", 11)).pack(anchor="w")
        settings = ttk.Frame(self, padding=14)
        settings.pack(fill="x")
        self.controls = []
        for row, (label, var, command) in enumerate([
            ("Folder / ZIP batch", self.source_display, self.choose_source),
            ("Output folder", self.output, self.choose_output),
            ("Stamp PNG / JPG", self.stamp, self.choose_stamp),
            ("Signature PNG / JPG", self.signature, self.choose_signature)]):
            ttk.Label(settings, text=label, width=20).grid(row=row, column=0, sticky="w")
            entry = ttk.Entry(settings, textvariable=var, state="readonly")
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            button = ttk.Button(settings, text="Browse…", command=command)
            button.grid(row=row, column=2, padx=8)
            self.controls.append(button)
        settings.columnconfigure(1, weight=1)
        zip_button = ttk.Button(settings, text="Import ZIP files…", command=self.choose_zip)
        zip_button.grid(row=0, column=3)
        self.controls.append(zip_button)
        module_bar = ttk.Frame(self, padding=(14, 0, 14, 8))
        module_bar.pack(fill="x")
        ttk.Label(module_bar, text="Module:").pack(side="left")
        modules = ttk.Combobox(module_bar, textvariable=self.operation, values=("stamp", "signature"),
                               state="readonly", width=12)
        modules.pack(side="left", padx=8)
        modules.bind("<<ComboboxSelected>>", lambda event: self.reset_analysis())
        self.controls.append(modules)
        ttk.Label(module_bar, text="Field label / signatory role (optional):").pack(side="left")
        label_entry = ttk.Entry(module_bar, textvariable=self.field_label, width=28)
        label_entry.pack(side="left", padx=8)
        label_entry.bind("<KeyRelease>", lambda event: self.reset_analysis())
        self.controls.append(label_entry)
        ttk.Label(module_bar, text="Examples: Official Seal, Principal, Registrar").pack(side="left")
        options = ttk.Frame(self, padding=(14, 0, 14, 10))
        options.pack(fill="x")
        ttk.Label(options, text="Target pages:").pack(side="left")
        combo = ttk.Combobox(options, textvariable=self.mode, values=("first", "last", "all"),
                             width=8, state="readonly")
        combo.pack(side="left", padx=7)
        combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_states())
        self.controls.append(combo)
        for text, var in [("Remove white image background", self.white), ("OCR scanned pages", self.ocr)]:
            control = ttk.Checkbutton(options, text=text, variable=var, command=self.preview)
            control.pack(side="left", padx=10)
            self.controls.append(control)
        ttk.Label(options, text="Ink strength").pack(side="left", padx=8)
        control = ttk.Scale(options, from_=0.2, to=1, variable=self.opacity,
                            command=lambda value: self.schedule_preview())
        control.pack(side="left")
        self.controls.append(control)
        approval_bar = ttk.Frame(self, padding=(14, 0, 14, 8))
        approval_bar.pack(fill="x")
        review_option = ttk.Checkbutton(approval_bar, text="Require approval for each selected page",
                                       variable=self.require_approval, command=self.refresh_states)
        review_option.pack(side="left", padx=8)
        self.controls.append(review_option)
        actions = ttk.Frame(self, padding=(14, 0, 14, 10))
        actions.pack(fill="x")
        self.scan_button = ttk.Button(actions, text="1   Scan folder", command=self.scan)
        self.scan_button.pack(side="left")
        self.export_button = ttk.Button(actions, text="2   Export ready certificates", command=self.export)
        self.export_button.pack(side="left", padx=8)
        self.controls.extend([self.scan_button, self.export_button])
        review_button = ttk.Button(actions, text="Save review report", command=self.save_review)
        review_button.pack(side="left", padx=5)
        self.controls.append(review_button)
        zip_check = ttk.Checkbutton(actions, text="Also create ZIP", variable=self.zip_output)
        zip_check.pack(side="left", padx=5)
        self.controls.append(zip_check)
        ttk.Button(actions, text="Cancel job", command=self.cancel.set).pack(side="left")
        self.progress = ttk.Progressbar(actions, mode="determinate")
        self.progress.pack(side="right", fill="x", expand=True, padx=14)
        pane = ttk.Panedwindow(self, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=14)
        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=5)
        self.tree = ttk.Treeview(left, columns=("state",), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Certificates / regional folders")
        self.tree.heading("state", text="Check")
        self.tree.column("#0", width=260)
        self.tree.column("state", width=100)
        scrollbar = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        self.tree.tag_configure("review", foreground="#a65a00")
        self.tree.tag_configure("ready", foreground="#17785b")
        self.tree.tag_configure("occupied", foreground="#b42318")
        self.tree.tag_configure("stamped", foreground="#536579")
        self.tree.tag_configure("signed", foreground="#536579")
        bar = ttk.Frame(right)
        bar.pack(fill="x")
        ttk.Button(bar, text="◀ PDF", command=lambda: self.turn_certificate(-1)).pack(side="left")
        ttk.Button(bar, text="PDF ▶", command=lambda: self.turn_certificate(1)).pack(side="left")
        ttk.Button(bar, text="◀ Page", command=lambda: self.turn(-1)).pack(side="left")
        ttk.Button(bar, text="Page ▶", command=lambda: self.turn(1)).pack(side="left")
        bar = ttk.Frame(right)
        bar.pack(fill="x", pady=(4, 0))
        ttk.Checkbutton(bar, text="Show image preview", variable=self.overlay,
                        command=self.preview).pack(side="left", padx=8)
        ttk.Button(bar, text="Approve this area", command=self.approve).pack(side="right")
        ttk.Button(bar, text="Recheck page", command=self.recheck).pack(side="right")
        self.detail = tk.StringVar(value="Select a certificate to view every page.")
        ttk.Label(right, textvariable=self.detail, wraplength=690).pack(fill="x", pady=8)
        self.canvas = tk.Canvas(right, bg="#d6e1eb", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<B1-Motion>", self.drag_move)
        self.canvas.bind("<ButtonRelease-1>", self.drag_end)
        self.canvas.bind("<Configure>", lambda event: self.schedule_preview())
        ttk.Label(self, text="Draw a rectangle in the preview to set a custom image area. Amber areas require review.",
                  padding=(14, 8)).pack(anchor="w")
        ttk.Label(self, textvariable=self.status, padding=(14, 5)).pack(fill="x")
        self.after(100, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        if self.busy:
            self.cancel.set()
            self.status.set("Cancelling… wait for the current file to finish before closing.")
        else:
            if self.import_session:
                self.import_session.cleanup()
            self.destroy()

    def choose_source(self):
        path = filedialog.askdirectory(title="Choose unstamped certificates")
        if path:
            if self.import_session:
                self.import_session.cleanup()
                self.import_session = None
            self.source.set(str(Path(path).resolve()))
            self.source_display.set(path)
            self.output.set(str(Path(path).parent / (Path(path).name + " - stamped")))
            self.certificates = []
            self.current = None
            self.tree.delete(*self.tree.get_children())
            self.canvas.delete("all")

    def choose_zip(self):
        paths = filedialog.askopenfilenames(title="Choose certificate ZIP batches",
                                           filetypes=[("ZIP archives", "*.zip")])
        if not paths:
            return
        ocr = self.ocr.get()
        operation, label = self.operation.get(), self.field_label.get().strip()
        output = str(Path(paths[0]).parent / (Path(paths[0]).stem + " - stamped"))
        def run():
            session, root = import_archives(paths,
                lambda a, b, c: self.events.put(("progress", (a, b, c))), self.cancel.is_set)
            self.events.put(("import", (session, root, paths, output)))
            self.scan_files(str(root), output, ocr, operation, label)
        self.work(run)

    def scan_files(self, root, output, ocr, operation="stamp", label=None):
        files = discover(root, output)
        results = []
        for index, path in enumerate(files):
            if self.cancel.is_set():
                break
            results.append(inspect(path, ocr, operation, label))
            self.events.put(("progress", (index + 1, len(files), f"Checking {path.name}")))
        self.events.put(("scan", (results, len(files))))

    def save_review(self):
        if not self.certificates:
            messagebox.showinfo("Scan first", "Scan a folder or import certificate ZIP files first.")
            return
        path = filedialog.asksaveasfilename(title="Save certificate review", defaultextension=".json",
                                          initialfile="certificate-review.json", filetypes=[("JSON report", "*.json")])
        if path:
            try:
                rows = [{"file": str(c.path.resolve().relative_to(Path(self.source.get()).resolve())),
                         "operation": c.operation,
                         "source_sha256": c.digest, "error": c.error,
                         "pages": [asdict(p) for p in c.pages]} for c in self.certificates]
                Path(path).write_text(json.dumps(rows, indent=2), encoding="utf-8")
                self.status.set(f"Review saved: {path}")
            except OSError as exc:
                messagebox.showerror("Could not save review", str(exc))

    def choose_output(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output.set(path)

    def choose_stamp(self):
        path = filedialog.askopenfilename(filetypes=[("Stamp images", "*.png *.jpg *.jpeg")])
        if path:
            self.stamp.set(path)
            self.preview()

    def choose_signature(self):
        path = filedialog.askopenfilename(title="Select signature image",
                                         filetypes=[("Signature images", "*.png *.jpg *.jpeg")])
        if path:
            self.signature.set(path)
            self.preview()

    def active_image(self):
        return self.signature.get() if self.operation.get() == "signature" else self.stamp.get()

    def reset_analysis(self):
        if self.busy:
            return
        self.current = None
        self.certificates = []
        self.tree.delete(*self.tree.get_children())
        self.canvas.delete("all")
        self.detail.set("Field settings changed. Scan again to check this module's placement.")
        self.status.set("Choose the matching image and scan again. Signature mode applies a visible image only.")

    def turn_certificate(self, amount):
        items = self.tree.get_children()
        if not items:
            return
        selected = self.tree.selection()
        index = items.index(selected[0]) if selected else 0
        item = items[max(0, min(len(items) - 1, index + amount))]
        self.tree.selection_set(item)
        self.tree.see(item)
        self.select()

    def set_busy(self, value):
        self.busy = value
        for control in self.controls:
            if isinstance(control, ttk.Combobox):
                control.configure(state="disabled" if value else "readonly")
            else:
                control.configure(state="disabled" if value else "normal")

    def work(self, function):
        if self.busy:
            return
        self.cancel.clear()
        self.set_busy(True)
        def run():
            try:
                function()
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("done", None))
        threading.Thread(target=run, daemon=True).start()

    def scan(self):
        if not self.source.get():
            messagebox.showinfo("Choose folder", "Choose the unstamped certificate folder first.")
            return
        root, output, ocr = self.source.get(), self.output.get(), self.ocr.get()
        operation, label = self.operation.get(), self.field_label.get().strip()
        def run():
            self.scan_files(root, output, ocr, operation, label)
        self.work(run)

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "done":
                    self.set_busy(False)
                elif kind == "error":
                    self.status.set(value)
                    messagebox.showerror("Job could not finish", value)
                elif kind == "progress":
                    current, total, message = value
                    self.progress.configure(maximum=max(1, total), value=current)
                    self.status.set(f"{current}/{total} · {message}")
                elif kind == "import":
                    session, root, paths, output = value
                    if self.import_session:
                        self.import_session.cleanup()
                    self.import_session = session
                    self.source.set(str(root))
                    self.source_display.set("; ".join(Path(p).name for p in paths))
                    self.output.set(output)
                    self.current = None
                elif kind == "scan":
                    value, total = value
                    self.certificates = value
                    self.current = None
                    self.tree.delete(*self.tree.get_children())
                    for i, cert in enumerate(value):
                        state = self.certificate_state(cert)
                        self.tree.insert("", "end", iid=str(i), text=str(cert.path.resolve().relative_to(Path(self.source.get()).resolve())),
                                         values=(state,), tags=(state,))
                    counts = {state: sum(self.certificate_state(c) == state for c in value)
                              for state in ("ready", "review", "occupied", "stamped", "signed", "error")}
                    self.status.set(f"Checked {len(value)}/{total} PDFs · " + " · ".join(f"{k}: {v}" for k, v in counts.items())
                                    + (" · SCAN CANCELLED" if len(value) < total else ""))
                    if value:
                        self.tree.selection_set("0")
                elif kind == "export":
                    audit, report, archive = value
                    count = sum(r["status"] in ("stamped", "signed") for r in report)
                    self.status.set(f"Exported {count}/{len(report)} PDFs. Report: {audit}")
                    messagebox.showinfo("Export complete", f"Processed: {count}\nSkipped / errors / cancelled: {len(report) - count}\n\nReport: {audit}"
                                        + (f"\n\nZIP: {archive}" if archive else ""))
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def select(self, event=None):
        selected = self.tree.selection()
        if selected:
            self.current = self.certificates[int(selected[0])]
            self.page_index = 0
            self.preview()

    def certificate_state(self, cert):
        if cert.error:
            return "error"
        states = [cert.pages[i].status for i in selected_pages(cert, self.mode.get())]
        if all(s in ("ready", "approved") for s in states):
            if self.require_approval.get() and any(s == "ready" for s in states):
                return "review"
            return "ready"
        if all(s == "stamped" for s in states):
            return "signed" if cert.operation == "signature" else "stamped"
        if any(s == "occupied" for s in states):
            return "occupied"
        return "review"

    def refresh_states(self):
        for i, cert in enumerate(self.certificates):
            state = self.certificate_state(cert)
            self.tree.item(str(i), values=(state,), tags=(state,))

    def turn(self, amount):
        if self.current and self.current.pages:
            self.page_index = max(0, min(len(self.current.pages) - 1, self.page_index + amount))
            self.preview()

    def schedule_preview(self):
        if hasattr(self, "preview_timer"):
            self.after_cancel(self.preview_timer)
        self.preview_timer = self.after(200, self.preview)

    def preview(self):
        self.canvas.delete("all")
        self.render_context = None
        if not self.current:
            return
        if self.current.error:
            self.detail.set(self.current.error)
            return
        if not self.current.pages:
            self.detail.set("No readable pages.")
            return
        self.page_index = min(self.page_index, len(self.current.pages) - 1)
        placement = self.current.pages[self.page_index]
        try:
            with fitz.open(self.current.path) as doc:
                page = doc[self.page_index]
                if (self.overlay.get() and self.active_image() and placement.rect
                        and placement.status not in ("occupied", "stamped")):
                    apply_stamp(page, placement, stamp_bytes(self.active_image(), self.opacity.get(), self.white.get()))
                w, h = max(100, self.canvas.winfo_width()), max(100, self.canvas.winfo_height())
                scale = min((w - 20) / page.rect.width, (h - 20) / page.rect.height)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                self.photo = ImageTk.PhotoImage(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
                ox, oy = (w - pix.width) / 2, (h - pix.height) / 2
                self.canvas.create_image(ox, oy, anchor="nw", image=self.photo)
                self.render_context = (scale, ox, oy, page.derotation_matrix, page_bounds(page))
                if placement.rect:
                    r = fitz.Rect(placement.rect) * page.rotation_matrix
                    self.canvas.create_rectangle(ox + r.x0 * scale, oy + r.y0 * scale,
                                                 ox + r.x1 * scale, oy + r.y1 * scale,
                                                 outline=("#b42318" if placement.status == "occupied" else
                                                          "#0c9b75" if placement.status in ("ready", "approved") else "#ec940f"), width=2)
            self.detail.set(f"Page {self.page_index + 1}/{len(self.current.pages)} · {placement.status.upper()} · {placement.reason}")
        except Exception as exc:
            self.detail.set(f"Preview unavailable: {exc}")

    def drag_start(self, event):
        if (not self.busy and self.render_context and self.current
                and self.current.pages[self.page_index].status != "stamped"):
            self.start_point = (event.x, event.y)

    def drag_move(self, event):
        if self.start_point:
            self.canvas.delete("drag")
            self.canvas.create_rectangle(*self.start_point, event.x, event.y, outline="#ec940f", width=2, tags="drag")

    def drag_end(self, event):
        if self.busy or not self.start_point or not self.render_context:
            self.start_point = None
            return
        x, y = self.start_point
        self.start_point = None
        scale, ox, oy, inverse, bounds = self.render_context
        rect = fitz.Rect(min(x, event.x), min(y, event.y), max(x, event.x), max(y, event.y))
        rect = fitz.Rect((rect.x0 - ox) / scale, (rect.y0 - oy) / scale,
                         (rect.x1 - ox) / scale, (rect.y1 - oy) / scale) * inverse
        rect &= bounds
        if rect.width >= 18 and rect.height >= 18:
            with fitz.open(self.current.path) as doc:
                checked = check_area(doc[self.page_index], rect, ignore_underline=self.current.operation == "signature")
            checked.kind = self.current.operation
            if checked.status == "ready":
                checked.status, checked.reason = "review", "Custom area. Inspect the preview, then approve."
            self.current.pages[self.page_index] = checked
        self.preview()
        self.refresh_states()

    def approve(self):
        if self.busy or not self.current or not self.current.pages:
            return
        p = self.current.pages[self.page_index]
        if p.status == "occupied":
            messagebox.showinfo("Existing ink detected", "This area may already be stamped. It will be skipped. Draw a clear area only if the detected box is wrong.")
            return
        if p.rect and p.status != "stamped":
            p.status, p.reason = "approved", "Placement approved in preview."
            self.preview()
            self.refresh_states()

    def recheck(self):
        if not self.busy and self.current:
            updated = inspect(self.current.path, self.ocr.get(), self.operation.get(), self.field_label.get().strip())
            self.current.digest, self.current.pages, self.current.error = updated.digest, updated.pages, updated.error
            self.preview()
            self.refresh_states()

    def export(self):
        if not self.certificates or not self.active_image() or not self.output.get():
            messagebox.showinfo("Complete setup", "Scan the folder, choose the image for the selected module, and choose an output folder.")
            return
        try:
            image = stamp_bytes(self.active_image(), self.opacity.get(), self.white.get())
        except Exception as exc:
            messagebox.showerror("Stamp image", str(exc))
            return
        source, output, mode = self.source.get(), self.output.get(), self.mode.get()
        create_zip = self.zip_output.get()
        certificates = copy.deepcopy(self.certificates)
        if any(c.operation != self.operation.get() for c in certificates):
            messagebox.showinfo("Scan again", "The selected module changed. Scan again before exporting.")
            return
        if self.require_approval.get():
            for cert in certificates:
                for p in cert.pages:
                    if p.status == "ready":
                        p.status, p.reason = "review", "Preview approval is required for this page before export."
        def run():
            result = batch_export(certificates, source, output, image, mode,
                                  lambda a, b, c: self.events.put(("progress", (a, b, c))), self.cancel.is_set)
            audit, report = result
            archive = None
            if create_zip and not self.cancel.is_set():
                archive = package_results(output, report, audit,
                    progress=lambda a, b, c: self.events.put(("progress", (a, b, c))), cancelled=self.cancel.is_set)
            self.events.put(("export", (audit, report, archive)))
        self.work(run)


if __name__ == "__main__":
    App().mainloop()
