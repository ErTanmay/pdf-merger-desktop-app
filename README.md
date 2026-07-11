# PDF Tool Desktop App

A simple desktop application to merge, compress, split, protect, unlock, view multiple PDF files.

## Features

- Merge, Compress, Split, View, Protect, Unlock multiple PDFs
- Select output location
- Simple desktop GUI
- Windows executable support
- Built using Python

## Tech Stack

- Python
- Tkinter
- pypdf
- PyInstaller
- pymupdf

## Screenshot

<img width="958" height="503" alt="image" src="https://github.com/user-attachments/assets/43e9566e-0e5b-4957-846a-78bf52c048d3" />


## Run Locally

```bash
pip install pypdf pymupdf pillow pyinstaller
python app.py
```

## Build EXE

```bash
py -m PyInstaller --onefile --windowed --name PDF_Toolkit_by_TanmayLokhande --icon pdf.ico app.py
```

## Author

Tanmay Lokhande
