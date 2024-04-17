"""logdb (log debugger) is helper prompt script for going through the logs of ktrace"""
from __future__ import annotations

# Standard Imports
from typing import Optional, TextIO
from dataclasses import dataclass
import io
import sys

# Third-Party Imports
import tabulate
from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyPressEvent
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea, Frame

# Perun Imports

NS_TO_MS = 1000000


class BufferedLog:
    """Buffered Log reads file on the fly keeping it open and returning lines on demand.

    :ivar file_path: path to the file
    :ivar block_size: size of one read block
    :ivar current_position: current position in the log
    :ivar end_position: last position in the file
    :ivar file: opened file
    """
    def __init__(self, file_path: str, block_size: int = 1024):
        """Initializes the buffered log

        :param file_path: path to the file
        :param block_size: size of the read block
        """
        self.file_path: str = file_path
        self.block_size: int = block_size
        self.current_position: int = 0
        self.end_position: int = 0
        self.file: Optional[TextIO] = None

    def __enter__(self) -> BufferedLog:
        """Entering the context

        File is opened, and we infer the start and ending position
        """
        self.file = open(self.file_path, "r", encoding="utf-8")
        self.file.seek(0, io.SEEK_END)
        self.end_position = self.file.tell()
        self.file.seek(0)
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: BaseException) -> None:
        """Closes the file"""
        self.file.close()

    def read_next_line(self) -> str:
        """Reads the next line in the log

        :return: next line in the buffer
        """
        if self.current_position >= self.end_position:
            return ""
        self.file.seek(self.current_position)
        line = self.file.readline()
        self.current_position = self.file.tell()
        return line.strip()

    def read_previous_line(self) -> str:
        """Reads the previous line in log

        :return: previous line in the buffer
        """
        block = ""
        while self.current_position > 0:
            to_read = min(self.block_size, self.current_position)
            self.file.seek(self.current_position - to_read)
            block += self.file.read(to_read)
            self.current_position -= to_read
            if "\n" in block:
                lines = block.split("\n")
                if len(lines) < 3:
                    continue
                last_full_line = lines[-2]
                self.current_position += (
                    sum(len(line) + 1 for line in lines[:-2]) + len(lines[-2]) + 1
                )
                self.file.seek(self.current_position)
                return last_full_line.strip()
        return block.strip()

    def get_current_position(self) -> int:
        """Returns the current position in the log
        """
        return self.file.tell()

    def move_current_position(self, position: int) -> None:
        """Moves position in the log

        :param position: new position in the log
        """
        self.current_position = position
        self.file.seek(position)

    def close(self):
        """Closes the buffered log"""
        self.file.close()


@dataclass
class Event:
    """Event represents a single line in the log

    :ivar timestamp: timestamp of the event
    :ivar event: type of the event (either call or return)
    :ivar tid: thread id
    :ivar pid: process id
    :ivar uid: uid of the event (function)
    """
    timestamp: int
    event: str
    tid: int
    pid: int
    uid: str

    @classmethod
    def from_line(cls, line: str) -> "Event":
        """Parses the event from single line

        :param line: line from the log
        :return: parsed event
        """
        parts = line.split(":")
        ts, evt = parts[0], parts[-1]
        middle_parts = parts[2].split(')(')
        tid, pid, uid = middle_parts[0], parts[1][1:], middle_parts[1][:-1]
        return Event(int(ts), evt, int(tid), int(pid), uid)


def singleton_class(cls):
    """Helper class for creating singleton objects"""
    instances = {}

    def getinstance() -> object:
        """Singleton instance"""
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance


@singleton_class
class State:
    """Represents single state of the run

    :ivar current_line: currently highlighted line in the log
    :ivar real_line: real number in the log
    :ivar buffered_log: instance of buffered log
    :ivar last_command: last executed command
    :ivar current_timestamp: current timestamp in the log
    :ivar first_timestamp: first timestamp in the log
    :ivar stack: stack of the calls
    """
    def __init__(self):
        self.current_line: int = 0  # Tracks the currently highlighted line
        self.real_line: int = 0
        self.buffered_log: Optional[BufferedLog] = None
        self.last_command = ""
        self.current_timestamp = 0
        self.first_timestamp = 0
        self.stack = []

        self._log_content: list[str] = []
        self._buffer_positions: list[int] = []
        self._buffer_size: int = 25
        self._buffer_log_start: int = 0
        self._buffer_log_end: int = 0

    def get_content(self) -> list[str]:
        """Returns current content of the log"""
        return self._log_content

    def init_buffer(self, buffered_log: BufferedLog):
        """Initializes the buffer from buffered log.

        :param buffered_log: buffered log
        """
        self.buffered_log: BufferedLog = buffered_log
        self._buffer_log_start = 0
        for i in range(0, self._buffer_size):
            self._log_content.append(self.buffered_log.read_next_line())
            self._buffer_positions.append(self.buffered_log.get_current_position())
        self.first_timestamp = int(self._log_content[0].split(":")[0])
        self.current_timestamp = self.first_timestamp
        self._buffer_log_end = self.buffered_log.get_current_position()

    def move_window_forward(self) -> None:
        """Moves window forward by one line"""
        self.real_line += 1
        if self.current_line <= (self._buffer_size - 6):
            self.current_line = min(self.current_line + 1, self._buffer_size)
            return

        self._log_content = self._log_content[1:]
        self.buffered_log.move_current_position(self._buffer_log_end)
        line = self.buffered_log.read_next_line()
        self._log_content.append(line)

        self._buffer_log_start = self._buffer_positions[0]
        self._buffer_log_end = self.buffered_log.get_current_position()
        self._buffer_positions = self._buffer_positions[1:] + [self._buffer_log_end]

    def move_window_backward(self) -> None:
        """Moves window back by one line"""
        self.real_line = max(self.real_line - 1, 0)
        if self.current_line > 5 or self.real_line <= 5:
            self.current_line = max(self.current_line - 1, 0)
            return

        self._log_content = self._log_content[:-1]
        self.buffered_log.move_current_position(self._buffer_log_start)
        line = self.buffered_log.read_previous_line()
        self._log_content = [line] + self._log_content

        self._buffer_log_start = self.buffered_log.get_current_position() - len(line) + 1
        self._buffer_log_end = self._buffer_positions[-1]
        self._buffer_positions = [self._buffer_log_start] + self._buffer_positions[:-1]

    def process_event(self) -> None:
        """Processes next event"""
        event = Event.from_line(self._log_content[self.current_line])
        self.current_timestamp = int(event.timestamp)
        if event.event == "call":
            self.stack.append(event.uid)
        else:
            self.stack.pop()

    def undo_event(self) -> None:
        """Undo current event"""
        event = Event.from_line(self._log_content[self.current_line])
        self.current_timestamp = int(event.timestamp)
        if event.event == "call":
            self.stack.pop()
        else:
            self.stack.append(event.uid)


