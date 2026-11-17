"""Gmail delivery workspace; sending starts only from its explicit Send button."""
import csv
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pymupdf as fitz
from PIL import Image, ImageTk
from email_delivery import load_plan, make_message, send_batch


class EmailWindow(tk.Toplevel):
    def __init__(self, parent, output="", audit=""):
        super().__init__(parent)
        self.title("Cert Stamp Pro | Gmail certificate delivery")
        self.geometry("1100x850")
        self.plan = []
        self.busy = False
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.output = tk.StringVar(value=output)
        self.audit = tk.StringVar(value=audit)
        self.mapping = tk.StringVar()
        self.sender = tk.StringVar()
        self.password = tk.StringVar()
        self.subject = tk.StringVar(value="Your certificate")
        self.limit = tk.IntVar(value=100)
        self.reviewed = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Load successful output PDFs and their audit, then map recipients. No emails are sent by loading or previewing.")
        form = ttk.Frame(self, padding=12)
        form.pack(fill="x")
        for row, (label, variable, action) in enumerate([
            ("Processed PDF folder", self.output, self.pick_output),
            ("Export audit JSON", self.audit, self.pick_audit),
            ("Recipient CSV", self.mapping, self.pick_mapping)]):
            ttk.Label(form, text=label, width=22).grid(row=row, column=0, sticky="w")
            ttk.Entry(form, textvariable=variable, state="readonly").grid(row=row, column=1, sticky="ew", pady=3)
            ttk.Button(form, text="Browse", command=action).grid(row=row, column=2, padx=5)
        form.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate([("Gmail / Workspace sender", self.sender),
                                                ("Google app password", self.password), ("Subject", self.subject)], 3):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(form, textvariable=variable, show="*" if variable is self.password else "").grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Label(form, text="Max messages this run").grid(row=6, column=0, sticky="w")
        ttk.Spinbox(form, from_=1, to=1000, textvariable=self.limit, width=8).grid(row=6, column=1, sticky="w")
        ttk.Label(self, text="Gmail quotas apply. App passwords require eligible Google accounts with 2-Step Verification. Passwords are not saved.", wraplength=1000).pack(anchor="w", padx=12)
        self.body = tk.Text(self, height=5, wrap="word")
        self.body.pack(fill="x", padx=12, pady=6)
        self.body.insert("1.0", "Dear {name},\n\nPlease find your certificate attached.\n\nKind regards")
        self.body.bind("<KeyRelease>", lambda event: self.reviewed.set(False))
        self.sender.trace_add("write", lambda *args: self.reviewed.set(False))
        self.subject.trace_add("write", lambda *args: self.reviewed.set(False))
        controls = ttk.Frame(self, padding=(12, 4))
        controls.pack(fill="x")
        ttk.Button(controls, text="Create recipient CSV template", command=self.csv_template).pack(side="left")
        ttk.Button(controls, text="Load & validate plan", command=self.load).pack(side="left", padx=7)
        ttk.Button(controls, text="Preview attached PDF", command=self.preview_pdf).pack(side="left")
        self.tree = ttk.Treeview(self, columns=("email", "file"), show="headings", height=7)
        self.tree.heading("email", text="Recipient email")
        self.tree.heading("file", text="Exactly one certificate attached")
        self.tree.column("email", width=300)
        self.tree.column("file", width=650)
        self.tree.pack(fill="both", expand=True, padx=12)
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.preview_message())
        self.preview = tk.Text(self, height=6, wrap="word", state="disabled")
        self.preview.pack(fill="x", padx=12, pady=6)
        controls = ttk.Frame(self, padding=12)
        controls.pack(fill="x")
        ttk.Checkbutton(controls, text="I reviewed recipients, attachments and message content", variable=self.reviewed).pack(side="left")
        ttk.Button(controls, text="Send reviewed batch via Gmail", command=self.send).pack(side="right")
        ttk.Button(controls, text="Stop", command=self.cancel.set).pack(side="right", padx=8)
        ttk.Label(self, textvariable=self.status, wraplength=1000, padding=12).pack(fill="x")
        self.after(150, self.poll)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def clear_plan(self):
        self.plan = []
        self.reviewed.set(False)
        self.tree.delete(*self.tree.get_children())

    def pick_output(self):
        if self.busy: return
        path = filedialog.askdirectory(parent=self)
        if path: self.output.set(path); self.clear_plan()

    def pick_audit(self):
        if self.busy: return
        path = filedialog.askopenfilename(parent=self, filetypes=[("Export audit", "audit-*.json")])
        if path: self.audit.set(path); self.clear_plan()

    def pick_mapping(self):
        if self.busy: return
        path = filedialog.askopenfilename(parent=self, filetypes=[("Recipient CSV", "*.csv")])
        if path: self.mapping.set(path); self.clear_plan()

    def csv_template(self):
        if self.busy: return
        try:
            rows = json.loads(Path(self.audit.get()).read_text(encoding="utf-8"))
            path = filedialog.asksaveasfilename(parent=self, initialfile="recipients.csv", defaultextension=".csv")
            if not path: return
            with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(["email", "certificate", "recipient_name"])
                for row in rows:
                    if row.get("status") in ("stamped", "signed"):
                        writer.writerow(["", "./" + row["file"].replace("\\", "/"), ""])
            self.status.set("Template saved. Fill each email in Excel, save as CSV, then load and validate it.")
        except Exception as exc:
            messagebox.showerror("CSV template", str(exc), parent=self)

    def load(self):
        if self.busy: return
        self.clear_plan()
        mapping, output, audit = self.mapping.get(), self.output.get(), self.audit.get()
        self.busy = True
        self.cancel.clear()
        def worker():
            try:
                plan = load_plan(mapping, output, audit, cancelled=self.cancel.is_set,
                                 progress=lambda count: self.events.put(("progress", f"Validating recipient/PDF pair {count}")))
                self.events.put(("plan", plan))
            except Exception as exc:
                self.events.put(("error", str(exc)))
            finally:
                self.events.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def selected(self):
        selection = self.tree.selection()
        return self.plan[int(selection[0])] if selection else None

    def preview_message(self):
        item = self.selected()
        if not item: return
        try:
            message = make_message(item, self.sender.get(), self.subject.get(), self.body.get("1.0", "end-1c"))
            text = f"To: {item.email}\nSubject: {message['Subject']}\nAttachment: {item.certificate}\n\n{message.get_body(preferencelist=('plain',)).get_content()}"
        except Exception as exc:
            text = f"Enter the sender and valid templates to preview the message. {exc}"
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def preview_pdf(self):
        item = self.selected()
        if not item: return
        popup = tk.Toplevel(self)
        popup.title(f"Attachment for {item.email} | {item.certificate}")
        canvas = tk.Canvas(popup, width=840, height=620, bg="#d6e1eb")
        canvas.pack()
        index = [0]
        def render(delta=0):
            with fitz.open(item.path) as doc:
                index[0] = max(0, min(len(doc)-1, index[0]+delta))
                page = doc[index[0]]
                scale = min(820/page.rect.width, 600/page.rect.height)
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                popup.photo = ImageTk.PhotoImage(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
                canvas.delete("all")
                canvas.create_image(420, 310, image=popup.photo)
                popup.title(f"{item.email} | Page {index[0]+1}/{len(doc)} | {item.certificate}")
        ttk.Button(popup, text="Previous page", command=lambda: render(-1)).pack(side="left")
        ttk.Button(popup, text="Next page", command=lambda: render(1)).pack(side="right")
        render()

    def send(self):
        if self.busy: return
        if not self.plan or not self.reviewed.get() or not self.password.get():
            messagebox.showinfo("Review required", "Load the plan, review the pairs and message, enter a Google app password and tick the review checkbox.", parent=self)
            return
        try: limit = self.limit.get()
        except tk.TclError: return
        plan, sender, password = self.plan[:], self.sender.get(), self.password.get()
        subject, body, output = self.subject.get(), self.body.get("1.0", "end-1c"), self.output.get()
        self.password.set("")
        self.busy = True
        self.cancel.clear()
        def worker():
            try:
                result = send_batch(plan, sender, password, subject, body, output, reviewed=True, limit=limit,
                                    cancelled=self.cancel.is_set,
                                    progress=lambda a,b,c: self.events.put(("progress", f"{a}/{b}: {c}")))
                self.events.put(("result", result))
            except Exception:
                self.events.put(("error", "Sending stopped. Check Gmail authentication/account policy, connectivity, the local journal and any send lock. No automatic resend is attempted."))
            finally: self.events.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "done": self.busy = False; self.reviewed.set(False)
                elif kind == "progress": self.status.set(value)
                elif kind == "error": self.status.set(value)
                elif kind == "plan":
                    self.plan = value
                    for i, item in enumerate(self.plan):
                        self.tree.insert("", "end", iid=str(i), values=(item.email, item.certificate))
                    self.tree.selection_set("0")
                    self.status.set(f"Validated {len(self.plan)} mappings against successful output hashes. Review the exact recipient/PDF pairs.")
                elif kind == "result":
                    journal, rows = value
                    count = sum(row["status"] == "accepted" for row in rows)
                    self.status.set(f"Accepted by Gmail: {count}. Acceptance is not confirmed delivery. Journal: {journal}")
        except queue.Empty: pass
        self.after(150, self.poll)

    def close(self):
        if self.busy:
            self.cancel.set()
            self.status.set("Stopping after the current message. Wait before closing.")
        else:
            self.password.set("")
            self.destroy()
