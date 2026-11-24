#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bloco de Notas - clone da interface do Bloco de Notas do Windows 10.

Requer apenas Python 3 (com tkinter, que já vem no instalador oficial
do Python para Windows). Execute:  python notepad.py [arquivo]
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import webbrowser
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

APP_NAME = "Bloco de Notas"
UNTITLED = "Sem título"
IS_WINDOWS = sys.platform.startswith("win")

DEFAULT_FONT_FAMILY = "Consolas" if IS_WINDOWS else "DejaVu Sans Mono"
UI_FONT = ("Segoe UI", 9) if IS_WINDOWS else ("DejaVu Sans", 9)

EOL_NAMES = {"\r\n": "Windows (CRLF)", "\n": "Unix (LF)", "\r": "Macintosh (CR)"}
ENCODING_NAMES = {
    "utf-8": "UTF-8",
    "utf-8-sig": "UTF-8 com BOM",
    "utf-16-le": "UTF-16 LE",
    "utf-16-be": "UTF-16 BE",
    "cp1252": "ANSI",
}

STATUS_BG = "#F0F0F0"
STATUS_LINE = "#D7D7D7"


def settings_path():
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "BlocoDeNotasPy", "settings.json")


def load_settings():
    defaults = {
        "font_family": DEFAULT_FONT_FAMILY,
        "font_size": 11,
        "font_weight": "normal",
        "font_slant": "roman",
        "word_wrap": False,
        "status_bar": True,
        "geometry": "420x520",
        "match_case": False,
        "wrap_around": False,
    }
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            defaults.update(json.load(f))
    except Exception:
        pass
    return defaults


def save_settings(data):
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def make_icon(root):
    """Desenha um pequeno ícone de bloco de notas (32x32)."""
    size = 32
    img = tk.PhotoImage(master=root, width=size, height=size)
    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            color = None
            if 5 <= x <= 26 and 4 <= y <= 29:
                color = "#FFFFFF"
                if x in (5, 26) or y == 29:
                    color = "#5A7FA8"
                elif 4 <= y <= 8:
                    color = "#7FB2E5"  # topo azul
                    if y == 4:
                        color = "#5A7FA8"
                elif y > 10 and (y - 11) % 4 == 0 and 8 <= x <= 23:
                    color = "#9DB7D3"  # linhas
            # espiral
            if y in (2, 3, 4, 5, 6) and x in (9, 10, 14, 15, 19, 20, 24) and color != "#FFFFFF":
                if y in (2, 6) or x in (9, 14, 19, 24):
                    color = "#3C3C3C"
            row.append(color or "")
        rows.append(row)
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c:
                img.put(c, (x, y))
    return img


# --------------------------------------------------------------------------
# Diálogos
# --------------------------------------------------------------------------
class BaseDialog(tk.Toplevel):
    def __init__(self, app, title):
        super().__init__(app.root)
        self.app = app
        self.title(title)
        self.resizable(False, False)
        self.transient(app.root)
        self.configure(padx=10, pady=10)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda e: self.close())
        if IS_WINDOWS:
            try:
                self.attributes("-toolwindow", False)
            except tk.TclError:
                pass

    def place_near_parent(self):
        self.update_idletasks()
        root = self.app.root
        x = root.winfo_rootx() + max(0, (root.winfo_width() - self.winfo_width()) // 2)
        y = root.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")

    def close(self):
        self.destroy()
        self.app.text.focus_set()


class FindDialog(BaseDialog):
    def __init__(self, app, replace=False):
        super().__init__(app, "Substituir" if replace else "Localizar")
        self.replace = replace
        self.find_var = tk.StringVar(value=app.last_search)
        self.repl_var = tk.StringVar(value=app.last_replace)
        self.case_var = tk.BooleanVar(value=app.settings["match_case"])
        self.wrap_var = tk.BooleanVar(value=app.settings["wrap_around"])
        self.dir_var = tk.StringVar(value="down")

        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nw")
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="ne", padx=(10, 0))

        ttk.Label(left, text="Localizar:").grid(row=0, column=0, sticky="w", pady=2)
        self.find_entry = ttk.Entry(left, textvariable=self.find_var, width=34)
        self.find_entry.grid(row=0, column=1, sticky="we", pady=2)
        r = 1
        if replace:
            ttk.Label(left, text="Substituir por:").grid(row=1, column=0, sticky="w", pady=2)
            ttk.Entry(left, textvariable=self.repl_var, width=34).grid(row=1, column=1, sticky="we", pady=2)
            r = 2

        opts = ttk.Frame(left)
        opts.grid(row=r, column=0, columnspan=2, sticky="we", pady=(14, 0))
        checks = ttk.Frame(opts)
        checks.pack(side="left", anchor="s")
        ttk.Checkbutton(checks, text="Diferenciar maiúsculas de minúsculas",
                        variable=self.case_var).pack(anchor="w")
        ttk.Checkbutton(checks, text="Quebra automática", variable=self.wrap_var).pack(anchor="w")
        if not replace:
            direction = ttk.LabelFrame(opts, text="Direção", padding=(6, 2))
            direction.pack(side="right", padx=(10, 0))
            ttk.Radiobutton(direction, text="Acima", value="up", variable=self.dir_var).pack(side="left")
            ttk.Radiobutton(direction, text="Abaixo", value="down", variable=self.dir_var).pack(side="left")

        self.btn_next = ttk.Button(right, text="Localizar próxima", command=self.find_next, width=18)
        self.btn_next.pack(pady=2)
        if replace:
            ttk.Button(right, text="Substituir", command=self.replace_one, width=18).pack(pady=2)
            ttk.Button(right, text="Substituir tudo", command=self.replace_all, width=18).pack(pady=2)
        ttk.Button(right, text="Cancelar", command=self.close, width=18).pack(pady=2)

        self.find_var.trace_add("write", lambda *a: self.update_state())
        self.bind("<Return>", lambda e: self.find_next())
        self.update_state()
        self.place_near_parent()
        self.find_entry.focus_set()
        self.find_entry.select_range(0, "end")

    def update_state(self):
        self.btn_next.state(["!disabled"] if self.find_var.get() else ["disabled"])

    def sync(self):
        self.app.last_search = self.find_var.get()
        self.app.last_replace = self.repl_var.get()
        self.app.settings["match_case"] = self.case_var.get()
        self.app.settings["wrap_around"] = self.wrap_var.get()

    def find_next(self):
        if not self.find_var.get():
            return
        self.sync()
        self.app.search(backwards=(self.dir_var.get() == "up"))

    def replace_one(self):
        if not self.find_var.get():
            return
        self.sync()
        self.app.replace_current()

    def replace_all(self):
        if not self.find_var.get():
            return
        self.sync()
        self.app.replace_all()


