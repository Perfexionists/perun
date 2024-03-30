from prompt_toolkit import Application
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea

# Example log for demonstration
log_content = "2023-03-29 12:34:56:init:Log Initialized\n2023-03-29 12:35:00:process:Processing data\n"
current_line = 0  # Tracks the currently highlighted line


# Custom syntax highlighting
def get_colored_log(log):
    global current_line
    lines = log.split("\n")
    styled_lines = []
    for i, line in enumerate(lines):
        if i == current_line:
            # Apply a different background for the current line
            styled_lines.extend([("class:current_line", line + "\n")])
        else:
            styled_lines.extend(get_colored_log_line(line) + [("", "\n")])
    return styled_lines

def get_colored_log_line(line):
    parts = line.split(":")
    if len(parts) != 3:
        return [("class:text", line)]
    return [
        ("class:timestamp", parts[0]),
        ("class:text", ":"),
        ("class:function", parts[1]),
        ("class:text", ":"),
        ("class:event", parts[2]),
    ]

# Key bindings for the application
bindings = KeyBindings()


@bindings.add('c-c')
@bindings.add('c-q')
def _(event):
    " Quit application. "
    event.app.exit()


def process_command(buff):
    global current_line
    cmd = buff.text.strip().lower()
    max_line = len(log_content.split("\n")) - 1

    if cmd == "help":
        terminal.text = "Commands: help, next, prev"
    elif cmd == "next":
        current_line = min(current_line + 1, max_line)
    elif cmd == "prev":
        current_line = max(current_line - 1, 0)
    else:
        terminal.text = f"Unknown command: {cmd}"
    # Refresh log view to reflect changes
    log_view.content = FormattedTextControl(lambda: get_colored_log(log_content))
    buff.document = Document()  # Clear the terminal input after command execution


# Define the layout
log_view = Window(content=FormattedTextControl(lambda: get_colored_log(log_content)),
                  style="class:log_view")
state_view = Window(content=FormattedTextControl("State and Statistics will be here."),
                    style="class:state_view")
terminal = TextArea(prompt='> ', multiline=False, wrap_lines=False, accept_handler=process_command)
root_container = HSplit([
    VSplit([log_view, state_view]),
    terminal,
])


# Define styles
style = Style([
    ('log_view', 'bg:#073642 #839496'),
    ('state_view', 'bg:#002b36 #2aa198'),
    ('timestamp', 'bg:#073642 #268bd2'),
    ('function', 'bg:#073642 #859900'),
    ('event', 'bg:#073642 #cb4b16'),
    ('current_line', 'bg:#0044ff #ffffff'),
    ('text', ''),
])

# Create the application
application = Application(
    layout=Layout(root_container),
    key_bindings=bindings,
    style=style,
    full_screen=True)


if __name__ == '__main__':
    application.run()
