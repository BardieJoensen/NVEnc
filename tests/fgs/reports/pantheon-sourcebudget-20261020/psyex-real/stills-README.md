# R15 fixed ROI stills

Three native-size grayscale luma panels compare the admitted frame 216 original, R8 final postloop, and R15 final postloop for the frozen shirt, background, and face rectangles. The source files are the admitted one-frame `yuv420p10le` artifacts; only the luma plane is read, divided by 4 once, rounded/clipped to uint8, and rendered without resizing or enhancement. This is still extraction only: no metric, playback, rate, or repair claim.

The machine-readable manifest binds all input and output hashes, coordinates, dimensions, frame labels, and conversion details. `render.stderr` contains timing; `script.sha256` binds the executed renderer.