class GotoDialog(BaseDialog):
    def __init__(self, app):
        super().__init__(app, "Ir para a linha")
        current = app.text.index("insert").split(".")[0]
        self.var = tk.StringVar(value=current)
        ttk.Label(self, text="Número da linha:").grid(row=0, column=0, columnspan=2, sticky="w")
        vcmd = (self.register(lambda s: s.isdigit() or s == ""), "%P")
        entry = ttk.Entry(self, textvariable=self.var, width=36, validate="key", validatecommand=vcmd)
        entry.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 12))
        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Ir para", command=self.go).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=self.close).pack(side="left")
        self.bind("<Return>", lambda e: self.go())
        self.place_near_parent()
        entry.focus_set()
        entry.select_range(0, "end")
        self.grab_set()

    def go(self):
        try:
            line = int(self.var.get())
        except ValueError:
            return
        total = int(self.app.text.index("end-1c").split(".")[0])
        if line < 1 or line > total:
            messagebox.showinfo("Bloco de Notas - Ir para a linha",
                                "O número da linha está além do número total de linhas",
                                parent=self)
            return
        self.app.text.mark_set("insert", f"{line}.0")
        self.app.text.see("insert")
        self.app.update_status()
        self.close()


class FontDialog(BaseDialog):
    STYLES = [("Normal", "normal", "roman"), ("Itálico", "normal", "italic"),
              ("Negrito", "bold", "roman"), ("Negrito Itálico", "bold", "italic")]
    SIZES = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]

    def __init__(self, app):
        super().__init__(app, "Fonte")
        s = app.settings
        families = sorted({f for f in tkfont.families(app.root) if not f.startswith("@")},
                          key=str.lower)
        self.families = families
        self.family = tk.StringVar(value=s["font_family"])
        style_name = next((n for n, w, sl in self.STYLES
                           if w == s["font_weight"] and sl == s["font_slant"]), "Normal")
        self.style = tk.StringVar(value=style_name)
        self.size = tk.StringVar(value=str(s["font_size"]))

        self.lb_family = self._column(0, "Fonte:", self.family, families, 26)
        self.lb_style = self._column(1, "Estilo da fonte:", self.style,
                                     [n for n, _, _ in self.STYLES], 16)
        self.lb_size = self._column(2, "Tamanho:", self.size, [str(x) for x in self.SIZES], 7)

        sample = ttk.LabelFrame(self, text="Exemplo", padding=6)
        sample.grid(row=3, column=1, columnspan=2, sticky="we", pady=(10, 0))
        self.sample_font = tkfont.Font(self)
        tk.Label(sample, text="AaBbYyZz", font=self.sample_font, width=14, height=2).pack()

        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="OK", command=self.ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=self.close).pack(side="left")
        self.bind("<Return>", lambda e: self.ok())

        for var in (self.family, self.style, self.size):
            var.trace_add("write", lambda *a: self.preview())
        self.preview()
        self.place_near_parent()
        self.grab_set()

    def _column(self, col, label, var, values, width):
        ttk.Label(self, text=label).grid(row=0, column=col, sticky="w", padx=(0, 8))
        entry = ttk.Entry(self, textvariable=var, width=width)
        entry.grid(row=1, column=col, sticky="we", padx=(0, 8))
        frame = ttk.Frame(self)
        frame.grid(row=2, column=col, sticky="nswe", padx=(0, 8))
        lb = tk.Listbox(frame, height=8, width=width, exportselection=False,
                        activestyle="none", selectbackground="#0078D7")
        sb = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for v in values:
            lb.insert("end", v)
        if var.get() in values:
            i = values.index(var.get())
            lb.selection_set(i)
            lb.see(i)
        lb.bind("<<ListboxSelect>>",
                lambda e: lb.curselection() and var.set(lb.get(lb.curselection()[0])))
        return lb

    def _values(self):
        family = self.family.get() or DEFAULT_FONT_FAMILY
        weight, slant = next(((w, sl) for n, w, sl in self.STYLES if n == self.style.get()),
                             ("normal", "roman"))
        try:
            size = max(1, min(500, int(self.size.get())))
        except ValueError:
            size = self.app.settings["font_size"]
        return family, weight, slant, size

    def preview(self):
        family, weight, slant, size = self._values()
        self.sample_font.configure(family=family, weight=weight, slant=slant, size=size)

    def ok(self):
        family, weight, slant, size = self._values()
        self.app.settings.update(font_family=family, font_weight=weight,
                                 font_slant=slant, font_size=size)
        self.app.apply_font()
        self.close()


