"""Pinned pywebview 6.2.1 adapter: keep Save As, set its initial user folder."""
from __future__ import annotations

import os
from pathlib import Path


def configure_downloads(folder: Path) -> None:
    # pywebview 6.2.1 has no public default-download-directory setting. Do not
    # mutate the system Downloads folder or blindly auto-save/overwrite files.
    # Its Windows backend registers this handler when each renderer is built.
    from webview.platforms.edgechromium import EdgeChrome, WinForms
    from webview import settings

    def on_download_starting(self, sender, args):
        if not settings["ALLOW_DOWNLOADS"]:
            args.Cancel = True
            return
        dialog = WinForms.SaveFileDialog()
        try:
            dialog.InitialDirectory = str(folder)
            dialog.Filter = self.pywebview_window.localization["windows.fileFilter.allFiles"] + " (*.*)|*.*"
            dialog.RestoreDirectory = True
            dialog.OverwritePrompt = True
            dialog.FileName = os.path.basename(args.ResultFilePath)
            if dialog.ShowDialog(self.form) == WinForms.DialogResult.OK:
                args.ResultFilePath = dialog.FileName
            else:
                args.Cancel = True
        finally:
            dialog.Dispose()

    EdgeChrome.on_download_starting = on_download_starting
