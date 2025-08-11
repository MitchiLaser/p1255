#!/usr/bin/env python3

import curses
import ipaddress
import time
import traceback
from . import capture
from . import decode


class plot:
    def __init__(self, y, x, height, width, x_label, y_label):
        # define a constant for later use
        self.x_label_width = 6  # 6 characters for the width of the x label
        # create a window for the plot
        self.win = curses.newwin(height, width, y, x)
        self.win.bkgd(curses.color_pair(0))  # black and white
        # store metadata for later reuse
        self.x = x
        self.y = y
        self.height = height
        self.width = width
        self.x_label = x_label
        self.y_label = y_label
        # begin with empty data
        self.data = None
        # draw the whole window for the first time
        self.redraw_win()

    def redraw_win(self):
        self.win.erase()
        # draw labels
        self.win.addstr(0, (self.width - len(self.y_label) - self.x_label_width) // 2 + self.x_label_width, self.y_label, curses.A_BOLD)
        self.win.addstr(self.height - 1, (self.width - len(self.x_label) - self.x_label_width) // 2 + self.x_label_width, self.x_label, curses.A_BOLD)
        # draw borders
        self.win.addstr(1, self.x_label_width, "┌" + "─" * (self.width - 2 - self.x_label_width) + "┐")
        for i in range(2, self.height - 3):
            self.win.addstr(i, self.x_label_width, "│" + " " * (self.width - 2 - self.x_label_width) + "│")
        self.win.addstr(self.height - 3, self.x_label_width, "└" + "─" * (self.width - 2 - self.x_label_width) + "┘")
        # draw data
        if self.data is None:
            placeholder = "No data to display"
            text_x = (self.width - self.x_label_width - len(placeholder)) // 2 + self.x_label_width
            text_y = (self.height - 5) // 2 + 2
            self.win.addstr(text_y, text_x, placeholder, curses.A_BOLD)
        else:
            pass
            # TODO: Draw the data
            # This includes the parsing of the dataset,
            # redrawing the plot axes
            # plotting the legend
            # plotting the channels
        self.win.refresh()

    def move(self, new_y, new_x, new_height, new_width):
        self.x = new_x
        self.y = new_y
        self.height = new_height
        self.width = new_width
        self.win.resize(new_height, new_width)
        self.win.mvwin(new_y, new_x)
        self.redraw_win()

    def update_data(self, data):
        pass
        # TODO

    def foreground(self):
        # move the window to the foreground
        # without re-calculating the window
        self.win.touchwin()
        self.win.refresh()


# base class for all interactive elements in the terminal
class movable:
    def __init__(self):
        self.x = 0
        self.y = 0

    def move(self, y, x):
        self.y = y
        self.x = x
        self.win.mvwin(y, x)
        self.win.refresh()


# curses input field for numbers with limited length
class num_input(movable):
    def __init__(self, length, placeholder=""):
        super().__init__()
        self.length = length + 1  # one more space for the cursor
        self.text = placeholder if len(placeholder) < length else placeholder[0:length]  # cut text off when too long
        self.active = True  # flag weather the cursor is visible on this input field
        self.cursor = len(placeholder)  # cursor position after last character
        self.win = curses.newwin(1, self.length, self.y, self.x)

    def redraw(self):
        self.win.erase()
        self.win.addstr(0, 0, self.text)
        self.win.move(0, self.cursor)  # show cursor at right position
        self.win.refresh()

    def activity(self):
        curses.curs_set(self.active)  # show or hide the cursor when active

    def input(self, key: str | int):
        if isinstance(key, str) and key.isdecimal():
            self.text = self.text[0:self.cursor] + key + self.text[self.cursor:]
            self.text = self.text if len(self.text) <= self.length - 1 else self.text[0:self.length - 1]
            self.cursor = min(len(self.text), self.cursor + 1)
        elif isinstance(key, int):
            match key:
                case curses.KEY_LEFT:
                    self.cursor = max(0, self.cursor - 1)  # move cursor left
                case curses.KEY_RIGHT:
                    self.cursor = min(len(self.text), self.cursor + 1)
                case curses.KEY_BACKSPACE | 127:
                    if self.cursor > 0:
                        self.text = self.text[0:self.cursor - 1] + self.text[self.cursor:]
                        self.cursor -= 1
                case curses.KEY_DC:  # delete key
                    if self.cursor < len(self.text):
                        self.text = self.text[0:self.cursor] + self.text[self.cursor + 1:]
                case _:
                    return key  # pass unhandled key to the event loop
        else:
            return key  # pass unhandled key to the event loop
        self.redraw()  # update changes on the screen
        return None  # key was handled properly


# separate input field for the IPv4 address
class ip_input(num_input):
    def __init__(self):
        super().__init__(length=15, placeholder="192.168.0.1")

    def redraw(self):
        # Validate the ip addr
        try:
            ipaddress.IPv4Address(self.text)
            self.win.bkgd(curses.color_pair(1))
        except ValueError:
            self.win.bkgd(curses.color_pair(2))
        super().redraw()

    def input(self, key: str | int):
        ret = super().input(key)
        if ret == ".":
            # insert a dot at the current cursor position
            if self.cursor < self.length - 1:
                self.text = self.text[0:self.cursor] + "." + self.text[self.cursor:]
                self.text = self.text if len(self.text) <= self.length - 1 else self.text[0:self.length - 1]
                self.cursor = min(len(self.text), self.cursor + 1)
                self.redraw()  # update changes on the screen
            return None
        else:
            return ret

    def validate(self):
        # Validate the ip addr
        try:
            ipaddress.IPv4Address(self.text)
            return True
        except ValueError:
            return False


class checkbox(movable):
    def __init__(self, text, checked):
        super().__init__()
        self.text = text
        self.win = curses.newwin(1, len(self.text) + 4, self.y, self.x)
        self.checked = checked
        self.prefix = {
            False: "( )",
            True: "(X)",
        }

    def activity(self):
        curses.curs_set(True)  # blinking cursor

    def redraw(self):
        self.win.erase()
        self.win.insstr(0, 0, f"{self.prefix[self.checked]} {self.text}")
        self.win.move(0, 1)  # cursor always at the same position
        if self.checked:  # Change color to red / green when (un)checked
            self.win.bkgd(curses.color_pair(1))
        else:
            self.win.bkgd(curses.color_pair(2))
        self.win.refresh()

    def input(self, key: str | int):
        # when no char, then key is int and isspace() fails. Therefore check for str first, else shortcut.
        if isinstance(key, str) and (key.isspace() or (key in [" ", "\n", "\t", "x", "X"])):
            self.checked = not self.checked  # toggle button
        else:
            return key  # pass unhandled key to the event loop
        self.redraw()  # update changes on the screen
        return None  # key was handled properly


class channel_legend:  # Dummy class, just used as a flag
    pass


class button(movable):
    def __init__(self):
        super().__init__()
        self.win = curses.newwin(1, len(self.text), self.y, self.x)

    def activity(self):
        curses.curs_set(False)  # No blinking cursor
        self.win.erase()
        self.win.insstr(0, 0, self.text, curses.A_REVERSE)
        self.win.refresh()

    def redraw(self):
        self.win.erase()
        self.win.insstr(0, 0, self.text)
        self.win.refresh()

    def input(self, key: str | int):
        # when no char, then key is int and isspace() fails. Therefore check for str first, else shortcut.
        if isinstance(key, str) and (key.isspace() or (key in [" ", "\n", "\t"])):
            return self.trigger()
        elif isinstance(key, int) and (key in [curses.KEY_DOWN, curses.KEY_UP]):
            self.redraw()  # redraw when leaving the button to remove hover effect
            return key
        else:
            return key  # pass unhandled key to the event loop
        return None  # key was handled properly

    def trigger(self):
        # dummy function to be overwritten. This is the function that is called when the button is pressed
        raise RuntimeError("Button base class is not supposed to be triggered")


class save(button):
    def __init__(self):
        self.text = "< Save >"
        super().__init__()

    def trigger(self):
        return None  # TODO: implement the save dialog


class exit_button(button):
    def __init__(self):
        self.text = "< Exit >"
        super().__init__()

    def trigger(self):
        exit(0)  # Internally this is an exception with no corresponding text


class control:
    def __init__(self, y, x, height, width):
        # store metadata for later reuse
        self.x = x
        self.y = y
        self.height = height
        self.width = width

        # create a window for the control area
        self.win = curses.newwin(height, width, y, x)
        self.win.bkgd(curses.color_pair(0))  # clack and white
        self.win.erase()

        # Create input fields and active elements, display them later
        # X and Y positions are irrelevant because they are set later
        self.interactive = [
            ip_field := ip_input(),
            port_field := num_input(5, "3000"),
            refresh_checkbox := checkbox("Automatic Refresh", False),
            save(),
            exit_button(),
        ]

        # set up some shortcuts to the interactive elements
        self.ip_field = ip_field
        self.port_field = port_field
        self.refresh_checkbox = refresh_checkbox

        # now: specify the order of the texts and interactive elements
        self.content = [
            "IP Address:",
            self.interactive[0],
            "",
            "Port:",
            self.interactive[1],
            "",
            self.interactive[2],
            "",
            self.interactive[3],
            self.interactive[4],
            "",
            "",
            "Channels:",
            channel_legend(),  # not an interactive element but a more complex output
            "",  # This is just a shitty way to cope with the fact that the previous line is 2 lines long
        ]
        self.active = 0  # first element is the chosen one
        self.draw_win()

    def draw_win(self):  # no 'redraw', because there is no need to redraw this window frequently
        self.win.erase()
        # now draw all the texts and interactive elements
        for i in range(len(self.content)):
            if isinstance(self.content[i], str):
                # if it is a string, draw it
                self.win.addstr(i + 1, 1, self.content[i])
            elif isinstance(self.content[i], channel_legend):
                self.win.addstr(i + 1, 2, "CH1", curses.color_pair(2))
                self.win.addstr(i + 2, 2, "CH2", curses.color_pair(3))
                i += 1  # skip next line, last print were 2 lines
            else:
                # if it is an interactive element, put it into the right position
                self.content[i].move(self.y + i + 1, self.x + 2)

        # Refresh all the windows in the right order
        self.win.refresh()
        for i in self.interactive:
            i.redraw()
        self.interactive[self.active].redraw()  # redraw the active one at last
        self.interactive[self.active].activity()  # show or hide cursor on active field

    def move(self, new_y, new_x, new_height, new_width):
        self.y = new_y
        self.x = new_x
        self.width = new_width
        self.height = new_height
        self.win.resize(new_height, new_width)
        self.win.mvwin(new_y, new_x)
        self.draw_win()

    def input(self, key):  # Pass keys to the interactive elements or handle them here
        ret = self.interactive[self.active].input(key)
        match ret:
            case None:
                return None  # key was handled by the interactive element
            case curses.KEY_DOWN:
                self.active = min(len(self.interactive) - 1, self.active + 1)
                self.interactive[self.active].redraw()
                self.interactive[self.active].activity()
            case curses.KEY_UP:
                self.active = max(0, self.active - 1)
                self.interactive[self.active].redraw()
                self.interactive[self.active].activity()
            case _:
                return key  # return key to the event loop if not handled
        return None  # key was handled here successfully


def tui():
    try:
        # curse the terminal
        stdscr = curses.initscr()
        if curses.has_colors():
            curses.start_color()
        else:
            raise RuntimeError("Terminal does not support colors")
        curses.noecho()
        curses.cbreak()  # no line-buffering
        curses.curs_set(False)  # hide the cursor
        stdscr.keypad(1)  # activate escape sequences
        stdscr.erase()  # clear screen

        # set background color
        if curses.can_change_color():  # the default black might not be dark enough
            curses.init_color(curses.COLOR_BLACK, 0, 0, 0)
        stdscr.bkgd(curses.color_pair(0))  # 0 is always hard wired to black and white
        stdscr.refresh()

        # define two color pairs for red or green text on black background
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # green text
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)  # red text
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # yellow text

        height, width = stdscr.getmaxyx()  # get terminal window size

        # for more granularity: control the width of the control area via a parameter
        control_width = 25
        # plot area
        plot_obj = plot(1, 1, height - 2, width - control_width - 2, "Time (s)", "Voltage (V)")
        # control area
        control_obj = control(2, width - control_width - 1, height - 5, control_width)

        # create a timer for the event loop to trigger the automatic data capturing every second
        timer = time.time()  # start time for the timer
        while True:  # Event-loop
            # update timer
            time_new = time.time()

            # handle user input
            ret = control_obj.input(stdscr.get_wch())

            # handle a terminal resize event
            if ret == curses.KEY_RESIZE:
                # I hate this but this is the only way to make it work!
                # unfortunately curses needs minimally 2 attempts to resize the window properly
                # because the first time getmaxyx() returns the wrong size when maximizing.
                # This is caused by the terminal emulator which triggers the resize event but then needs to re-calculate the
                # new windows size a second time for the scroll bar (as far as I understood this problem from stackoverflow).
                # Therefore, the terminal size is smaller than reported and redrawing the windows fails because the terminal borders are exceeded.
                # First you need to trigger curses to refresh the screen metadata before this loop starts.
                # Without this sometimes the terminal returns the wrong sizes and
                # sometimes the plot is just not visible for no known reason.
                stdscr.erase()
                stdscr.refresh()
                height, width = stdscr.getmaxyx()
                # now try to repaint the plot and control area until it finally fits into the terminal window.
                while True:
                    try:
                        stdscr.erase()
                        stdscr.refresh()
                        height, width = stdscr.getmaxyx()
                        plot_obj.move(1, 1, height - 2, width - control_width - 2)
                        control_obj.move(2, width - control_width - 1, height - 5, control_width)
                        break
                    except curses.error:
                        pass

            # TODO: Event-Loop for handling the user input
            if control_obj.refresh_checkbox.checked and int(time_new - timer) > 0 and control_obj.ip_field.validate and control_obj.port_field.text.isdecimal():
                timer = time_new  # reset timer
                try:  # fetch data
                    data = decode.Dataset(capture.capture(
                        ipaddress.IPv4Address(control_obj.ip_field.text),
                        control_obj.port_field.text,
                    ))
                    plot_obj.update_data(data)
                except Exception:
                    plot_obj.data = None  # reset data on error
                finally:
                    plot_obj.redraw_win()
                    # control_obj.draw_win()

    except KeyboardInterrupt:  # CTRL+C
        exit(0)
    except Exception:
        Error = traceback.format_exc()
    finally:
        # reverse the curse
        curses.echo()
        curses.nocbreak()
        curses.curs_set(True)
        stdscr.clear()  # clear screen
        curses.endwin()

        # try to print the error message in case there is any
        try:
            print(Error)
        except NameError:
            pass


if __name__ == "__main__":
    tui()
