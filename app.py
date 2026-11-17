"""Cert Stamp Pro desktop application. Run with python app.py."""
import copy
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pymupdf as fitz
from PIL import Image, ImageTk

from stamper import (Placement, apply_stamp, batch_export, discover, inspect,
                     page_bounds, selected_pages, stamp_bytes)


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
        self.output = tk.StringVar()
        self.stamp = tk.StringVar()
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
            ("Certificate folder", self.source, self.choose_source),
            ("Output folder", self.output, self.choose_output),
            ("Stamp PNG / JPG", self.stamp, self.choose_stamp)]):
            ttk.Label(settings, text=label, width=20).grid(row=row, column=0, sticky="w")
            entry = ttk.Entry(settings, textvariable=var, state="readonly")
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            button = ttk.Button(settings, text="Browse…", command=command)
            button.grid(row=row, column=2, padx=8)
            self.controls.append(button)
        settings.columnconfigure(1, weight=1)
        options = ttk.Frame(self, padding=(14, 0, 14, 10))
        options.pack(fill="x")
        ttk.Label(options, text="Stamp pages:").pack(side="left")
        combo = ttk.Combobox(options, textvariable=self.mode, values=("first", "last", "all"),
                             width=8, state="readonly")
        combo.pack(side="left", padx=7)
        combo.bind("<<ComboboxSelected>>", lambda event: self.refresh_states())
        self.controls.append(combo)
        for text, var in [("Remove white stamp background", self.white), ("OCR scanned pages", self.ocr)]:
            control = ttk.Checkbutton(options, text=text, variable=var, command=self.preview)
            control.pack(side="left", padx=10)
            self.controls.append(control)
        ttk.Label(options, text="Ink strength").pack(side="left", padx=8)
        control = ttk.Scale(options, from_=0.2, to=1, variable=self.opacity,
                            command=lambda value: self.schedule_preview())
        control.pack(side="left")
        self.controls.append(control)
        actions = ttk.Frame(self, padding=(14, 0, 14, 10))
        actions.pack(fill="x")
        self.scan_button = ttk.Button(actions, text="1   Scan folder", command=self.scan)
        self.scan_button.pack(side="left")
        self.export_button = ttk.Button(actions, text="2   Stamp ready certificates", command=self.export)
        self.export_button.pack(side="left", padx=8)
        self.controls.extend([self.scan_button, self.export_button])
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
        bar = ttk.Frame(right)
        bar.pack(fill="x")
        ttk.Button(bar, text="◀ Page", command=lambda: self.turn(-1)).pack(side="left")
        ttk.Button(bar, text="Page ▶", command=lambda: self.turn(1)).pack(side="left")
        ttk.Checkbutton(bar, text="Show stamp preview", variable=self.overlay,
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
        ttk.Label(self, text="Draw a rectangle in the preview to set a custom stamp area. Amber areas require approval.",
                  padding=(14, 8)).pack(anchor="w")
        ttk.Label(self, textvariable=self.status, padding=(14, 5)).pack(fill="x")
        self.after(100, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def close(self):
        if self.busy:
            self.cancel.set()
            self.status.set("Cancelling… wait for the current file to finish before closing.")
        else:
            self.destroy()

    def choose_source(self):
        path = filedialog.askdirectory(title="Choose unstamped certificates")
        if path:
            self.source.set(path)
            self.output.set(str(Path(path).parent / (Path(path).name + " - stamped")))
            self.certificates = []
            self.current = None
            self.tree.delete(*self.tree.get_children())
            self.canvas.delete("all")

    def choose_output(self):
        path = filedialog.askdirectory(title="Choose output folder")
        if path:
            self.output.set(path)

    def choose_stamp(self):
        path = filedialog.askopenfilename(filetypes=[("Stamp images", "*.png *.jpg *.jpeg")])
        if path:
            self.stamp.set(path)
            self.preview()

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
        def run():
            files = discover(root, output)
            results = []
            for index, path in enumerate(files):
                if self.cancel.is_set():
                    break
                results.append(inspect(path, ocr))
                self.events.put(("progress", (index + 1, len(files), f"Checking {path.name}")))
            self.events.put(("scan", results))
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
                elif kind == "scan":
                    self.certificates = value
                    self.current = None
                    self.tree.delete(*self.tree.get_children())
                    for i, cert in enumerate(value):
                        state = self.certificate_state(cert)
                        self.tree.insert("", "end", iid=str(i), text=str(cert.path.relative_to(Path(self.source.get()))),
                                         values=(state,), tags=(state,))
                    self.status.set(f"Checked {len(value)} PDFs. Select any certificate to preview or adjust its pages.")
                    if value:
                        self.tree.selection_set("0")
                elif kind == "export":
                    audit, report = value
                    count = sum(r["status"] == "stamped" for r in report)
                    self.status.set(f"Exported {count}/{len(report)} PDFs. Report: {audit}")
                    messagebox.showinfo("Export complete", f"Stamped: {count}\nSkipped / errors / cancelled: {len(report) - count}\n\nReport: {audit}")
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
            return "ready"
        if all(s == "stamped" for s in states):
            return "stamped"
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
        placement = self.current.pages[self.page_index]
        try:
            with fitz.open(self.current.path) as doc:
                page = doc[self.page_index]
                if self.overlay.get() and self.stamp.get() and placement.rect:
                    apply_stamp(page, placement, stamp_bytes(self.stamp.get(), self.opacity.get(), self.white.get()))
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
                                                 outline="#0c9b75" if placement.status in ("ready", "approved") else "#ec940f", width=2)
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
            self.current.pages[self.page_index] = Placement(tuple(rect), "review", "Custom area. Inspect the preview, then approve.")
        self.preview()
        self.refresh_states()

    def approve(self):
        if self.busy or not self.current or not self.current.pages:
            return
        p = self.current.pages[self.page_index]
        if p.rect and p.status != "stamped":
            p.status, p.reason = "approved", "Placement approved in preview."
            self.preview()
            self.refresh_states()

    def recheck(self):
        if not self.busy and self.current:
            updated = inspect(self.current.path, self.ocr.get())
            self.current.digest, self.current.pages, self.current.error = updated.digest, updated.pages, updated.error
            self.preview()
            self.refresh_states()

    def export(self):
        if not self.certificates or not self.stamp.get() or not self.output.get():
            messagebox.showinfo("Complete setup", "Scan the folder, choose your stamp image and choose an output folder.")
            return
        try:
            image = stamp_bytes(self.stamp.get(), self.opacity.get(), self.white.get())
        except Exception as exc:
            messagebox.showerror("Stamp image", str(exc))
            return
        source, output, mode = self.source.get(), self.output.get(), self.mode.get()
        certificates = copy.deepcopy(self.certificates)
        def run():
            result = batch_export(certificates, source, output, image, mode,
                                  lambda a, b, c: self.events.put(("progress", (a, b, c))), self.cancel.is_set)
            self.events.put(("export", result))
        self.work(run)


if __name__ == "__main__":
    App().mainloop()
