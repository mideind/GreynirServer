# Reynir configuration file for ipython.

from platform import python_version, python_implementation

c.TerminalInteractiveShell.confirm_exit = False
c.InteractiveShellApp.exec_PYTHONSTARTUP = False

c.InteractiveShell.banner1 = "Python %s (%s)" % (python_version(), python_implementation())
c.InteractiveShell.banner2 = 'Welcome to the Greynir iPython shell!\n'

c.InteractiveShellApp.exec_lines = [
    'from scraperdb import *',
    's = SessionContext(commit=True).__enter__()',
]
