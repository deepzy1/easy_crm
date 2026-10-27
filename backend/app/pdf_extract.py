"""Internal POSIX child-process limits before execing Poppler (never a web endpoint)."""

import os
import resource
import sys

if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024, 64 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    # Child limits avoid preexec_fn, which is unsafe in threaded web servers.
    os.execvp(
        "pdftotext",
        ["pdftotext", "-f", "1", "-l", "30", "-enc", "UTF-8", "-nopgbrk", sys.argv[1], sys.argv[2]],
    )
