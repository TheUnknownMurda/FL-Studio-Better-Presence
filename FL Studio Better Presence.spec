# PyInstaller recipe of the app: dist\FL-Studio-Better-Presence\, the .exe and the Python and Qt it runs on, which
# the installer (installer\setup.iss) installs. build.bat runs both.
import sys

from PyInstaller.utils.win32 import versioninfo

sys.path.insert(0, "src")
import flbp  # noqa: E402

numbers = tuple(int(part) for part in flbp.__version__.split(".")) + (0,)
# Without spaces, which GitHub turns into dots in the files of a release
FILE_NAME = flbp.APP_NAME.replace(" ", "-")
version = versioninfo.VSVersionInfo(
    ffi=versioninfo.FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        versioninfo.StringFileInfo([versioninfo.StringTable("040904B0", [
            versioninfo.StringStruct("ProductName", flbp.APP_NAME),
            versioninfo.StringStruct("FileDescription", flbp.APP_NAME),
            versioninfo.StringStruct("ProductVersion", flbp.__version__),
            versioninfo.StringStruct("FileVersion", flbp.__version__),
            versioninfo.StringStruct("OriginalFilename", f"{FILE_NAME}.exe"),
            versioninfo.StringStruct("LegalCopyright", "TheUnknownMurda"),
        ])]),
        versioninfo.VarFileInfo([versioninfo.VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(
    ["run.py"],
    pathex=["src"],
    datas=[("src/flbp/resources", "flbp/resources"), ("src/flbp/ui/style.qss", "flbp/ui")],
    excludes=["tkinter", "unittest", "pydoc", "doctest", "pytest", "ssl", "_ssl"],
)
# Parts of Qt the app doesn't use: software OpenGL, image formats other than PNG and SVG, encryption for the
# web, touch screens. The offscreen platform stays, for the tests that run the .exe without showing it.
UNUSED = ("opengl32sw", "qdirect2d", "qminimal", "qtuiotouchplugin", "qsvgicon", "qgif", "qicns", "qico", "qjpeg",
          "qtga", "qtiff", "qwbmp", "qwebp", "plugins\\tls", "networkinformation", "libssl", "libcrypto")
a.binaries = [entry for entry in a.binaries if not any(part in entry[0].lower().replace("/", "\\") for part in UNUSED)]
pyz = PYZ(a.pure)
# A folder rather than a single file, which would unpack itself in the temporary folder at each start: the app
# starts faster, and looks less suspicious to antivirus software
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=FILE_NAME,
    icon="assets/app.ico",
    version=version,
    console=False,
    upx=False,  # compressed programs look suspicious to antivirus software
)
COLLECT(exe, a.binaries, a.datas, name=FILE_NAME, upx=False)
