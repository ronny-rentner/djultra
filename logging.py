import os
import shutil
import sys
from datetime import datetime

from rich.console import Console
from rich.highlighter import Highlighter, RegexHighlighter
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text
from rich.pretty import pretty_repr

from .middleware import RequestIDMiddleware

pretty = pretty_repr

class RainbowHighlighter(Highlighter):
    def highlight(self, text):
        for index in range(len(text)):
            text.stylize(f"color({randint(16, 255)})", index, index + 1)

class CustomHighlighter(RegexHighlighter):
    """Highlights the text typically produced from ``__repr__`` methods."""

    base_style = "repr."
    highlights = [
        r"^(?P<tag_start><)(?P<tag_name>[-\w.:|]*)(?P<tag_contents>[\w\W]*)(?P<tag_end>>)",
        #r'(?P<attrib_name>[\w_]{1,50})=(?P<attrib_value>"?[\w_]+"?)?',
        #r"(?P<brace>[][{}()])",
        '|'.join([
        #    r"(?P<ipv4>[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})",
        #    r"(?P<ipv6>([A-Fa-f0-9]{1,4}::?){1,7}[A-Fa-f0-9]{1,4})",
        #    r"(?P<eui64>(?:[0-9A-Fa-f]{1,2}-){7}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{1,2}:){7}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{4}\.){3}[0-9A-Fa-f]{4})",
        #    r"(?P<eui48>(?:[0-9A-Fa-f]{1,2}-){5}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2}|(?:[0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4})",
        #    r"(?P<uuid>[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})",
            #custom
            r"(?P<uuid>[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})",
        #    r"(?P<call>[\w.]*?)\(",
            r"\b(?P<bool_true>True)\b|\b(?P<bool_false>False)\b|\b(?P<none>None)\b",
        #    r"(?P<ellipsis>\.\.\.)",
        #    r"(?P<number_complex>(?<!\w)(?:\-?[0-9]+\.?[0-9]*(?:e[-+]?\d+?)?)(?:[-+](?:[0-9]+\.?[0-9]*(?:e[-+]?\d+)?))?j)",
        #    r"(?P<number>(?<!\w)\-?[0-9]+\.?[0-9]*(e[-+]?\d+?)?\b|0x[0-9a-fA-F]*)",
             #custom
            r"\b(?P<number>(0x[0-9a-fA-F]+|[0-9]+))\b",
        #    r"(?P<path>\B(/[-\w._+]+)*\/)(?P<filename>[-\w._+]*)?",
            r"(?<![\\\w])(?P<str>b?'''.*?(?<!\\)'''|b?'.*?(?<!\\)'|b?\"\"\".*?(?<!\\)\"\"\"|b?\".*?(?<!\\)\")",
        #    r"(?P<url>(file|https|http|ws|wss)://[-0-9a-zA-Z$_+!`(),.?/;:&=%#~@]*)",
        ]),
    ]


