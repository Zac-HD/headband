# Metal Design Files

OpenSCAD designs for laser-cut metal components.

## Rendering

Render the crown design with OpenSCAD CLI:

```bash
# Full design (both halves)
openscad -o metal/headband_waves.png --autocenter --viewall metal/headband_waves.scad

# Right half only
openscad -o metal/headband_waves_right.png \
  --projection=o \
  --camera=160,0,0,0,0,0,220 \
  --imgsize=2000,500 \
  metal/headband_waves.scad

# Electronics holder with band context
openscad -o metal/headband_waves_holder.png \
  --projection=o \
  --camera=265,-10,0,0,0,0,160 \
  --imgsize=1400,1000 \
  metal/headband_waves.scad
```

Camera parameters: `--camera=translateX,translateY,translateZ,rotX,rotY,rotZ,distance`
- `--projection=o` enables orthographic projection
- Right half: camera at x=160, distance 220
- Holder detail: camera at x=265, y=-10, distance 160 (shows holder with end cap and band)
