
class Mouse:
    BUTTON_LEFT = 1
    BUTTON_RIGHT = 2
    BUTTON_MIDDLE = 3
    BUTTON_FORWARD = 4
    BUTTON_BACK = 5
    BUTTON_4 = BUTTON_FORWARD
    BUTTON_5 = BUTTON_BACK

    def click(self, button):
        """Click mouse button"""

    def move(self, x, y):
        """move mouse to absolute"""

    def move_rel(self, x, y):
        """move mouse delta x and y"""

