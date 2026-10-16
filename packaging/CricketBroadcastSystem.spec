# One-folder runtime; Inno Setup wraps it in the single downloadable Setup.exe.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).parent
datas = [(str(root / "frontend"), "frontend"),
         (str(root / "RELIABILITY_TEST_CHECKLIST.md"), "."),
         (str(root / "INSTALLER_TEST_CHECKLIST.md"), "."),
         (str(root / "INSTALLER_README.md"), ".")]
binaries = []
hiddenimports = ["uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.httptools_impl",
                 "uvicorn.protocols.websockets.websockets_impl", "uvicorn.lifespan.on",
                 "webview.platforms.winforms", "webview.platforms.edgechromium",
                 "qrcode.image.svg", "tkinter", "tkinter.ttk", "tkinter.filedialog",
                 "tkinter.messagebox"]
for package in ("webview", "pythonnet", "clr_loader", "winrt"):
    extra_data, extra_binaries, extra_imports = collect_all(package)
    datas += extra_data
    binaries += extra_binaries
    hiddenimports += extra_imports
hiddenimports += collect_submodules("winrt")
notices = root / "build" / "THIRD_PARTY_NOTICES.txt"
if not notices.exists():
    raise RuntimeError("Generate third-party notices with scripts/build_installer.ps1 first")
datas.append((str(notices), "."))
a = Analysis([str(root / "run.py")], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports,
             excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3", "pytest", "IPython", "matplotlib"],
             noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="CricketBroadcastSystem",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          version=str(root / "packaging" / "version_info.txt"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CricketBroadcastSystem")