class CustomRichHandler(RichHandler):
    LEVEL_STYLES = {
        "DEBUG":    "dim white",
        "INFO":     "cyan",
        "WARNING":  "yellow",
        "ERROR":    "bold red",
        "CRITICAL": "bold underline red",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #self.console = Console()
        self.width = self.get_terminal_width()
        self.console = Console(file=sys.stdout, force_terminal=True, width=self.width)
        #self.highlighter = ReprHighlighter()
        self.highlighter = CustomHighlighter()
        self.markup = False
        self._log_render = self.custom_log_render
        self._last_time = None
        # TODO: There seems to be a bug in Rich and it adds a space for no reason
        self._time_column_width = 8


    def get_terminal_width(self):
        default_columns = int(os.getenv('DEFAULT_TERMINAL_COLUMNS', 80))  # Set a default or use environment variable
        try:
            terminal_size = shutil.get_terminal_size(fallback=(default_columns, 24))
            return terminal_size.columns
        except OSError:
            return default_columns

    def emit(self, record):
        current_time = datetime.fromtimestamp(record.created)
        request_id = RequestIDMiddleware.get_request_id()
        request_start_time = RequestIDMiddleware.get_request_start_time()

        if request_id is not None:
            if request_start_time is None:
                RequestIDMiddleware.set_request_start_time(current_time)
                record.relativeCreated = 0
            else:
                time_since_first_log = current_time - request_start_time
                record.relativeCreated = time_since_first_log.total_seconds() * 1000  # Convert to milliseconds
        else:
            record.relativeCreated = 0

        #print((not isinstance(record.msg, str)), ('%' not in record.msg), isinstance(record.args, tuple))
        #if ((not isinstance(record.msg, str)) or ('%' not in record.msg)) and isinstance(record.args, tuple):

        #Why does it have to be a tuple?
        if ((not isinstance(record.msg, str)) or ('%' not in record.msg)): # and isinstance(record.args, tuple):
            if isinstance(record.args, tuple):
                # TODO: Why are lists wrapped in a tuple?
                if len(record.args) == 1 and isinstance(record.args[0], list):
                    record.msg = f'{record.msg}{pretty(record.args[0])}'
                else:
                    record.msg = str(record.msg) + ' '.join(map(str, record.args))
            else:
                #record.msg = f'{record.msg} {pretty(record.args, expand_all=True)}'
                record.msg = f'{record.msg} {pretty(record.args)}'
            #record.msg = f'{record.msg} {pretty(record.args, expand_all=True)}'
            record.args = ()  # Clear args to avoid further formatting issues

        super().emit(record)

    def custom_log_render(self, record, traceback, message_renderable, time_format=None, level_width=None, omit_path=False, link_path=False):
        log_time = datetime.fromtimestamp(record.created)
        log_time_highlight = True
        if not RequestIDMiddleware.is_first_log_message() or record.relativeCreated == 0:
            if self.formatter:
                time_display = self.formatter.formatTime(record, self.formatter.datefmt)
            else:
                time_display = log_time.strftime('%Y-%m-%d %H:%M:%S')
            #self._time_column_width = len(time_display.strip())
            RequestIDMiddleware.set_first_log_message_sent()
        else:
            time_display = f"+{record.relativeCreated:.0f}ms"
            log_time_highlight = False

        time = Text(time_display)
        level = self.get_level_text(record)

        table = Table.grid(padding=(0, 1))
        table.expand = True
        table.add_column(style="log.time", width=self._time_column_width, justify="right")
        table.add_column(style="log.level", width=8)
        table.add_column(ratio=1, style="log.message", overflow="fold")

        if not traceback:
            table.add_column(style="log.path")

        row = []
        if log_time_highlight:
            row.append(f"[b]{time}[/b]")
        else:
            if time == self._last_time:
                row.append("" + (" " * self._time_column_width))
            else:
                row.append(f"{time}")

        self._last_time = time
        row.append(level)

        if traceback:
            row.append(traceback)
        else:
            #row.append(self.highlighter(message_renderable))
            row.append(self.highlighter(message_renderable))

            path_text = Text()
            path_text.append(f"{record.name}:{record.lineno}",
                             style=f"link file://{record.pathname}#{record.lineno}" if record.pathname else "")

            row.append(path_text)

        table.add_row(*row)

        return table

    def get_level_text(self, record):
        level_text = Text(record.levelname)
        style = self.LEVEL_STYLES.get(record.levelname, "log.level")
        level_text.stylize(style)
        return level_text

    def render(self, *, record, traceback, message_renderable):
        message_renderable = str(message_renderable).strip()
        if message_renderable == '':
            return ''
        plain_message = Text(message_renderable)
        log_table = self._log_render(record, None, plain_message)
        if traceback:
            grid = Table.grid(expand=True)
            grid.add_column()
            grid.add_row(log_table)
            grid.add_row(self._log_render(record, traceback, message_renderable))
            return grid

        return log_table

    #def _log(self, level, msg, args, **kwargs):
    #    print('LOG!!!')
    #    msg = ' '.join(map(str, (msg,) + args))
    #    super()._log(level, msg, (), **kwargs)

    #def debug(self, *args, **kwargs):
    #    print('DEBUG!!!')
    #    self._log(logging.DEBUG, args[0], args[1:], **kwargs)
