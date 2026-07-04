import os
from tkinter import *
from tkinter import filedialog, messagebox
from pypdf import PdfWriter

# -------------------- Window --------------------
root = Tk()
root.title("PDF Merger")
root.geometry("700x650")
root.resizable(False, False)

pdf_files = []

# -------------------- Functions --------------------

def add_files():
    files = filedialog.askopenfilenames(
        title="Select PDF Files",
        filetypes=[("PDF Files", "*.pdf")]
    )

    for file in files:
        if file not in pdf_files:
            pdf_files.append(file)
            listbox.insert(END, file)


def remove_file():
    selected = listbox.curselection()

    if not selected:
        messagebox.showwarning("Warning", "Please select a PDF to remove.")
        return

    index = selected[0]
    listbox.delete(index)
    pdf_files.pop(index)


def clear_files():
    listbox.delete(0, END)
    pdf_files.clear()
    status_label.config(text="Status : Ready")


def choose_output():
    file = filedialog.asksaveasfilename(
        title="Save Merged PDF",
        defaultextension=".pdf",
        filetypes=[("PDF Files", "*.pdf")]
    )

    if file:
        output_entry.delete(0, END)
        output_entry.insert(0, file)


def merge_pdfs():

    if len(pdf_files) < 2:
        messagebox.showerror(
            "Error",
            "Please select at least two PDF files."
        )
        return

    output = output_entry.get().strip()

    if output == "":
        messagebox.showerror(
            "Error",
            "Please choose the output file."
        )
        return

    merger = PdfWriter()

    try:

        for pdf in pdf_files:
            merger.append(pdf)

        merger.write(output)
        merger.close()

        status_label.config(text="Status : Merge Completed Successfully")

        messagebox.showinfo(
            "Success",
            f"PDF merged successfully!\n\nSaved at:\n{output}"
        )

    except Exception as e:

        messagebox.showerror(
            "Error",
            str(e)
        )

        status_label.config(text="Status : Error")


# -------------------- Title --------------------

title = Label(
    root,
    text="PDF Merger Tool",
    font=("Arial", 24, "bold")
)

title.pack(pady=15)

# -------------------- Listbox --------------------

listbox = Listbox(
    root,
    width=90,
    height=12,
    selectmode=SINGLE
)

listbox.pack(pady=10)

# -------------------- Buttons --------------------

button_frame = Frame(root)
button_frame.pack(pady=10)

Button(
    button_frame,
    text="Add PDFs",
    width=18,
    command=add_files
).grid(row=0, column=0, padx=8)

Button(
    button_frame,
    text="Remove Selected",
    width=18,
    command=remove_file
).grid(row=0, column=1, padx=8)

Button(
    button_frame,
    text="Clear List",
    width=18,
    command=clear_files
).grid(row=0, column=2, padx=8)

# -------------------- Output --------------------

Label(
    root,
    text="Output File",
    font=("Arial", 12, "bold")
).pack(pady=(20, 5))

output_entry = Entry(
    root,
    width=70
)

output_entry.pack()

Button(
    root,
    text="Browse",
    command=choose_output
).pack(pady=8)

# -------------------- Merge Button --------------------

Button(
    root,
    text="Merge PDFs",
    font=("Arial", 14, "bold"),
    bg="green",
    fg="white",
    width=20,
    height=2,
    command=merge_pdfs
).pack(pady=20)

# -------------------- Status --------------------

status_label = Label(
    root,
    text="Status : Ready",
    font=("Arial", 11),
    fg="blue"
)

status_label.pack()

# -------------------- Run --------------------

root.mainloop()