"""Small native host/connect chooser. Join mode never starts local services."""
from __future__ import annotations

import queue
import threading
from pathlib import Path

from .install_support import load_preferences, write_json_atomic
from .studio_client import StudioClient, ApprovalRequired, remember_connection, studio_url, public_ca
from .studio_network import discover_studios


def show_launcher(settings, *, _diagnostics=False):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from .desktop_setup import is_ca_trusted, trust_ca
    from .build_info import APP_VERSION
    root = tk.Tk()
    if _diagnostics:
        root.withdraw()
    root.title("Cricket Broadcast System · Choose a studio")
    root.geometry(f"{min(820, root.winfo_screenwidth()-80)}x{min(810, root.winfo_screenheight()-100)}")
    root.minsize(600, 460)
    root.configure(bg="#0d110f")
    style = ttk.Style(root)
    style.theme_use("clam")
    for name in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton"):
        style.configure(name, background="#0d110f", foreground="#edf2e8", font=("Segoe UI", 10))
    style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"))
    style.configure("Hint.TLabel", foreground="#abb7ac")
    style.configure("TButton", padding=8, font=("Segoe UI", 10))
    style.configure("TEntry", padding=5)
    footer = ttk.Frame(root, padding=(24, 12))
    footer.pack(side="bottom", fill="x")
    canvas = tk.Canvas(root, bg="#0d110f", highlightthickness=0)
    scroll = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scroll.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)
    canvas.configure(yscrollcommand=scroll.set)
    body = ttk.Frame(canvas, padding=24)
    item = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(item, width=e.width))
    root.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-int(e.delta/120), "units"))
    prefs = load_preferences(settings.data_root)
    saved = prefs.get("connection", {})
    mode = tk.StringVar(value=prefs.get("studio_mode", "host"))
    if mode.get() not in ("host", "connect"):
        mode.set("host")
    address = tk.StringVar(value=saved.get("url", ""))
    ca_path = tk.StringVar(value=saved.get("ca", ""))
    code = tk.StringVar()
    approve = tk.BooleanVar(value=False)
    auto_retry = tk.BooleanVar(value=True)
    fingerprint = tk.StringVar(value="Choose the public CA exported from the host's Settings. No private keys.")
    status = tk.StringVar(value="Choose what this PC should do.")
    selected = tk.StringVar()
    found = []
    outcome = None
    busy = False
    generation = 0
    jobs = queue.Queue()

    def label(text, style_name="TLabel", parent=body):
        ttk.Label(parent, text=text, wraplength=680, style=style_name).pack(anchor="w", pady=(0, 8))

    label("Your studio, on this network.", "Title.TLabel")
    label(f"Cricket Broadcast System {APP_VERSION} · choose each time you open the app", "Hint.TLabel")
    ttk.Radiobutton(body, text="Host a studio — cameras, scores and match data live on this PC", variable=mode, value="host").pack(anchor="w", pady=(10, 6))
    ttk.Radiobutton(body, text="Connect to a studio — control another PC without running a second server", variable=mode, value="connect").pack(anchor="w", pady=(0, 12))
    join_body = ttk.Frame(body)
    join_body.pack(fill="x")
    label("Nearby studios (host must enable new PC connections in Settings)", parent=join_body)
    row = ttk.Frame(join_body)
    row.pack(fill="x", pady=(0, 8))
    studios = ttk.Combobox(row, textvariable=selected, state="readonly")
    studios.pack(side="left", fill="x", expand=True)

    def background(kind, work):
        current = generation
        def run():
            try:
                jobs.put((current, kind, work(), None))
            except Exception as exc:
                jobs.put((current, kind, None, exc))
        threading.Thread(target=run, daemon=True, name="studio-" + kind).start()

    def find():
        if busy:
            return
        status.set("Looking for nearby studios… (about two seconds)")
        find_button.configure(state="disabled")
        background("find", discover_studios)

    find_button = ttk.Button(row, text="Find studios", command=find)
    find_button.pack(side="right", padx=(8, 0))

    def choose_found(event=None):
        index = studios.current()
        if 0 <= index < len(found):
            address.set(found[index]["url"])
            mode.set("connect")

    studios.bind("<<ComboboxSelected>>", choose_found)
    label("Or enter the host's LAN address", parent=join_body)
    ttk.Entry(join_body, textvariable=address).pack(fill="x", pady=(0, 8))
    label("Example: https://192.168.1.68:8765 · not 127.0.0.1 on a different PC", "Hint.TLabel", join_body)
    label("Host's public CA certificate", parent=join_body)
    cert_row = ttk.Frame(join_body)
    cert_row.pack(fill="x", pady=(0, 6))
    ttk.Entry(cert_row, textvariable=ca_path).pack(side="left", fill="x", expand=True)

    def show_fingerprint():
        try:
            _, value, _ = public_ca(Path(ca_path.get()))
            fingerprint.set("SHA-256: " + value + "\nCompare with the fingerprint shown on the host PC before approving trust.")
        except Exception:
            fingerprint.set("Choose the host's valid public CA certificate. Never select a private key.")

    def select_certificate():
        path = filedialog.askopenfilename(parent=root, title="Choose the host's public CA certificate", filetypes=[("Public certificates", "*.crt *.cer *.pem"), ("All files", "*.*")])
        if path:
            ca_path.set(path)
            show_fingerprint()

    ttk.Button(cert_row, text="Choose certificate…", command=select_certificate).pack(side="right", padx=(8, 0))
    ttk.Label(join_body, textvariable=fingerprint, wraplength=680, style="Hint.TLabel").pack(anchor="w", pady=(0, 8))
    label("Connection code (only needed for a new / removed PC)", parent=join_body)
    ttk.Entry(join_body, textvariable=code).pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(join_body, text="I verified the host fingerprint and approve this CA for my Windows user", variable=approve).pack(anchor="w", pady=(0, 6))
    label("Trust is never automatic. This CA can sign certificates trusted by your Windows user. Private keys stay on the host. Use a trusted Private network only; this is not Internet access or a view-only role.", "Hint.TLabel", join_body)
    ttk.Checkbutton(join_body, text="Keep retrying this saved studio while it starts", variable=auto_retry).pack(anchor="w", pady=(0, 8))
    ttk.Label(body, textvariable=status, wraplength=680).pack(anchor="w", pady=(12, 8))

    def update_mode(*_):
        nonlocal generation, busy
        generation += 1
        busy = False
        open_button.configure(state="normal", text="Start hosting" if mode.get() == "host" else "Connect to studio")
        find_button.configure(state="normal")
        if mode.get() == "connect":
            join_body.pack(fill="x", before=body.winfo_children()[-1])
        else:
            join_body.pack_forget()
        status.set("Host mode starts this PC's studio." if mode.get() == "host" else "Connect mode leaves this PC's server, Bluetooth receiver and match data off.")

    def connect():
        nonlocal busy
        if busy:
            return
        try:
            url = studio_url(address.get())
            path = Path(ca_path.get())
            client = StudioClient(url, path)
            if not is_ca_trusted(path) and not approve.get():
                messagebox.showinfo("Public certificate approval", "Choose the public CA, compare its fingerprint with the host PC, then approve trust. No trust has been added.", parent=root)
                return
            # A changed LAN IP can reuse approval only after BOTH the selected
            # certificate and the host UUID verify, before sending the token.
            saved_token = saved.get("token", "") if saved.get("ca_sha256") == client.fingerprint and not code.get().strip() else ""
            expected_id = saved.get("id") if saved_token else None
            entered_code = code.get()
            busy = True
            open_button.configure(state="disabled")
            status.set("Verifying the host and requesting an approved connection…")
            background("connect", lambda: (client, client.connect(code=entered_code, token=saved_token, expected_id=expected_id), bool(saved_token)))
        except Exception as exc:
            status.set(str(exc))

    def open_studio():
        nonlocal outcome
        if mode.get() == "host":
            preferences = load_preferences(settings.data_root)
            preferences["studio_mode"] = "host"
            write_json_atomic(settings.data_root / "installation.json", preferences)
            outcome = {"mode": "host"}
            root.destroy()
        else:
            connect()

    def poll():
        nonlocal busy, found, outcome
        try:
            while True:
                job_generation, kind, value, error = jobs.get_nowait()
                if job_generation != generation:
                    continue
                if kind == "find":
                    find_button.configure(state="normal")
                    found = value or []
                    studios.configure(values=[f"{item['name']} · {item['url']}" for item in found])
                    status.set(str(error) if error else f"Found {len(found)} studio(s). Select one, or enter its address manually. Discovery may be blocked by Wi-Fi/firewall.")
                else:
                    busy = False
                    open_button.configure(state="normal")
                    if error:
                        status.set(str(error))
                        # Only remembered, certificate-pinned connections retry.
                        # Bad/expired codes and revoked approvals need a human.
                        if not isinstance(error, ApprovalRequired) and saved.get("url") == address.get().strip() and not code.get().strip() and auto_retry.get():
                            status.set(str(error) + " Retrying in five seconds; you can change mode or close.")
                            retry_generation = generation
                            root.after(5000, lambda: connect() if generation == retry_generation and mode.get() == "connect" else None)
                    else:
                        client, result, remembered = value
                        try:
                            # The verified CA is copied before trust; never trust a
                            # file that could have changed during a network wait.
                            remember_connection(settings.data_root, client, result)
                            saved_ca = Path(load_preferences(settings.data_root)["connection"]["ca"])
                            if not is_ca_trusted(saved_ca):
                                if not approve.get():
                                    raise ApprovalRequired("Approval was withdrawn. The CA has not been trusted.")
                                trust_ca(saved_ca)
                            outcome = {"mode": "connect", "url": client.url + "/studio/join#" + result["ticket"],
                                       "name": result["studio"]["name"], "origin": client.url}
                            root.destroy()
                            return
                        except Exception as exc:
                            status.set(str(exc))
        except queue.Empty:
            pass
        root.after(100, poll)

    ttk.Button(footer, text="Close", command=root.destroy).pack(side="left")
    open_button = ttk.Button(footer, text="Start hosting", command=open_studio)
    open_button.pack(side="right")
    mode.trace_add("write", update_mode)
    update_mode()
    show_fingerprint()
    if _diagnostics:
        root.update_idletasks()
        result = {"status": "created", "mode": mode.get(), "certificate_approval_default": approve.get(), "scrollable": True,
                  "connect_label": "Connect to a studio", "saved_address": address.get()}
        root.destroy()
        return result
    root.after(100, poll)
    root.mainloop()
    return outcome
