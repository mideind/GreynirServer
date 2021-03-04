# type: ignore
# Greynir configuration file for ipython.

from platform import python_version, python_implementation

c.TerminalInteractiveShell.confirm_exit = False
c.InteractiveShellApp.exec_PYTHONSTARTUP = False

c.InteractiveShell.banner1 = "Python %s (%s)" % (python_version(), python_implementation())
c.InteractiveShell.banner2 = 'Welcome to the Greynir IPython shell!\n'

c.InteractiveShellApp.extensions = ['autoreload']

c.InteractiveShellApp.exec_lines = [
    'from db import *',
    'from db.models import *',
    's = SessionContext(commit=False).__enter__()',
    'from reynir import Greynir',
    'g = Greynir()'
]
