from .keyboard import Keyboard
from .mouse import Mouse
from .genericjoystick import GenericJoystick

class GamePad:
    """Xbox joystick layout:
        Buttons: ABXY, start, select, bumper left, bumper right, left stick, right stick
        Joystick axes: JoyLeftX, JoyLeftY, JoyRightX, JoyRightY
        Other Axes: TriggerL, TriggerR (Can act as buttons when trigger pull > 75%, configurable)
    """
    BUTTON_A = 1
    BUTTON_B = 2
    BUTTON_X = 3
    BUTTON_Y = 4
    BUTTON_START = 5
    BUTTON_SELECT = 6
    BUTTON_LB = 7
    BUTTON_RB = 8
    BUTTON_LS = 9
    BUTTON_RS = 10

    def __init__(self):
        self.keyboard = Keyboard()
        self.mouse = Mouse()
        self.genericjoystick = GenericJoystick()
        self.button_mappings = {
            self.BUTTON_A: None,
            self.BUTTON_B: None,
            self.BUTTON_X: None,
            self.BUTTON_Y: None,
            self.BUTTON_START: None,
            self.BUTTON_SELECT: None,
            self.BUTTON_LB: None,
            self.BUTTON_RB: None,
            self.BUTTON_LS: None,
            self.BUTTON_RS: None
        }

    def map(self, macro, button):
        """Maps a macro (type function) to a button"""
        self.button_mappings[button] = macro

    def press_button(self, button):
        """Run mapping for the button"""
        if callable(self.button_mappings[button]):
            self.button_mappings[button]()

    def trigger_joystickmove(self, joystick, deltax, deltay):
        """Run events for when joystick moves"""
