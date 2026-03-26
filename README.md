# PaperZD Sprite Tool

A free, no-code desktop tool for 2D artists to generate the JSON files required by the **[PaperZD](https://www.fab.com/listings/f4d2c7d9-6e93-4cd1-a0b5-f1dc69d99c17)** Unreal Engine plugin — no Python, no terminal, just double-click and go.

---

## ⬇️ Download

Grab the latest **`PaperZD Sprite Tool.exe`** from the [**Releases**](https://github.com/brunogbrito/SpriteTool/releases) page.  
No installation required — just run it.

---

## What does it do?

PaperZD can auto-import sprite sheets and generate Flipbooks from a `.json` file that describes where each animation frame lives in the texture. This tool lets artists create that file visually, without touching any code.

---

## How to use

### 1 · Load your sprite sheet
Click **Load Image…** and pick your PNG (or JPG) sprite sheet.

### 2 · Set the cell size
Enter the pixel dimensions of a single sprite frame in the **Cell Size** fields (e.g. `44 × 44`).  
Click **Apply Grid** — a grid overlay will appear on your texture.

### 3 · Add animation sets
Click **Add** under *Animation Sets* and give it a name (e.g. `Idle_L`, `Run_D`).  
Set the **Frame Duration** in milliseconds (default: `100 ms`).

### 4 · Select frames
With an animation selected, click **▶ Select Frames on Canvas**.  
Then click the cells in your texture **in the order they should play**.  
Each animation gets a distinct color; frame indices are shown on the cells.  
Click a selected cell again to deselect it.

### 5 · Export
Once all animations are set up, click **⬇ Generate JSON**.  
Save the `.json` file next to your texture PNG.

### 6 · Import into Unreal
Drag both the `.png` and the `.json` into your Unreal project — PaperZD will automatically detect the JSON and create the Flipbooks for you.

---

## Example

The `Example/Example_Char/` folder contains a sample sprite sheet and its matching JSON so you can see the expected output format.

---

## Building from source

If you want to run or modify the source:

```bash
# Requirements: Python 3.10+
pip install pillow pyinstaller

# Run directly
python SpriteTool.py

# Build the .exe
pyinstaller SpriteTool.py --onefile --windowed --name "PaperZD Sprite Tool"
# Output: dist/PaperZD Sprite Tool.exe
```

The GitHub Actions workflow (`.github/workflows/build.yml`) builds and attaches the `.exe` automatically whenever a new release tag (`v*`) is pushed.

---

## License

[MIT](LICENSE) — free to use, modify, and distribute.