# Custom syntax highlighting
def get_colored_log() -> list[tuple[str, str]]:
    """Returns coloured contents"""
    current_state: State = State()
    styled_lines = []
    for i, line in enumerate(current_state.get_content()):
        if i == current_state.current_line:
            # Apply a different background for the current line
            styled_lines.extend([("class:current_line", line + "\n")])
        else:
            styled_lines.extend(get_colored_log_line(line) + [("", "\n")])
    return styled_lines


def get_colored_log_line(line: str) -> list[tuple[str, str]]:
    """Returns colored line

    :param line: current line
    """
    event = Event.from_line(line)
    return [
        ("class:timestamp", str(event.timestamp)),
        ("class:text", ":("),
        ("class:pid", str(event.pid)),
        ("class:text", ":"),
        ("class:tid", str(event.tid)),
        ("class:text", ")("),
        ("class:function", event.uid),
        ("class:text", "):"),
        (f"class:{event.event}", event.event),
    ]


# Key bindings for the application
bindings = KeyBindings()


@bindings.add("c-c")
@bindings.add("c-q")
def _(event: KeyPressEvent) -> None:
    """Quit application."""
    event.app.exit()


def format_time(time: int) -> str:
    """Formats time

    :param time: formatted time
    """
    if time < NS_TO_MS:
        return f"{time / NS_TO_MS:.2f}ms"
    else:
        minutes, milliseconds = divmod(int(time / NS_TO_MS), 60)
        seconds, milliseconds = divmod(milliseconds, 1000)
        return f"{minutes:02d}:{seconds:02d}.{milliseconds:d}"


def get_stats() -> str:
    """Returns statistics for current state"""
    current_state: State = State()
    data = [
        ["current event", f"{current_state.real_line}"],
        ["current time", f"{format_time(current_state.current_timestamp - current_state.first_timestamp)}"],
    ]
    return tabulate.tabulate(data, headers=[], tablefmt="presto")

def get_stack() -> list[tuple[str, str]]:
    """Returns formatted stack"""
    current_state: State = State()
    lines = []
    for f in current_state.stack[::-1]:
        lines.extend([("class:function", f), ("", "\n")])
    return lines


def create_app(buffered_log: BufferedLog) -> Application:
    """Creates apllication for given buffered log

    :param buffered_log: buffered log
    """
    current_state: State = State()
    current_state.init_buffer(buffered_log)

    def process_command(buff):
        current_state: State = State()
        cmd = buff.text.strip().lower()

        if cmd == "":
            cmd = current_state.last_command

        if cmd == "help":
            terminal.text = "Commands: help, next, prev"
        elif cmd in ("next", "n", "j"):
            current_state.process_event()
            current_state.move_window_forward()
        elif cmd in ("prev", "p", "k"):
            current_state.move_window_backward()
            current_state.undo_event()
        elif cmd in ("quit", "exit", "q"):
            app.exit()
        else:
            terminal.text = f"Unknown command: {cmd}"
        current_state.last_command = cmd
        # Refresh log view to reflect changes
        log_view.content = FormattedTextControl(get_colored_log)
        buff.document = Document()  # Clear the terminal input after command execution
        return True

    # Define the layout
    stack_view = Frame(title="Stack", body=Window(content=FormattedTextControl(get_stack)))
    counter_view = Frame(title="Stats", body=Window(content=FormattedTextControl(get_stats)))
    log_view = Frame(title="Log", body=Window(content=FormattedTextControl(get_colored_log)))
    state_view = Frame(
        title="State",
        body=HSplit([stack_view, counter_view]),
    )
    terminal = TextArea(
        prompt="> ", multiline=False, wrap_lines=False, accept_handler=process_command
    )
    root_container = HSplit(
        [
            VSplit([log_view, state_view]),
            terminal,
        ]
    )

    # Define styles
    style = Style(
        [
            ("timestamp", "#ff595e"),
            ("tid", "#ff924c"),
            ("pid", "#ffca3a"),
            ("function", "#8ac926"),
            ("call", "#1982c4"),
            ("return", "#6a4c93"),
            ("current_line", "bg:#0044ff #ffffff"),
            ("text", ""),
        ]
    )

    # Create the application
    app = Application(
        layout=Layout(root_container), key_bindings=bindings, style=style, full_screen=True
    )
    return app


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: ./logdb.py <LOG>.log")
        sys.exit(1)
    with BufferedLog(sys.argv[1]) as buffered_log:
        application = create_app(buffered_log)
        application.run()
