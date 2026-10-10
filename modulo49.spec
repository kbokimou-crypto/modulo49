# -*- mode: python ; coding: utf-8 -*-
# Spécification PyInstaller : produit dist\Modulo49\Modulo49.exe (sans console)

a = Analysis(
    ['modulo49.py'],
    pathex=['.'],
    datas=[('exemple.csv', '.')],
    hiddenimports=['matplotlib.backends.backend_tkagg', 'PIL._tkinter_finder'],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'IPython', 'pandas', 'scipy'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Modulo49',
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name='Modulo49')
