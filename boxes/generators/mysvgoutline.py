# Copyright (C) 2026
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from pathlib import Path
from xml.etree import ElementTree as ET

from boxes import *
from svgpathtools import Arc, CubicBezier, Line, QuadraticBezier, parse_path


class MySvgOutline(Boxes):
    """Import an SVG outline and choose which outline to use."""

    ui_group = "MyDesigns"

    def __init__(self) -> None:
        Boxes.__init__(self)
        self.argparser.add_argument(
            "--svg_file", type=str, default="",
            help="full path to the SVG file on this computer")
        self.argparser.add_argument(
            "--outline", choices=["outer", "first", "last", "all"], default="outer",
            help="which SVG outline to use")
        self.argparser.add_argument(
            "--width", type=float, default=100.0,
            help="final outline width in mm")
        self.argparser.add_argument(
            "--height", type=float, default=0.0,
            help="final outline height in mm (zero keeps the SVG proportions)")
        self.argparser.add_argument(
            "--operation", choices=["etch", "cut"], default="etch",
            help="draw as an engraving line or a cut line")

    @staticmethod
    def _subpaths(svg_file: Path):
        root = ET.parse(svg_file).getroot()
        paths = []
        for element in root.iter():
            if element.tag.endswith("path") and element.get("d"):
                paths.extend(parse_path(element.get("d")).continuous_subpaths())
        if not paths:
            raise ValueError("The SVG does not contain a path outline.")
        return paths

    @staticmethod
    def _area(path) -> float:
        try:
            return abs(float(path.area()))
        except AssertionError:
            xmin, xmax, ymin, ymax = path.bbox()
            return abs((xmax - xmin) * (ymax - ymin))

    def _select_paths(self, paths):
        if self.outline == "all":
            return paths
        if self.outline == "first":
            return [paths[0]]
        if self.outline == "last":
            return [paths[-1]]
        return [max(paths, key=self._area)]

    @staticmethod
    def _bounds(paths):
        bounds = [path.bbox() for path in paths]
        return (
            min(b[0] for b in bounds), max(b[1] for b in bounds),
            min(b[2] for b in bounds), max(b[3] for b in bounds),
        )

    def _draw_path(self, path, x_offset: float, y_offset: float, scale: float) -> None:
        ctx = self.ctx
        start = path[0].start
        ctx.move_to((start.real + x_offset) * scale, (start.imag + y_offset) * scale)
        for segment in path:
            end = segment.end
            if isinstance(segment, Line):
                ctx.line_to((end.real + x_offset) * scale, (end.imag + y_offset) * scale)
            elif isinstance(segment, QuadraticBezier):
                start = segment.start
                control = segment.control
                control1 = start + 2.0 / 3.0 * (control - start)
                control2 = end + 2.0 / 3.0 * (control - end)
                ctx.curve_to(
                    (control1.real + x_offset) * scale, (control1.imag + y_offset) * scale,
                    (control2.real + x_offset) * scale, (control2.imag + y_offset) * scale,
                    (end.real + x_offset) * scale, (end.imag + y_offset) * scale,
                )
            elif isinstance(segment, CubicBezier):
                ctx.curve_to(
                    (segment.control1.real + x_offset) * scale, (segment.control1.imag + y_offset) * scale,
                    (segment.control2.real + x_offset) * scale, (segment.control2.imag + y_offset) * scale,
                    (end.real + x_offset) * scale, (end.imag + y_offset) * scale,
                )
            elif isinstance(segment, Arc):
                for curve in segment.as_cubic_curves():
                    self._draw_path(curve, x_offset, y_offset, scale)
            else:
                raise ValueError(f"Unsupported SVG segment: {type(segment).__name__}")

    def render(self):
        if not self.svg_file:
            raise ValueError("Choose an SVG file by entering its full path.")
        svg_file = Path(self.svg_file).expanduser()
        if svg_file.suffix.lower() != ".svg" or not svg_file.is_file():
            raise ValueError("SVG file not found. Check its full path.")

        paths = self._select_paths(self._subpaths(svg_file))
        xmin, xmax, ymin, ymax = self._bounds(paths)
        source_width = xmax - xmin
        source_height = ymax - ymin
        if source_width <= 0 or source_height <= 0:
            raise ValueError("The selected SVG outline has no size.")
        scale = self.width / source_width
        if self.height:
            scale = min(scale, self.height / source_height)

        with self.saved_context() as ctx:
            self.set_source_color(Color.INNER_CUT if self.operation == "cut" else Color.ETCHING)
            for path in paths:
                self._draw_path(path, -xmin, -ymin, scale)
            ctx.stroke()