class PageSetupDialog(BaseDialog):
    def __init__(self, app):
        super().__init__(app, "Configurar página")
        ps = app.page_setup
        self.vars = {k: tk.StringVar(value=v) for k, v in ps.items()}
        paper = ttk.LabelFrame(self, text="Papel", padding=6)
        paper.grid(row=0, column=0, sticky="we")
        ttk.Label(paper, text="Tamanho:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(paper, textvariable=self.vars["paper"], state="readonly", width=20,
                     values=["A4", "A5", "Carta", "Ofício"]).grid(row=0, column=1, pady=2)
        orient = ttk.LabelFrame(self, text="Orientação", padding=6)
        orient.grid(row=0, column=1, sticky="nswe", padx=(8, 0))
        ttk.Radiobutton(orient, text="Retrato", value="Retrato",
                        variable=self.vars["orientation"]).pack(anchor="w")
        ttk.Radiobutton(orient, text="Paisagem", value="Paisagem",
                        variable=self.vars["orientation"]).pack(anchor="w")
        margins = ttk.LabelFrame(self, text="Margens (milímetros)", padding=6)
        margins.grid(row=1, column=0, columnspan=2, sticky="we", pady=(8, 0))
        for i, (key, label) in enumerate([("left", "Esquerda:"), ("right", "Direita:"),
                                          ("top", "Superior:"), ("bottom", "Inferior:")]):
            ttk.Label(margins, text=label).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=4)
            ttk.Entry(margins, textvariable=self.vars[key], width=8).grid(
                row=i // 2, column=(i % 2) * 2 + 1, pady=2)
        hf = ttk.Frame(self)
        hf.grid(row=2, column=0, columnspan=2, sticky="we", pady=(8, 0))
        ttk.Label(hf, text="Cabeçalho:").grid(row=0, column=0, sticky="w")
        ttk.Entry(hf, textvariable=self.vars["header"], width=40).grid(row=0, column=1, pady=2)
        ttk.Label(hf, text="Rodapé:").grid(row=1, column=0, sticky="w")
        ttk.Entry(hf, textvariable=self.vars["footer"], width=40).grid(row=1, column=1, pady=2)
        btns = ttk.Frame(self)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="OK", command=self.ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=self.close).pack(side="left")
        self.place_near_parent()
        self.grab_set()

    def ok(self):
        self.app.page_setup = {k: v.get() for k, v in self.vars.items()}
        self.close()


