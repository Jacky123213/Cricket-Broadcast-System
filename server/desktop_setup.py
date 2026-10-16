"""Native first-run / maintenance UI; no Python install or browser required."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from .app_paths import RESOURCE_ROOT, default_recordings_root
from .install_support import ensure_https, has_saved_data, import_legacy, load_preferences, write_json_atomic


def is_ca_trusted(certificate: Path) -> bool:
    if sys.platform != "win32" or not certificate.exists():
        return False
    from scripts.generate_certificate import load_certificate
    from cryptography.hazmat.primitives import serialization
    import ssl
    expected = load_certificate(certificate).public_bytes(serialization.Encoding.DER)
    return any(cert == expected for cert, encoding, trust in ssl.enum_certificates("ROOT"))


def trust_ca(certificate: Path) -> None:
    # Called only after explicit checkbox + Continue. Current user, not machine.
    subprocess.run(["certutil.exe", "-user", "-addstore", "Root", str(certificate)],
                   check=True, capture_output=True, text=True, timeout=120,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not is_ca_trusted(certificate):
        raise RuntimeError("Windows did not trust this certificate. No trust is assumed.")


def setup_required(settings) -> bool:
    return not load_preferences(settings.data_root).get("setup_complete") or not is_ca_trusted(settings.certificate_dir / "rootCA.crt")


def show_setup(settings, *, _diagnostics: bool = False) -> bool | dict:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    if _diagnostics:
        root.withdraw()
    root.title("Cricket Broadcast System · Setup & certificates")
    width = min(800, root.winfo_screenwidth() - 80)
    height = min(780, root.winfo_screenheight() - 120)
    root.geometry(f"{width}x{height}")
    root.minsize(min(620, width), min(460, height))
    root.configure(bg="#0d110f")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="#0d110f")
    style.configure("TLabel", background="#0d110f", foreground="#edf2e8", font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
    style.configure("Hint.TLabel", foreground="#abb7ac")
    style.configure("TCheckbutton", background="#0d110f", foreground="#edf2e8", font=("Segoe UI", 10))
    style.map("TCheckbutton", background=[("active", "#18211a")])
    style.configure("TButton", font=("Segoe UI", 10), padding=8)
    footer = ttk.Frame(root, padding=(28, 12, 28, 18))
    footer.pack(side="bottom", fill="x")
    scroll_area = ttk.Frame(root)
    scroll_area.pack(fill="both", expand=True)
    canvas = tk.Canvas(scroll_area, background="#0d110f", highlightthickness=0)
    scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    body = ttk.Frame(canvas, padding=28)
    content = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

    def fit_content(event):
        canvas.itemconfigure(content, width=event.width)
        for child in body.winfo_children():
            if child.winfo_class() == "TLabel":
                child.configure(wraplength=max(220, event.width - 56))

    canvas.bind("<Configure>", fit_content)
    root.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(-int(event.delta / 120), "units"))
    preferences = load_preferences(settings.data_root)
    saved = has_saved_data(settings.data_root)
    success = False
    source = tk.StringVar()
    recordings = tk.StringVar(value=preferences.get("recordings_dir", str(default_recordings_root(settings.data_root))))
    approve = tk.BooleanVar(value=False)
    refresh = tk.BooleanVar(value=False)

    def label(text, *, title=False, hint=False, gap=6):
        ttk.Label(body, text=text, wraplength=690, style="Title.TLabel" if title else "Hint.TLabel" if hint else "TLabel").pack(anchor="w", pady=(0, gap))

    def picker(variable, title):
        row = ttk.Frame(body)
        row.pack(fill="x", pady=(0, 6))
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True)

        def choose():
            selected = filedialog.askdirectory(parent=root, title=title)
            if selected:
                variable.set(selected)

        button = ttk.Button(row, text="Choose folder…", command=choose)
        button.pack(side="left", padx=(8, 0))
        return entry, button

    label("Make this PC match-ready", title=True)
    label("Setup & certificates · installer test build", hint=True, gap=16)
    label("Saved matches, logos, logs and certificates stay here:")
    label(str(settings.data_root), hint=True, gap=16)
    label("Import an existing .bat installation (optional)")
    source_entry, import_button = picker(source, "Select the old app folder containing data / storage / certs")
    if saved:
        source_entry.configure(state="disabled")
        import_button.configure(state="disabled")
        label("Saved data already exists. Import is disabled to prevent overwriting it.", hint=True, gap=14)
    else:
        label("Leave blank for fresh setup. Import copies recognised data and certificates with a backup. Your old app and recordings stay where they are. Close the old app before importing.", hint=True, gap=14)
    label("Desktop download folder (OBS still manages its own recordings)")
    picker(recordings, "Choose a folder for desktop downloads")
    label("iPad/browser downloads use that device's settings. Existing recordings are not moved.", hint=True, gap=14)
    ttk.Checkbutton(body, text="Refresh the server certificate for this PC / Wi-Fi (keeps the same CA)", variable=refresh).pack(anchor="w", pady=(0, 5))
    label("Fresh setup creates unique certificates. Imports, upgrades and repairs preserve the existing CA and private keys.", hint=True, gap=14)
    ttk.Checkbutton(body, text="I approve trusting this app's local CA for my Windows user", variable=approve).pack(anchor="w", pady=(0, 5))
    label("This CA can sign certificates your Windows user will trust. Keep its private keys secret and only trust your own Studio PC. We do not change system-wide trust. If you decline, close setup; the secure desktop app cannot open until its CA is trusted.", hint=True, gap=12)
    label("For iPad / Android / the OBS PC: install only the public CA from app Settings. If Windows asks about network access, allow your trusted Private network only. Do not expose this server to the internet.", hint=True, gap=12)
    status = tk.StringVar(value="Ready. Continue prepares local HTTPS and saves your choices.")
    ttk.Label(body, textvariable=status, wraplength=690).pack(anchor="w", pady=(0, 12))

    def finish():
        nonlocal success
        try:
            recording_path = Path(recordings.get()).expanduser()
            if not recording_path.is_absolute():
                raise ValueError("Choose an absolute desktop download folder")
            app_folder = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else RESOURCE_ROOT
            if recording_path.resolve().is_relative_to(app_folder):
                raise ValueError("Choose a download folder outside the installed program folder")
            certificate = settings.certificate_dir / "rootCA.crt"
            if not approve.get() and not is_ca_trusted(certificate):
                messagebox.showinfo("Certificate approval required", "No certificate has been trusted. Approve local trust or close setup and return later.", parent=root)
                return
            continue_button.configure(state="disabled")
            status.set("Preparing saved files and local HTTPS…")
            root.update_idletasks()
            if source.get().strip():
                report = import_legacy(Path(source.get().strip()), settings.data_root)
                source.set("")
                source_entry.configure(state="disabled")
                import_button.configure(state="disabled")
                preferences["import_backup"] = report["backup"]
            ensure_https(settings.certificate_dir, refresh=refresh.get())
            if not is_ca_trusted(certificate):
                trust_ca(certificate)
            recording_path.mkdir(parents=True, exist_ok=True)
            preferences.update(setup_complete=True, recordings_dir=str(recording_path.resolve()))
            write_json_atomic(settings.data_root / "installation.json", preferences)
            success = True
            root.destroy()
        except Exception as exc:
            status.set("Setup needs attention. Your old installation has not been changed.")
            continue_button.configure(state="normal")
            messagebox.showerror("Setup needs attention", str(exc), parent=root)

    buttons = footer
    ttk.Button(buttons, text="Close without starting", command=root.destroy).pack(side="left")
    continue_button = ttk.Button(buttons, text="Continue", command=finish)
    continue_button.pack(side="right")
    if _diagnostics:
        root.update_idletasks()
        result = {"status": "created", "import_enabled": not saved,
                  "certificate_approval_default": approve.get(),
                  "continue_text": continue_button.cget("text"),
                  "scrollable": scrollbar.winfo_exists() == 1}
        root.destroy()
        return result
    root.mainloop()
    return success
