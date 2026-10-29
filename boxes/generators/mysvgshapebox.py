# Copyright (C) 2026

"""Turn an imported SVG outline into an open box with a matching bottom."""

import math
from pathlib import Path

from boxes import *
from boxes.generators.mysvgoutline import _SvgOutlineBase, svg_file_type


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
        self.argparser.add_argument("--wall_height", type=float, default=35.0,
                                    help="height of the box walls in mm")
        self.argparser.add_argument(
            "--material", choices=["plywood_3mm", "mdf_3mm"], default="plywood_3mm",
            help="material preset for the living hinge")
        self.argparser.add_argument(
            "--wall_style", choices=["panels", "living_hinge"], default="panels",
            help="separate flat wall panels or one flexible living-hinge wall")
        self.argparser.add_argument(
            "--bottom_joint", choices=["inside_finger_slots", "outside_edge"],
            default="inside_finger_slots",
            help="finger joints in the bottom, or a plain outside edge for gluing")
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

    def _outline_points(self, paths):
        path, transform = paths[0]
        raw = []
        for segment in path:
            steps = max(1, int(segment.length(error=1e-3) / 5.0))
            for index in range(steps):
                raw.append(self._point(segment.point(index / steps), transform, 0, 0, 1.0))
        raw.append(self._point(path[-1].end, transform, 0, 0, 1.0))
        xmin = min(point[0] for point in raw)
        xmax = max(point[0] for point in raw)
        ymin = min(point[1] for point in raw)
        ymax = max(point[1] for point in raw)
        scale = self.width / (xmax - xmin)
        normalized = [((x - xmin) * scale, (ymax - y) * scale) for x, y in raw]
        if math.hypot(normalized[0][0] - normalized[-1][0], normalized[0][1] - normalized[-1][1]) > 1e-4:
            normalized.append(normalized[0])
        return self._resample(normalized, max(self.panel_length, 5.0))

    def _draw_bottom(self, points):
        self.set_source_color(Color.INNER_CUT)
        self.ctx.move_to(*points[0])
        for point in points[1:]:
            self.ctx.line_to(*point)
        self.ctx.stroke()
        if self.bottom_joint != "inside_finger_slots":
            return
        for start, end in zip(points, points[1:]):
            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)
            if length >= 4 * self.thickness:
                self.fingerHolesAt(start[0], start[1], length,
                                   math.degrees(math.atan2(dy, dx)))

    def _living_hinge_wall(self, perimeter: float):
        width = perimeter + 2 * self.thickness
        height = self.wall_height
        end_edges = "eFef" if self.wall_join == "finger_joint" else "eeee"
        self.rectangularWall(width, height, end_edges, move="up", label="living hinge wall")
        spacing = self.hinge_spacing
        bridge = self.hinge_bridge
        if self.material == "mdf_3mm" and spacing == 3.0:
            spacing = 2.4
        if spacing <= bridge or bridge <= 0:
            raise ValueError("Living hinge spacing must be greater than bridge width.")
        self.set_source_color(Color.INNER_CUT)
        with self.saved_context() as ctx:
            ctx.translate(self.spacing, height + self.spacing)
            count = int(width // spacing)
            for index in range(1, count):
                x = index * spacing
                if index % 2:
                    ctx.move_to(x, bridge)
                    ctx.line_to(x, height - bridge * 2)
                else:
                    ctx.move_to(x, bridge * 2)
                    ctx.line_to(x, height - bridge)
            ctx.stroke()

    def _panel_walls(self, points):
        for number, (start, end) in enumerate(zip(points, points[1:]), 1):
            length = math.dist(start, end)
            if length < 4 * self.thickness:
                continue
            bottom = "f" if self.bottom_joint == "inside_finger_slots" else "e"
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
        points = self._outline_points(paths)
        self._draw_bottom(points)
        perimeter = sum(math.dist(start, end) for start, end in zip(points, points[1:]))
        if self.wall_style == "living_hinge":
            self._living_hinge_wall(perimeter)
        else:
            self._panel_walls(points)