class AboutDialog(BaseDialog):
    def __init__(self, app):
        super().__init__(app, "Sobre o Bloco de Notas")
        top = tk.Frame(self)
        top.pack(fill="x")
        tk.Label(top, image=app.icon).pack(side="left", anchor="n", padx=(0, 12))
        tk.Label(top, text="Bloco de Notas", font=(UI_FONT[0], 16)).pack(side="left", anchor="w")
        ttk.Separator(self).pack(fill="x", pady=10)
        info = ("Versão 1.0\n\n"
                "Um editor de texto simples escrito em Python/Tkinter,\n"
                "com a mesma interface do Bloco de Notas do Windows 10.\n\n"
                "Este programa é software livre.")
        tk.Label(self, text=info, justify="left", font=UI_FONT).pack(anchor="w")
        ttk.Button(self, text="OK", command=self.close).pack(anchor="e", pady=(12, 0))
        self.bind("<Return>", lambda e: self.close())
        self.place_near_parent()
        self.grab_set()


# --------------------------------------------------------------------------
# Aplicação principal
# --------------------------------------------------------------------------
class Notepad:
    ZOOM_LEVELS = list(range(10, 501, 10))

    def __init__(self, root, path=None):
        self.root = root
        self.settings = load_settings()
        self.path = None
        self.encoding = "utf-8"
        self.eol = "\r\n" if IS_WINDOWS else "\n"
        self.zoom = 100
        self.last_search = ""
        self.last_replace = ""
        self.find_dialog = None
        self.page_setup = {"paper": "A4", "orientation": "Retrato", "left": "20", "right": "20",
                           "top": "25", "bottom": "25", "header": "&f", "footer": "Página &p"}

        root.geometry(self.settings.get("geometry", "420x520"))
        root.minsize(200, 120)
        self.icon = make_icon(root)
        root.iconphoto(True, self.icon)
        root.option_add("*Font", UI_FONT)
        root.option_add("*tearOff", False)

        self.text_font = tkfont.Font(root)
        self.wrap_var = tk.BooleanVar(value=self.settings["word_wrap"])
        self.status_var = tk.BooleanVar(value=self.settings["status_bar"])

        self.build_menu()
        self.build_statusbar()
        self.build_editor()
        self.build_context_menu()
        self.bind_keys()
        self.apply_font()
        self.apply_wrap()
        self.apply_statusbar()

        root.protocol("WM_DELETE_WINDOW", self.exit_app)
        if path:
            self.load_file(path)
        self.update_title()
        self.update_status()
        self.text.focus_set()

    # ---------------------------------------------------------------- layout
    def build_menu(self):
        m = tk.Menu(self.root)
        self.root.config(menu=m)

        f = tk.Menu(m)
        f.add_command(label="Novo", accelerator="Ctrl+N", command=self.new_file)
        f.add_command(label="Nova Janela", accelerator="Ctrl+Shift+N", command=self.new_window)
        f.add_command(label="Abrir...", accelerator="Ctrl+O", command=self.open_file)
        f.add_command(label="Salvar", accelerator="Ctrl+S", command=self.save)
        f.add_command(label="Salvar como...", accelerator="Ctrl+Shift+S", command=self.save_as)
        f.add_separator()
        f.add_command(label="Configurar página...", command=lambda: PageSetupDialog(self))
        f.add_command(label="Imprimir...", accelerator="Ctrl+P", command=self.print_file)
        f.add_separator()
        f.add_command(label="Sair", command=self.exit_app)
        m.add_cascade(label="Arquivo", menu=f)

        e = tk.Menu(m, postcommand=self.refresh_edit_menu)
        self.edit_menu = e
        e.add_command(label="Desfazer", accelerator="Ctrl+Z", command=self.undo)
        e.add_separator()
        e.add_command(label="Recortar", accelerator="Ctrl+X", command=self.cut)
        e.add_command(label="Copiar", accelerator="Ctrl+C", command=self.copy)
        e.add_command(label="Colar", accelerator="Ctrl+V", command=self.paste)
        e.add_command(label="Excluir", accelerator="Del", command=self.delete)
        e.add_separator()
        e.add_command(label="Pesquisar com o Bing...", accelerator="Ctrl+E", command=self.search_web)
        e.add_command(label="Localizar...", accelerator="Ctrl+F", command=lambda: self.open_find(False))
        e.add_command(label="Localizar próxima", accelerator="F3", command=lambda: self.find_again(False))
        e.add_command(label="Localizar anterior", accelerator="Shift+F3", command=lambda: self.find_again(True))
        e.add_command(label="Substituir...", accelerator="Ctrl+H", command=lambda: self.open_find(True))
        e.add_command(label="Ir para...", accelerator="Ctrl+G", command=self.goto_line)
        e.add_separator()
        e.add_command(label="Selecionar Tudo", accelerator="Ctrl+A", command=self.select_all)
        e.add_command(label="Hora/Data", accelerator="F5", command=self.insert_datetime)
        m.add_cascade(label="Editar", menu=e)

        fm = tk.Menu(m)
        fm.add_checkbutton(label="Quebra Automática de Linha", variable=self.wrap_var,
                           command=self.apply_wrap)
        fm.add_command(label="Fonte...", command=lambda: FontDialog(self))
        m.add_cascade(label="Formatar", menu=fm)

        v = tk.Menu(m)
        z = tk.Menu(v)
        z.add_command(label="Ampliar", accelerator="Ctrl+Mais", command=lambda: self.set_zoom(+1))
        z.add_command(label="Reduzir", accelerator="Ctrl+Menos", command=lambda: self.set_zoom(-1))
        z.add_command(label="Restaurar Zoom Padrão", accelerator="Ctrl+0", command=lambda: self.set_zoom(0))
        v.add_cascade(label="Zoom", menu=z)
        v.add_checkbutton(label="Barra de Status", variable=self.status_var,
                          command=self.apply_statusbar)
        self.view_menu = v
        m.add_cascade(label="Exibir", menu=v)

        h = tk.Menu(m)
        h.add_command(label="Exibir Ajuda", command=self.show_help)
        h.add_command(label="Enviar Comentários", command=self.send_feedback)
        h.add_separator()
        h.add_command(label="Sobre o Bloco de Notas", command=lambda: AboutDialog(self))
        m.add_cascade(label="Ajuda", menu=h)

    def build_editor(self):
        self.editor_frame = tk.Frame(self.root, bd=0)
        self.editor_frame.pack(side="top", fill="both", expand=True)
        self.text = tk.Text(
            self.editor_frame, undo=True, autoseparators=True, maxundo=-1,
            relief="flat", bd=0, highlightthickness=0, padx=2, pady=0,
            font=self.text_font, bg="#FFFFFF", fg="#000000",
            insertbackground="#000000", insertwidth=1,
            selectbackground="#0078D7", selectforeground="#FFFFFF",
            inactiveselectbackground="#CCE8FF", exportselection=True,
        )
        self.vbar = tk.Scrollbar(self.editor_frame, orient="vertical", command=self.text.yview)
        self.hbar = tk.Scrollbar(self.editor_frame, orient="horizontal", command=self.text.xview)
        self.corner = tk.Frame(self.editor_frame, bg=STATUS_BG, width=17, height=17)
        self.text.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.corner.grid(row=1, column=1, sticky="nsew")
        self.editor_frame.rowconfigure(0, weight=1)
        self.editor_frame.columnconfigure(0, weight=1)

        self.text.bind("<<Modified>>", self.on_modified)
        for ev in ("<KeyRelease>", "<ButtonRelease-1>", "<B1-Motion>", "<<Selection>>"):
            self.text.bind(ev, lambda e: self.update_status(), add="+")

    def build_statusbar(self):
        sb = tk.Frame(self.root, bg=STATUS_BG, height=23)
        self.statusbar = sb
        tk.Frame(sb, bg=STATUS_LINE, height=1).pack(side="top", fill="x")
        row = tk.Frame(sb, bg=STATUS_BG)
        row.pack(fill="both", expand=True)

        grip = ttk.Sizegrip(row)
        grip.pack(side="right", anchor="se")

        def cell(width, text=""):
            var = tk.StringVar(value=text)
            frame = tk.Frame(row, bg=STATUS_BG, width=width, height=22)
            frame.pack_propagate(False)
            frame.pack(side="right", fill="y")
            tk.Frame(frame, bg=STATUS_LINE, width=1).pack(side="left", fill="y")
            tk.Label(frame, textvariable=var, bg=STATUS_BG, anchor="w", padx=6,
                     font=UI_FONT).pack(side="left", fill="both", expand=True)
            return var

        self.enc_var = cell(120, "UTF-8")
        self.eol_var = cell(120, "Windows (CRLF)")
        self.zoom_var = cell(52, "100%")
        self.pos_var = cell(150, "Ln 1, Col 1")

    def build_context_menu(self):
        c = tk.Menu(self.root)
        c.add_command(label="Desfazer", command=self.undo)
        c.add_separator()
        c.add_command(label="Recortar", command=self.cut)
        c.add_command(label="Copiar", command=self.copy)
        c.add_command(label="Colar", command=self.paste)
        c.add_command(label="Excluir", command=self.delete)
        c.add_separator()
        c.add_command(label="Selecionar Tudo", command=self.select_all)
        c.add_separator()
        c.add_command(label="Pesquisar com o Bing...", command=self.search_web)
        self.context_menu = c

        def show(e):
            self.refresh_menu_state(c, {"Desfazer": 0, "Recortar": 2, "Copiar": 3,
                                        "Colar": 4, "Excluir": 5, "Pesquisar": 9})
            self.text.focus_set()
            c.tk_popup(e.x_root, e.y_root)
        self.text.bind("<Button-3>", show)

    # ------------------------------------------------------------ atalhos
    def bind_keys(self):
        r = self.root
        def b(seq, fn):
            handler = lambda e: (fn(), "break")[1]
            r.bind_all(seq, handler)
            # Também no próprio Text, para sobrepor os atalhos estilo Emacs do Tk
            # (Ctrl+O insere linha, Ctrl+H apaga, Ctrl+F avança, etc.).
            self.text.bind(seq, handler)
        b("<Control-n>", self.new_file)
        b("<Control-N>", self.new_window)            # Ctrl+Shift+N
        b("<Control-o>", self.open_file)
        b("<Control-s>", self.save)
        b("<Control-S>", self.save_as)               # Ctrl+Shift+S
        b("<Control-p>", self.print_file)
        b("<Control-e>", self.search_web)
        b("<Control-f>", lambda: self.open_find(False))
        b("<Control-h>", lambda: self.open_find(True))
        b("<Control-g>", self.goto_line)
        b("<F3>", lambda: self.find_again(False))
        b("<Shift-F3>", lambda: self.find_again(True))
        b("<F5>", self.insert_datetime)
        b("<Control-plus>", lambda: self.set_zoom(+1))
        b("<Control-equal>", lambda: self.set_zoom(+1))
        b("<Control-KP_Add>", lambda: self.set_zoom(+1))
        b("<Control-minus>", lambda: self.set_zoom(-1))
        b("<Control-KP_Subtract>", lambda: self.set_zoom(-1))
        b("<Control-0>", lambda: self.set_zoom(0))
        b("<Control-KP_0>", lambda: self.set_zoom(0))
        self.text.bind("<Control-a>", lambda e: (self.select_all(), "break")[1])
        self.text.bind("<Control-z>", lambda e: (self.undo(), "break")[1])
        self.text.bind("<Control-y>", lambda e: "break")  # Bloco de Notas não tem Refazer
        self.text.bind("<Control-MouseWheel>",
                       lambda e: (self.set_zoom(1 if e.delta > 0 else -1), "break")[1])
        self.text.bind("<Control-Button-4>", lambda e: (self.set_zoom(+1), "break")[1])
        self.text.bind("<Control-Button-5>", lambda e: (self.set_zoom(-1), "break")[1])

    # -------------------------------------------------------- aparência
    def apply_font(self):
        s = self.settings
        size = max(1, round(s["font_size"] * self.zoom / 100))
        self.text_font.configure(family=s["font_family"], size=size,
                                 weight=s["font_weight"], slant=s["font_slant"])
        self.text.configure(tabs=(self.text_font.measure(" " * 8),))

    def apply_wrap(self):
        wrap = self.wrap_var.get()
        self.settings["word_wrap"] = wrap
        self.text.configure(wrap="word" if wrap else "none")
        if wrap:
            self.hbar.grid_remove()
            self.corner.grid_remove()
        else:
            self.hbar.grid()
            self.corner.grid()

    def apply_statusbar(self):
        self.settings["status_bar"] = self.status_var.get()
        if self.status_var.get():
            self.statusbar.pack(side="bottom", fill="x", before=self.editor_frame)
        else:
            self.statusbar.pack_forget()

    def set_zoom(self, direction):
        if direction == 0:
            self.zoom = 100
        else:
            levels = self.ZOOM_LEVELS
            i = min(range(len(levels)), key=lambda k: abs(levels[k] - self.zoom))
            i = max(0, min(len(levels) - 1, i + direction))
            self.zoom = levels[i]
        self.apply_font()
        self.update_status()

    def update_title(self):
        name = os.path.basename(self.path) if self.path else UNTITLED
        star = "*" if self.text.edit_modified() else ""
        self.root.title(f"{star}{name} - {APP_NAME}")

    def update_status(self):
        line, col = self.text.index("insert").split(".")
        # Coluna considerando tabulações como no Bloco de Notas (1 caractere = 1 coluna)
        self.pos_var.set(f"Ln {line}, Col {int(col) + 1}")
        self.zoom_var.set(f"{self.zoom}%")
        self.eol_var.set(EOL_NAMES.get(self.eol, "Windows (CRLF)"))
        self.enc_var.set(ENCODING_NAMES.get(self.encoding, self.encoding.upper()))

    def on_modified(self, _event=None):
        self.update_title()
        self.update_status()

    # ------------------------------------------------------------ arquivos
    def confirm_discard(self):
        """Retorna True se pode continuar (salvou ou descartou)."""
        if not self.text.edit_modified():
            return True
        name = self.path or UNTITLED
        ans = messagebox.askyesnocancel(APP_NAME, f"Deseja salvar as alterações em {name}?",
                                        parent=self.root)
        if ans is None:
            return False
        if ans:
            return self.save()
        return True

    def set_content(self, content):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self.text.see("insert")
        self.update_title()
        self.update_status()

    def new_file(self):
        if not self.confirm_discard():
            return
        self.path = None
        self.encoding = "utf-8"
        self.eol = "\r\n" if IS_WINDOWS else "\n"
        self.set_content("")

    def new_window(self):
        if getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            cmd = [sys.executable, os.path.abspath(__file__)]
        subprocess.Popen(cmd)

    def open_file(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Abrir",
            filetypes=[("Documentos de texto (*.txt)", "*.txt"), ("Todos os arquivos (*.*)", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path):
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível abrir {path}.\n\n{exc}",
                                 parent=self.root)
            return
        if raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8-sig"
        elif raw.startswith(b"\xff\xfe"):
            enc, raw = "utf-16-le", raw[2:]
        elif raw.startswith(b"\xfe\xff"):
            enc, raw = "utf-16-be", raw[2:]
        else:
            try:
                raw.decode("utf-8")
                enc = "utf-8"
            except UnicodeDecodeError:
                enc = "cp1252"
        text = raw.decode(enc, errors="replace")
        if "\r\n" in text:
            eol = "\r\n"
        elif "\n" in text:
            eol = "\n"
        elif "\r" in text:
            eol = "\r"
        else:
            eol = "\r\n" if IS_WINDOWS else "\n"
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.path = os.path.abspath(path)
        self.encoding = enc
        self.eol = eol
        self.set_content(text)

    def save(self):
        if not self.path:
            return self.save_as()
        return self.write_file(self.path)

    def save_as(self):
        initial = os.path.basename(self.path) if self.path else "*.txt"
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Salvar como", initialfile=initial, defaultextension=".txt",
            filetypes=[("Documentos de texto (*.txt)", "*.txt"), ("Todos os arquivos (*.*)", "*.*")])
        if not path:
            return False
        return self.write_file(path)

    def write_file(self, path):
        content = self.text.get("1.0", "end-1c")
        if self.eol != "\n":
            content = content.replace("\n", self.eol)
        data = content.encode(self.encoding, errors="replace")
        if self.encoding == "utf-16-le":
            data = b"\xff\xfe" + data
        elif self.encoding == "utf-16-be":
            data = b"\xfe\xff" + data
        try:
            with open(path, "wb") as f:
                f.write(data)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível salvar {path}.\n\n{exc}",
                                 parent=self.root)
            return False
        self.path = os.path.abspath(path)
        self.text.edit_modified(False)
        self.update_title()
        return True

    def print_file(self):
        content = self.text.get("1.0", "end-1c")
        if not IS_WINDOWS:
            messagebox.showinfo(APP_NAME, "A impressão está disponível apenas no Windows.",
                                parent=self.root)
            return
        if not messagebox.askokcancel("Imprimir", "Imprimir o documento na impressora padrão?",
                                      parent=self.root):
            return
        try:
            fd, tmp = tempfile.mkstemp(suffix=".txt", prefix="bloco_")
            with os.fdopen(fd, "w", encoding="utf-8-sig", newline="\r\n") as f:
                f.write(content)
            os.startfile(tmp, "print")  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível imprimir.\n\n{exc}", parent=self.root)

    def exit_app(self):
        if not self.confirm_discard():
            return
        self.settings["geometry"] = self.root.geometry().split("+")[0] \
            if self.root.state() == "normal" else self.settings.get("geometry", "420x520")
        save_settings(self.settings)
        self.root.destroy()

    # --------------------------------------------------------------- edição
    def has_selection(self):
        return bool(self.text.tag_ranges("sel"))

    def refresh_menu_state(self, menu, idx):
        sel = self.has_selection()
        try:
            clip = bool(self.root.clipboard_get())
        except tk.TclError:
            clip = False
        can_undo = self.text.edit("canundo") if self._has_canundo() else True
        menu.entryconfig(idx["Desfazer"], state="normal" if can_undo else "disabled")
        for k in ("Recortar", "Copiar", "Excluir", "Pesquisar"):
            menu.entryconfig(idx[k], state="normal" if sel else "disabled")
        menu.entryconfig(idx["Colar"], state="normal" if clip else "disabled")

    def _has_canundo(self):
        try:
            self.text.edit("canundo")
            return True
        except tk.TclError:
            return False

    def refresh_edit_menu(self):
        e = self.edit_menu
        self.refresh_menu_state(e, {"Desfazer": 0, "Recortar": 2, "Copiar": 3, "Colar": 4,
                                    "Excluir": 5, "Pesquisar": 7})
        has_text = bool(self.text.get("1.0", "end-1c"))
        for i in (8, 9, 10, 11):  # Localizar..., próxima, anterior, Substituir
            e.entryconfig(i, state="normal" if has_text else "disabled")
        e.entryconfig(12, state="disabled" if self.wrap_var.get() else "normal")  # Ir para

    def undo(self):
        try:
            self.text.edit_undo()
        except tk.TclError:
            pass
        self.update_status()

    def cut(self):
        self.text.event_generate("<<Cut>>")
        self.update_status()

    def copy(self):
        self.text.event_generate("<<Copy>>")

    def paste(self):
        self.text.event_generate("<<Paste>>")
        self.text.see("insert")
        self.update_status()

    def delete(self):
        if self.has_selection():
            self.text.delete("sel.first", "sel.last")
        else:
            self.text.delete("insert")
        self.update_status()

    def select_all(self):
        self.text.tag_add("sel", "1.0", "end-1c")
        self.text.mark_set("insert", "end-1c")
        self.update_status()

    def insert_datetime(self):
        if self.has_selection():
            self.text.delete("sel.first", "sel.last")
        self.text.insert("insert", time.strftime("%H:%M %d/%m/%Y"))
        self.text.see("insert")
        self.update_status()

    def search_web(self):
        if not self.has_selection():
            return
        query = self.text.get("sel.first", "sel.last").strip()
        if query:
            from urllib.parse import quote_plus
            webbrowser.open("https://www.bing.com/search?q=" + quote_plus(query))

    def goto_line(self):
        if self.wrap_var.get():
            return
        GotoDialog(self)

    # ------------------------------------------------------- localizar
    def open_find(self, replace):
        if self.find_dialog is not None and self.find_dialog.winfo_exists():
            self.find_dialog.destroy()
        if self.has_selection():
            sel = self.text.get("sel.first", "sel.last")
            if "\n" not in sel:
                self.last_search = sel
        self.find_dialog = FindDialog(self, replace=replace)

    def find_again(self, backwards):
        if not self.last_search:
            self.open_find(False)
            return
        self.search(backwards)

    def search(self, backwards=False):
        needle = self.last_search
        nocase = not self.settings["match_case"]
        t = self.text
        if backwards:
            start = "sel.first" if self.has_selection() else "insert"
            pos = t.search(needle, start, stopindex="1.0", backwards=True, nocase=nocase)
            if not pos and self.settings["wrap_around"]:
                pos = t.search(needle, "end", stopindex=start, backwards=True, nocase=nocase)
        else:
            start = "sel.last" if self.has_selection() else "insert"
            pos = t.search(needle, start, stopindex="end", nocase=nocase)
            if not pos and self.settings["wrap_around"]:
                pos = t.search(needle, "1.0", stopindex=start, nocase=nocase)
        if not pos:
            parent = self.find_dialog if (self.find_dialog and self.find_dialog.winfo_exists()) \
                else self.root
            messagebox.showinfo(APP_NAME, f'Não foi possível localizar "{needle}"', parent=parent)
            return False
        end = f"{pos}+{len(needle)}c"
        t.tag_remove("sel", "1.0", "end")
        t.tag_add("sel", pos, end)
        t.mark_set("insert", end if not backwards else pos)
        t.see(pos)
        self.update_status()
        return True

    def selection_matches(self):
        if not self.has_selection():
            return False
        sel = self.text.get("sel.first", "sel.last")
        if self.settings["match_case"]:
            return sel == self.last_search
        return sel.lower() == self.last_search.lower()

    def replace_current(self):
        if self.selection_matches():
            self.text.edit_separator()
            self.text.delete("sel.first", "sel.last")
            self.text.insert("insert", self.last_replace)
            self.text.edit_separator()
        self.search()

    def replace_all(self):
        t = self.text
        needle, repl = self.last_search, self.last_replace
        nocase = not self.settings["match_case"]
        t.edit_separator()
        pos = "1.0"
        while True:
            pos = t.search(needle, pos, stopindex="end", nocase=nocase)
            if not pos:
                break
            t.delete(pos, f"{pos}+{len(needle)}c")
            t.insert(pos, repl)
            pos = f"{pos}+{len(repl)}c"
        t.edit_separator()
        self.update_status()

    # ------------------------------------------------------------ ajuda
    def show_help(self):
        webbrowser.open("https://www.bing.com/search?q=obter+ajuda+com+o+bloco+de+notas+no+windows")

    def send_feedback(self):
        messagebox.showinfo(APP_NAME, "Obrigado! Envie seus comentários pelo repositório do projeto.",
                            parent=self.root)


def enable_dpi_awareness():
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    if IS_WINDOWS:
        try:
            ttk.Style(root).theme_use("vista")
        except tk.TclError:
            pass
    path = sys.argv[1] if len(sys.argv) > 1 else None
    Notepad(root, path)
    root.mainloop()


if __name__ == "__main__":
    main()
