import os
import subprocess
import time
import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.document.UpdateDocMode import QUIET_UPDATE, FULL_UPDATE  # update-links policy
# If you don't have python3-uno installed system-wide, run this script with LibreOffice's python.

# ---- tiny helper to make UNO PropertyValue objects
def _prop(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p

class LibreOfficeServer:
    """
    Starts (if needed) a headless LibreOffice process that accepts UNO socket connections,
    and returns a connected Desktop object.
    """
    def __init__(self, soffice_path="soffice", host="127.0.0.1", port=2002, extra_args=None, auto_start=True):
        self.soffice_path = soffice_path
        self.host = host
        self.port = int(port)
        self.extra_args = extra_args or []
        self.auto_start = auto_start
        self.proc = None  # subprocess.Popen, if we start LO ourselves

    def start(self):
        if self.proc and self.proc.poll() is None:
            return
        accept = f"--accept=socket,host={self.host},port={self.port};urp;"
        args = [
            self.soffice_path,
            "--headless", "--nologo", "--nodefault", "--norestore", "--nolockcheck",
            accept,
            # Optional but nice for isolation/speed on servers:
            # f'-env:UserInstallation=file://{os.path.abspath("lo-profile")}'
        ]
        args += self.extra_args
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def connect_desktop(self, timeout=10.0):
        # connect via UnoUrlResolver (start LO if necessary)
        local_ctx = uno.getComponentContext()
        resolver = local_ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.bridge.UnoUrlResolver", local_ctx
        )
        url = f"uno:socket,host={self.host},port={self.port};urp;StarOffice.ComponentContext"
        last_exc = None
        if self.auto_start:
            self.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                ctx = resolver.resolve(url)
                desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
                return desktop, ctx
            except Exception as e:
                last_exc = e
                time.sleep(0.25)
        raise RuntimeError(f"Could not connect to LibreOffice on {self.host}:{self.port}") from last_exc


def recalc_and_export(
    input_path,
    output_path,
    *,
    soffice_path="soffice",
    update_links="quiet",      # "quiet" or "full"
    hard_recalc=False,         # True => hard recalc (includes non-volatile and add-ins)
    refresh_pivots=True        # True => refresh all DataPilot tables
):
    # 1) connect to (or start) headless LibreOffice
    server = LibreOfficeServer(soffice_path=soffice_path)
    desktop, ctx = server.connect_desktop()

    # 2) load the document hidden; tell LO how to handle external links on load
    upd = {"quiet": QUIET_UPDATE, "full": FULL_UPDATE}.get(update_links, QUIET_UPDATE)
    load_props = tuple([
        _prop("Hidden", True),
        _prop("ReadOnly", False),
        _prop("UpdateDocMode", upd),
    ])
    url_in = uno.systemPathToFileUrl(os.fspath(input_path))  # must be a file URL
    doc = desktop.loadComponentFromURL(url_in, "_blank", 0, load_props)

    try:
        # Optional: lock controllers to avoid spurious events (harmless in headless)
        doc.lockControllers()
        doc.addActionLock()

        # 3) recalc formulas
        if hard_recalc:
            # dispatch .uno:CalculateHard (same as Data ▸ Calculate ▸ Recalculate hard)
            frame = doc.getCurrentController().getFrame()
            dispatcher = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
            dispatcher.executeDispatch(frame, ".uno:CalculateHard", "", 0, ())
        else:
            # regular full recalc of all formula cells via XCalculatable
            doc.calculateAll()

        # 4) refresh all Pivot Tables (DataPilot), if any
        if refresh_pivots:
            sheets = doc.getSheets()
            for name in sheets.getElementNames():
                sheet = sheets.getByName(name)
                try:
                    # Some builds expose getDataPilotTables(), others a DataPilotTables property
                    dpt = sheet.getDataPilotTables() if hasattr(sheet, "getDataPilotTables") else getattr(sheet, "DataPilotTables", None)
                    if not dpt:
                        continue
                    for i in range(dpt.getCount()):
                        dpt.getByIndex(i).refresh()
                except Exception:
                    # Not a fatal problem if a sheet doesn't support pilots
                    pass

        # 5) export to XLSX
        url_out = uno.systemPathToFileUrl(os.fspath(output_path))
        store_props = tuple([_prop("FilterName", "Calc MS Excel 2007 XML")])
        doc.storeToURL(url_out, store_props)

    finally:
        # 6) cleanup
        try:
            doc.removeActionLock()
        except Exception:
            pass
        try:
            doc.unlockControllers()
        except Exception:
            pass
        doc.close(True)
