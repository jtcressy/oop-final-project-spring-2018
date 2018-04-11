"""
Object Oriented Programming - Spring 2018 - Final Project
Authors: Joel Cressy, Lucas Bingham
Professor: Dr. Warren MacEvoy

Demonstrating decorators by applying haptic(vibration) effects to macros applied to gamepad button presses
"""
from gamepad import GamePad
import gamepad.keyboard
import gamepad.mouse
import gamepad.haptics
import gamepad.genericjoystick

class Macros:
    def __init__(self, controller: GamePad):
        self.gamepad = controller

    @gamepad.haptics.fuzzy_vibrate
    def send_keyboard_hello(self):
        self.gamepad.keyboard.send_keypress('h')
        self.gamepad.keyboard.send_keypress('e')
        self.gamepad.keyboard.send_keypress('l')
        self.gamepad.keyboard.send_keypress('l')
        self.gamepad.keyboard.send_keypress('o')

    def _map_all(self):
        # Populate an actions list
        actions = [x for x in self.__dict__ if callable(x) and not x.__name__.startswith('_')]


def demo():
    """Run demo program"""
    controller_1 = gamepad.GamePad()
    macros = Macros(controller_1)

    # Execute macros independent of controller button presses
    print("\n\nExecute macro directly:\n")
    macros.send_keyboard_hello()

    # Assign macros to button presses in controller
    controller_1.map(macros.send_keyboard_hello, GamePad.BUTTON_A)

    # Press button on gamepad
    print("\n\nPressed button on gamepad:\n")
    controller_1.press_button(GamePad.BUTTON_A)


def test():
    """Run all tests"""


if __name__ == "__main__":
    demo()
