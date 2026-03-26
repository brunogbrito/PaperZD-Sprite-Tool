#!/usr/bin/env python3
"""
PaperZD Sprite Tool
Generate PaperZD-compatible JSON files from sprite sheet textures.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
from PIL import Image, ImageTk, ImageDraw


# ── Data model ────────────────────────────────────────────────────────────────

class AnimationSet:
    def __init__(self, name: str, duration: int = 100):
        self.name = name
        self.duration = duration
        self.frames: list[tuple[int, int]] = []  # ordered list of (col, row)


# ── Main application ──────────────────────────────────────────────────────────

class SpriteToolApp:

    # Colors cycled through animation sets
    ANIM_COLORS = [
        "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
        "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PaperZD Sprite Tool")
        self.root.geometry("1340x860")
        self.root.minsize(900, 600)

        # Image state
        self.image_path: str | None = None
        self.pil_image: Image.Image | None = None
        self.img_w = 0
        self.img_h = 0

        # Grid state
        self.cell_w = 32
        self.cell_h = 32
        self.grid_applied = False

        # Animation state
        self.animations: list[AnimationSet] = []
        self.active_anim_idx: int | None = None
        self.selecting_frames = False
        self.hover_cell: tuple[int, int] | None = None

        # Zoom
        self.zoom = 1.0
        self.photo_image: ImageTk.PhotoImage | None = None

        # Tk variables
        self.char_name_var = tk.StringVar(value="Character")
        self.cell_w_var = tk.StringVar(value="32")
        self.cell_h_var = tk.StringVar(value="32")
        self.duration_var = tk.StringVar(value="100")
        self._duration_trace_id = self.duration_var.trace_add("write", self._on_duration_change)

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Green.TLabel", foreground="#2ea04c")
        style.configure("Active.TButton", foreground="#ffffff", background="#2ea04c")

        # Top-level paned window
        main_pane = tk.PanedWindow(
            self.root, orient=tk.HORIZONTAL, sashwidth=6,
            bg="#888888", sashrelief=tk.RAISED,
        )
        main_pane.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # ── Left: canvas ──────────────────────────────────────────────────────
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, minsize=500, stretch="always")

        # Toolbar above canvas
        toolbar = ttk.Frame(left_frame)
        toolbar.pack(fill=tk.X, pady=(0, 3))

        ttk.Button(toolbar, text="Zoom In",  command=self.zoom_in).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(toolbar, text="Zoom Out", command=self.zoom_out).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Fit",      command=self.zoom_fit).pack(side=tk.LEFT, padx=2)

        self.canvas_info_label = ttk.Label(toolbar, text="No image loaded", foreground="gray")
        self.canvas_info_label.pack(side=tk.RIGHT, padx=6)

        # Canvas + scrollbars
        canvas_outer = ttk.Frame(left_frame, relief=tk.SUNKEN, borderwidth=1)
        canvas_outer.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_outer, bg="#2b2b2b", cursor="crosshair",
                                highlightthickness=0)
        h_sb = ttk.Scrollbar(canvas_outer, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_sb = ttk.Scrollbar(canvas_outer, orient=tk.VERTICAL,   command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=h_sb.set, yscrollcommand=v_sb.set)

        h_sb.pack(side=tk.BOTTOM, fill=tk.X)
        v_sb.pack(side=tk.RIGHT,  fill=tk.Y)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>",  self._on_canvas_click)
        self.canvas.bind("<Motion>",    self._on_canvas_hover)
        self.canvas.bind("<Leave>",     self._on_canvas_leave)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # ── Right: controls ───────────────────────────────────────────────────
        right_frame = ttk.Frame(main_pane, padding=(6, 0))
        main_pane.add(right_frame, minsize=310, stretch="never")

        # 1. Image
        img_grp = ttk.LabelFrame(right_frame, text="1 · Image", padding=8)
        img_grp.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(img_grp, text="Load Image…", command=self.load_image).pack(fill=tk.X)
        self.img_path_label = ttk.Label(img_grp, text="No image loaded",
                                        foreground="gray", wraplength=290, justify=tk.LEFT)
        self.img_path_label.pack(fill=tk.X, pady=(4, 0))

        # 2. Sprite settings
        spr_grp = ttk.LabelFrame(right_frame, text="2 · Sprite Settings", padding=8)
        spr_grp.pack(fill=tk.X, pady=(0, 8))
        spr_grp.columnconfigure(1, weight=1)

        ttk.Label(spr_grp, text="Character Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(spr_grp, textvariable=self.char_name_var).grid(
            row=0, column=1, sticky=tk.EW, padx=(6, 0), pady=2)

        ttk.Label(spr_grp, text="Cell Size (px):").grid(row=1, column=0, sticky=tk.W, pady=2)
        cell_row = ttk.Frame(spr_grp)
        cell_row.grid(row=1, column=1, sticky=tk.W, padx=(6, 0), pady=2)
        ttk.Entry(cell_row, textvariable=self.cell_w_var, width=5).pack(side=tk.LEFT)
        ttk.Label(cell_row, text=" × ").pack(side=tk.LEFT)
        ttk.Entry(cell_row, textvariable=self.cell_h_var, width=5).pack(side=tk.LEFT)

        ttk.Button(spr_grp, text="Apply Grid", command=self.apply_grid).grid(
            row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 0))
        self.grid_info_label = ttk.Label(spr_grp, text="", foreground="gray")
        self.grid_info_label.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(3, 0))

        # 3. Animation sets
        anim_grp = ttk.LabelFrame(right_frame, text="3 · Animation Sets", padding=8)
        anim_grp.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        list_frame = ttk.Frame(anim_grp)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.anim_listbox = tk.Listbox(
            list_frame, height=7, selectmode=tk.SINGLE,
            font=("Consolas", 9), activestyle="none",
            bg="#1e1e1e", fg="#cccccc", selectbackground="#3a3a5c",
        )
        anim_sb = ttk.Scrollbar(list_frame, command=self.anim_listbox.yview)
        self.anim_listbox.configure(yscrollcommand=anim_sb.set)
        anim_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.anim_listbox.pack(fill=tk.BOTH, expand=True)
        self.anim_listbox.bind("<<ListboxSelect>>", self._on_anim_select)

        btn_row = ttk.Frame(anim_grp)
        btn_row.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_row, text="Add",          command=self.add_animation).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(btn_row, text="Rename",       command=self.rename_animation).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Remove",       command=self.remove_animation).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Clear Frames", command=self.clear_frames).pack(side=tk.LEFT, padx=2)

        # Edit panel (active animation)
        edit_grp = ttk.LabelFrame(anim_grp, text="Edit Selected Animation", padding=6)
        edit_grp.pack(fill=tk.X, pady=(8, 0))

        dur_row = ttk.Frame(edit_grp)
        dur_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(dur_row, text="Frame Duration (ms):").pack(side=tk.LEFT)
        ttk.Entry(dur_row, textvariable=self.duration_var, width=6).pack(side=tk.LEFT, padx=(6, 0))

        self.select_btn = ttk.Button(
            edit_grp, text="▶  Select Frames on Canvas", command=self.toggle_select_mode)
        self.select_btn.pack(fill=tk.X)

        self.edit_status = ttk.Label(
            edit_grp, text="Select an animation set to begin.",
            foreground="gray", wraplength=290, justify=tk.LEFT)
        self.edit_status.pack(fill=tk.X, pady=(5, 0))

        # 4. Export
        exp_grp = ttk.LabelFrame(right_frame, text="4 · Export", padding=8)
        exp_grp.pack(fill=tk.X)

        ttk.Button(exp_grp, text="⬇  Generate JSON", command=self.generate_json).pack(fill=tk.X)

        # Status bar
        self.status_bar = ttk.Label(
            self.root, text="Ready.", relief=tk.SUNKEN, anchor=tk.W, padding=(6, 2))
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_status(self, msg: str):
        self.status_bar.config(text=msg)

    # ── Image loading ─────────────────────────────────────────────────────────

    def load_image(self):
        path = filedialog.askopenfilename(
            title="Load Sprite Sheet",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tga"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open image:\n{exc}")
            return

        self.image_path = path
        self.pil_image = img
        self.img_w, self.img_h = img.size

        name = os.path.basename(path)
        self.img_path_label.config(text=name, foreground="black")
        self.canvas_info_label.config(
            text=f"{name}  ·  {self.img_w}×{self.img_h} px", foreground="black")
        self._set_status(f"Loaded: {name}  ({self.img_w} × {self.img_h})")

        # Suggest character name from filename (strip extension)
        stem = os.path.splitext(name)[0]
        self.char_name_var.set(stem)

        # Reset grid + selection
        self.grid_applied = False
        self.grid_info_label.config(text="", foreground="gray")
        self.selecting_frames = False
        self.active_anim_idx = None
        self.hover_cell = None
        self.select_btn.config(text="▶  Select Frames on Canvas")

        self.zoom_fit()

    # ── Grid ──────────────────────────────────────────────────────────────────

    def apply_grid(self):
        if not self.pil_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        try:
            cw = int(self.cell_w_var.get())
            ch = int(self.cell_h_var.get())
            if cw <= 0 or ch <= 0:
                raise ValueError("Must be positive integers.")
        except ValueError as exc:
            messagebox.showerror("Invalid Cell Size", str(exc))
            return

        self.cell_w = cw
        self.cell_h = ch
        self.grid_applied = True

        cols = self.img_w // self.cell_w
        rows = self.img_h // self.cell_h
        self.grid_info_label.config(
            text=f"✓  {cols} cols × {rows} rows  ({cols * rows} cells)",
            foreground="#2ea04c",
        )
        self._set_status(
            f"Grid applied: {cw}×{ch} px cells — {cols} cols × {rows} rows")
        self._redraw_canvas()

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def zoom_in(self):
        self.zoom = min(self.zoom * 1.3, 10.0)
        self._redraw_canvas()

    def zoom_out(self):
        self.zoom = max(self.zoom / 1.3, 0.05)
        self._redraw_canvas()

    def zoom_fit(self):
        if not self.pil_image:
            return
        cw = max(self.canvas.winfo_width(),  1)
        ch = max(self.canvas.winfo_height(), 1)
        self.zoom = min(cw / self.img_w, ch / self.img_h) * 0.97
        self._redraw_canvas()

    def _on_canvas_configure(self, _event):
        # Auto-fit on first paint when no zoom set yet
        if self.pil_image and self.zoom == 1.0:
            self.zoom_fit()

    # ── Canvas drawing ────────────────────────────────────────────────────────

    def _canvas_to_cell(self, canvas_x: int, canvas_y: int) -> tuple[int, int] | None:
        """Convert canvas pixel position → (col, row), or None if out of bounds."""
        if not self.grid_applied or not self.pil_image:
            return None
        img_x = self.canvas.canvasx(canvas_x) / self.zoom
        img_y = self.canvas.canvasy(canvas_y) / self.zoom
        if img_x < 0 or img_y < 0 or img_x >= self.img_w or img_y >= self.img_h:
            return None
        col = int(img_x // self.cell_w)
        row = int(img_y // self.cell_h)
        max_col = self.img_w // self.cell_w
        max_row = self.img_h // self.cell_h
        if col >= max_col or row >= max_row:
            return None
        return (col, row)

    def _redraw_canvas(self):
        if not self.pil_image:
            self.canvas.delete("all")
            return

        base = self.pil_image.copy()

        if self.grid_applied:
            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            cols = self.img_w // self.cell_w
            rows = self.img_h // self.cell_h

            # Draw selected cells for every animation
            for anim_idx, anim in enumerate(self.animations):
                hex_color = self.ANIM_COLORS[anim_idx % len(self.ANIM_COLORS)]
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                is_active = (anim_idx == self.active_anim_idx)
                fill_alpha = 175 if is_active else 80

                for frame_idx, (fc, fr) in enumerate(anim.frames):
                    x0 = fc * self.cell_w
                    y0 = fr * self.cell_h
                    x1 = x0 + self.cell_w - 1
                    y1 = y0 + self.cell_h - 1
                    draw.rectangle([x0, y0, x1, y1], fill=(r, g, b, fill_alpha))

                    # Frame index label (only for active animation)
                    if is_active:
                        label = str(frame_idx)
                        tx, ty = x0 + 2, y0 + 2
                        # Shadow
                        draw.text((tx + 1, ty + 1), label, fill=(0, 0, 0, 200))
                        # Text
                        draw.text((tx, ty), label, fill=(255, 255, 255, 230))

            # Hover highlight
            if self.hover_cell and self.selecting_frames:
                hc, hr = self.hover_cell
                x0 = hc * self.cell_w
                y0 = hr * self.cell_h
                draw.rectangle(
                    [x0, y0, x0 + self.cell_w - 1, y0 + self.cell_h - 1],
                    fill=(255, 255, 255, 55),
                )

            # Grid lines
            line_color = (255, 255, 255, 70)
            for c in range(cols + 1):
                x = c * self.cell_w
                draw.line([(x, 0), (x, self.img_h)], fill=line_color, width=1)
            for r in range(rows + 1):
                y = r * self.cell_h
                draw.line([(0, y), (self.img_w, y)], fill=line_color, width=1)

            base = Image.alpha_composite(base, overlay)

        # Apply zoom
        nw = max(1, int(self.img_w * self.zoom))
        nh = max(1, int(self.img_h * self.zoom))
        resample = Image.NEAREST if self.zoom >= 1.0 else Image.LANCZOS
        base = base.resize((nw, nh), resample)

        self.photo_image = ImageTk.PhotoImage(base)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
        self.canvas.configure(scrollregion=(0, 0, nw, nh))

    # ── Canvas events ─────────────────────────────────────────────────────────

    def _on_canvas_click(self, event):
        if not self.selecting_frames or self.active_anim_idx is None:
            return
        cell = self._canvas_to_cell(event.x, event.y)
        if cell is None:
            return

        anim = self.animations[self.active_anim_idx]
        if cell in anim.frames:
            anim.frames.remove(cell)
        else:
            anim.frames.append(cell)

        self._refresh_anim_list()
        self._update_edit_status()
        self._redraw_canvas()

    def _on_canvas_hover(self, event):
        if not self.grid_applied:
            return
        new_hover = self._canvas_to_cell(event.x, event.y)
        if new_hover != self.hover_cell:
            self.hover_cell = new_hover
            self._redraw_canvas()

    def _on_canvas_leave(self, _event):
        if self.hover_cell is not None:
            self.hover_cell = None
            self._redraw_canvas()

    # ── Animation management ──────────────────────────────────────────────────

    def add_animation(self):
        if not self.grid_applied:
            messagebox.showwarning("Grid Required",
                                   "Apply a grid first before adding animations.")
            return
        name = self._ask_string("New Animation Set", "Animation name:")
        if name is None:
            return
        name = name.strip()
        if not name:
            return
        anim = AnimationSet(name)
        self.animations.append(anim)
        self._refresh_anim_list()
        idx = len(self.animations) - 1
        self.anim_listbox.selection_clear(0, tk.END)
        self.anim_listbox.selection_set(idx)
        self._activate_animation(idx)
        self._set_status(f"Added animation: {name}")

    def rename_animation(self):
        idx = self._selected_idx()
        if idx is None:
            return
        anim = self.animations[idx]
        name = self._ask_string("Rename Animation", "New name:", initial=anim.name)
        if name is None:
            return
        name = name.strip()
        if name:
            anim.name = name
            self._refresh_anim_list()

    def remove_animation(self):
        idx = self._selected_idx()
        if idx is None:
            return
        anim = self.animations[idx]
        if not messagebox.askyesno("Remove Animation",
                                   f"Remove '{anim.name}' and all its frames?"):
            return
        self.animations.pop(idx)
        if self.active_anim_idx is not None:
            if self.active_anim_idx == idx:
                self.active_anim_idx = None
                self.selecting_frames = False
                self.select_btn.config(text="▶  Select Frames on Canvas")
            elif self.active_anim_idx > idx:
                self.active_anim_idx -= 1
        self._refresh_anim_list()
        self._update_edit_status()
        self._redraw_canvas()

    def clear_frames(self):
        idx = self._selected_idx()
        if idx is None:
            return
        anim = self.animations[idx]
        if not messagebox.askyesno("Clear Frames",
                                   f"Clear all frames from '{anim.name}'?"):
            return
        anim.frames.clear()
        self._refresh_anim_list()
        self._update_edit_status()
        self._redraw_canvas()

    def toggle_select_mode(self):
        idx = self._selected_idx()
        if idx is None:
            messagebox.showinfo("No Selection",
                                "Please select an animation set first.")
            return

        if self.selecting_frames and self.active_anim_idx == idx:
            # Stop selecting
            self.selecting_frames = False
            self.select_btn.config(text="▶  Select Frames on Canvas")
            self._set_status("Frame selection stopped.")
        else:
            # Start selecting
            self.selecting_frames = True
            self._activate_animation(idx)
            anim = self.animations[idx]
            self.select_btn.config(text="⏹  Stop Selecting Frames")
            self._set_status(
                f"Selecting frames for '{anim.name}' — click cells to add/remove.")

        self._update_edit_status()
        self._redraw_canvas()

    def _activate_animation(self, idx: int):
        """Set active animation without toggling select mode."""
        if self.active_anim_idx != idx:
            self.selecting_frames = False
            self.select_btn.config(text="▶  Select Frames on Canvas")
        self.active_anim_idx = idx
        if idx < len(self.animations):
            self.duration_var.set(str(self.animations[idx].duration))
        self._update_edit_status()
        self._redraw_canvas()

    def _on_anim_select(self, _event):
        idx = self._selected_idx()
        if idx is not None:
            self._activate_animation(idx)

    def _on_duration_change(self, *_args):
        if self.active_anim_idx is None:
            return
        try:
            val = int(self.duration_var.get())
            if val > 0:
                self.animations[self.active_anim_idx].duration = val
        except ValueError:
            pass

    # ── List refresh helpers ──────────────────────────────────────────────────

    def _refresh_anim_list(self):
        prev_sel = self._selected_idx()
        self.anim_listbox.delete(0, tk.END)
        for i, anim in enumerate(self.animations):
            color = self.ANIM_COLORS[i % len(self.ANIM_COLORS)]
            marker = "▶ " if i == self.active_anim_idx else "   "
            self.anim_listbox.insert(
                tk.END, f"{marker}{anim.name}  ({len(anim.frames)} frames)")
            self.anim_listbox.itemconfig(i, fg=color)
        if prev_sel is not None and prev_sel < len(self.animations):
            self.anim_listbox.selection_set(prev_sel)

    def _update_edit_status(self):
        idx = self.active_anim_idx
        if idx is None or idx >= len(self.animations):
            self.edit_status.config(
                text="Select an animation set to begin.", foreground="gray")
            return
        anim = self.animations[idx]
        mode = "🖱  Click cells to add / remove frames." if self.selecting_frames \
            else "Press ▶ to start picking frames on the canvas."
        frames_summary = ""
        if anim.frames:
            coords = ", ".join(f"({c},{r})" for c, r in anim.frames[:6])
            if len(anim.frames) > 6:
                coords += f"  … +{len(anim.frames)-6} more"
            frames_summary = f"\nFrames: {coords}"
        self.edit_status.config(
            text=f"'{anim.name}':  {len(anim.frames)} frame(s) selected.\n{mode}{frames_summary}",
            foreground="black",
        )

    # ── JSON export ───────────────────────────────────────────────────────────

    def generate_json(self):
        if not self.pil_image:
            messagebox.showwarning("No Image", "Please load an image first.")
            return
        if not self.grid_applied:
            messagebox.showwarning("No Grid", "Please apply a grid first.")
            return
        if not self.animations:
            messagebox.showwarning("No Animations", "Add at least one animation set.")
            return
        for anim in self.animations:
            if not anim.frames:
                messagebox.showwarning(
                    "Empty Animation",
                    f"Animation '{anim.name}' has no frames selected.\n"
                    "Select frames or remove the animation before exporting.")
                return

        char_name = self.char_name_var.get().strip()
        if not char_name:
            messagebox.showwarning("No Character Name",
                                   "Please enter a character name in the Sprite Settings.")
            return

        # ── Build frames dict + frameTags ─────────────────────────────────────
        frames_dict: dict = {}
        frame_tags: list[dict] = []
        global_idx = 0

        for anim in self.animations:
            tag_from = global_idx
            for local_idx, (col, row) in enumerate(anim.frames):
                x = col * self.cell_w
                y = row * self.cell_h
                w = self.cell_w
                h = self.cell_h
                key = f"{char_name} #{anim.name} {local_idx}.aseprite"
                frames_dict[key] = {
                    "frame":           {"x": x, "y": y, "w": w, "h": h},
                    "rotated":         False,
                    "trimmed":         False,
                    "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h},
                    "sourceSize":       {"w": w, "h": h},
                    "duration":         anim.duration,
                }
                global_idx += 1
            frame_tags.append({
                "name":      anim.name,
                "from":      tag_from,
                "to":        global_idx - 1,
                "direction": "forward",
                "color":     "#ffffffff",
            })

        img_filename = (os.path.basename(self.image_path)
                        if self.image_path else "sprite.png")

        output = {
            "frames": frames_dict,
            "meta": {
                "app":       "PaperZD Sprite Tool",
                "version":   "1.0",
                "image":     img_filename,
                "format":    "RGBA8888",
                "size":      {"w": self.img_w, "h": self.img_h},
                "scale":     "1",
                "frameTags": frame_tags,
                "layers":    [{"name": char_name, "opacity": 255, "blendMode": "normal"}],
                "slices":    [],
            },
        }

        # ── Save dialog ───────────────────────────────────────────────────────
        default_name = os.path.splitext(img_filename)[0] + ".json"
        save_path = filedialog.asksaveasfilename(
            title="Save JSON",
            defaultextension=".json",
            initialfile=default_name,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not save_path:
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=1)
        except OSError as exc:
            messagebox.showerror("Save Failed", str(exc))
            return

        total_frames = sum(len(a.frames) for a in self.animations)
        messagebox.showinfo(
            "JSON Exported",
            f"File saved successfully!\n\n"
            f"Path: {save_path}\n"
            f"Animations: {len(self.animations)}\n"
            f"Total frames: {total_frames}",
        )
        self._set_status(f"✓ JSON saved → {os.path.basename(save_path)}")

    # ── Utility helpers ───────────────────────────────────────────────────────

    def _selected_idx(self) -> int | None:
        sel = self.anim_listbox.curselection()
        return sel[0] if sel else None

    def _ask_string(self, title: str, prompt: str, initial: str = "") -> str | None:
        """Simple modal dialog that returns entered text, or None on cancel."""
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("320x130")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=prompt, padding=(10, 10, 10, 4)).pack(anchor=tk.W)
        var = tk.StringVar(value=initial)
        entry = ttk.Entry(dialog, textvariable=var, width=34)
        entry.pack(padx=10, pady=(0, 8))
        entry.select_range(0, tk.END)
        entry.focus_set()

        result: list[str | None] = [None]

        def _ok(_event=None):
            result[0] = var.get()
            dialog.destroy()

        def _cancel(_event=None):
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack()
        ttk.Button(btn_frame, text="OK",     command=_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=_cancel).pack(side=tk.LEFT, padx=5)

        entry.bind("<Return>", _ok)
        dialog.bind("<Escape>", _cancel)
        dialog.wait_window()
        return result[0]


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    SpriteToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
