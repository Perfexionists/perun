"""External utils contains modules for manipulation with external subprocesses

In particular, it includes functions for working with:

  1. Processes: calling external processes or working with running processes;
  2. Environment: getting information about environment, where Perun was run (such as the Python version).
  3. Executables: getting information about executable files.
"""

import perun.utils.external.commands
import perun.utils.external.environment
import perun.utils.external.executable
import perun.utils.external.processes
