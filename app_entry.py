"""Entry point for the built HERO-TV.exe (made by Build-App.bat). Double-click = start the TV; any words after the
program name work like HERO-TV.bat does (HERO-TV.exe doctor, HERO-TV.exe convert movie.mkv, ...)."""
import sys

from herotv.__main__ import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["launch"]))
