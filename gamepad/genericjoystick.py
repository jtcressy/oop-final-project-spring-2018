
class GenericJoystick:
    JOYSTICK_1 = 1
    JOYSTICK_2 = 2
    BUTTON_1 = 1
    BUTTON_2 = 2
    BUTTON_3 = 3
    BUTTON_4 = 4
    BUTTON_5 = 5

    def update_joystick(self, joystick, y = None, x = None):
        """Update OS joystick with new x or y coordinates"""

    def button_down(self, button):
        """Send button down event to OS"""

    def button_up(self, button):
        """Send button up event to OS"""

    def button_press(self, button):
        """Send button up then down events to OS"""