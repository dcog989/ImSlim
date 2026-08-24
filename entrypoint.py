"""PyInstaller entry point (see imslim.spec).

Kept free of relative imports so it can be executed as ``__main__`` by the
frozen bootloader.
"""

from imslim.main import main

if __name__ == "__main__":
    main()
