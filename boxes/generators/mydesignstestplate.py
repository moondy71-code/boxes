# Copyright (C) 2026
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

from boxes import *


class MyDesignsTestPlate(Boxes):
    """A plain rectangular plate for verifying the My Designs category."""

    ui_group = "MyDesigns"

    def __init__(self) -> None:
        Boxes.__init__(self)
        self.buildArgParser(x=100, y=60)

    def render(self):
        self.rectangularWall(self.x, self.y, "eeee", label="test plate")
