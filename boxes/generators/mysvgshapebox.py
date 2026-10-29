# Copyright (C) 2026

"""Turn an imported SVG outline into an open box with a matching bottom."""

import math
from pathlib import Path

from boxes import *
from boxes.generators.mysvgoutline import _SvgOutlineBase, svg_file_type
from svgpathtools import Line


class MySvgOutline(_SvgOutlineBase):
    """Import an SVG outline and create an open box from it."""

    ui_group = "MyDesigns"
    webinterface = True

    def __init__(self) -> None:
        Boxes.__init__(self)
        self.addSettingsArgs(edges.FingerJointSettings)
        self.argparser.add_argument(
            "--svg_file", type=svg_file_type, default="",
            help="choose an SVG file from this computer")
        self.argparser.add_argument(
            "--outline", choices=["outer", "first", "last", "all"], default="outer",
            help="which SVG outline to use as the bottom")
        self.argparser.add_argument("--width", type=float, default=100.0,
                                    help="final bottom width in mm")
        self.argparser.add_argument(
            "--size_mode", choices=["inside", "outside"], default="outside",
            help="treat width as the usable inside size or the outside SVG size")
        self.argparser.add_argument("--wall_height", type=float, default=35.0,
                                    help="height of the box walls in mm")
        self.argparser.add_argument(
            "--material", choices=["plywood_3mm", "mdf_3mm"], default="plywood_3mm",
            help="material preset for the living hinge")
        self.argparser.add_argument(
            "--wall_style", choices=["panels", "living_hinge"], default="panels",
            help="separate flat wall panels or one flexible living-hinge wall")
        self.argparser.add_argument(
            "--bottom_joint", choices=["inside_slots", "outside_open"],
            default="inside_slots",
            help="inside slots set back by material thickness, or open outside fingers")
        self.argparser.add_argument(
            "--wall_join", choices=["finger_joint", "butt_joint"], default="finger_joint",
            help="how the two ends of a living-hinge wall join together")
        self.argparser.add_argument("--panel_length", type=float, default=25.0,
                                    help="target width of each flat wall panel in mm")
        self.argparser.add_argument("--hinge_spacing", type=float, default=3.0,
                                    help="distance between living-hinge cuts in mm")
        self.argparser.add_argument("--hinge_bridge", type=float, default=1.0,
                                    help="uncut bridge left between hinge cuts in mm")

    @staticmethod
    def _resample(points, target_length: float):
        result = [points[0]]
        carry = 0.0
        for start, end in zip(points, points[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            if length < 1e-6:
                continue
            distance = target_length - carry
            while distance < length:
                ratio = distance / length
                result.append((start[0] + ratio * dx, start[1] + ratio * dy))
                distance += target_length
            carry = length - (distance - target_length)
        if math.hypot(result[-1][0] - points[-1][0], result[-1][1] - points[-1][1]) > 1e-4:
            result.append(points[-1])
        return result

    def _panel_segments(self, paths):
        path, transform = paths[0]
        xmin, xmax, ymin, ymax = self._bounds(paths)
        requested_width = self.width + (2 * self.thickness if self.size_mode == "inside" else 0)
        scale = requested_width / (xmax - xmin)

        def point(position):
            return self._point(position, transform, xmin, ymax, scale)

        segments = [(point(segment.start), point(segment.end)) for segment in path
                    if isinstance(segment, Line)]
        if segments:
            return segments, scale

        # Curved-only drawings have no straight sides. Approximate them for panels.
        raw = [point(segment.point(index / 8)) for segment in path for index in range(8)]
        raw.append(point(path[-1].end))
        sampled = self._resample(raw, max(self.panel_length, 5.0))
        return list(zip(sampled, sampled[1:])), scale

    def _draw_bottom(self, paths, panel_segments, scale):
        xmin, xmax, ymin, ymax = self._bounds(paths)
        base_width = (xmax - xmin) * scale
        base_height = (ymax - ymin) * scale
        if self.move(base_width, base_height, "up", before=True):
            return
        self.set_source_color(Color.INNER_CUT)
        for path, transform in paths:
            self._draw_path(path, transform, xmin, ymax, scale)
        self.ctx.stroke()
        if self.bottom_joint == "inside_slots":
            center = (sum((start[0] + end[0]) / 2 for start, end in panel_segments) / len(panel_segments),
                      sum((start[1] + end[1]) / 2 for start, end in panel_segments) / len(panel_segments))
            for start, end in panel_segments:
                dx, dy = end[0] - start[0], end[1] - start[1]
                length = math.hypot(dx, dy)
                if length < 4 * self.thickness:
                    continue
                nx, ny = -dy / length, dx / length
                midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
                if (center[0] - midpoint[0]) * nx + (center[1] - midpoint[1]) * ny < 0:
                    nx, ny = -nx, -ny
                self.fingerHolesAt(start[0] + nx * self.thickness,
                                   start[1] + ny * self.thickness, length,
                                   math.degrees(math.atan2(dy, dx)))
        self.move(base_width, base_height, "up")

    def _living_hinge_wall(self, perimeter: float):
        width = perimeter + 2 * self.thickness
        height = self.wall_height
        end_edges = "eFef" if self.wall_join == "finger_joint" else "eeee"
        if self.move(width, height, "right", before=True):
            return
        self.rectangularWall(width, height, end_edges, move="", label="living hinge wall")
        spacing = self.hinge_spacing
        bridge = self.hinge_bridge
        if self.material == "mdf_3mm" and spacing == 3.0:
            spacing = 2.4
        if spacing <= bridge or bridge <= 0:
            raise ValueError("Living hinge spacing must be greater than bridge width.")
        self.set_source_color(Color.INNER_CUT)
        count = int(width // spacing)
        for index in range(1, count):
            x = index * spacing
            if index % 2:
                self.ctx.move_to(x, bridge)
                self.ctx.line_to(x, height - bridge * 2)
            else:
                self.ctx.move_to(x, bridge * 2)
                self.ctx.line_to(x, height - bridge)
        self.ctx.stroke()
        self.move(width, height, "right")

    def _panel_walls(self, panel_segments):
        for number, (start, end) in enumerate(panel_segments, 1):
            length = math.dist(start, end)
            if length < 4 * self.thickness:
                continue
            bottom = "f" if self.bottom_joint in ("inside_slots", "outside_open") else "e"
            self.rectangularWall(length, self.wall_height, bottom + "eee",
                                 move="right", label=f"wall {number}")

    def render(self):
        if not self.svg_file:
            self.text("Choose an SVG file to create a shape box.", 0, 0,
                      fontsize=8, color=Color.ETCHING)
            return
        upload_file = Path(__import__("tempfile").gettempdir()) / "boxes-my-designs" / self.svg_file
        svg_file = upload_file if upload_file.is_file() else Path(self.svg_file).expanduser()
        if svg_file.suffix.lower() != ".svg" or not svg_file.is_file():
            raise ValueError("SVG file not found. Choose the file again.")
        paths = self._select_paths(self._subpaths(svg_file))
        if len(paths) != 1:
            raise ValueError("Choose one outline for a shape box, not all outlines.")
        panel_segments, scale = self._panel_segments(paths)
        self._draw_bottom(paths, panel_segments, scale)
        perimeter = sum(path.length(error=1e-3) for path, _ in paths) * scale
        if self.wall_style == "living_hinge":
            self._living_hinge_wall(perimeter)
        else:
            self._panel_walls(panel_segments)
