import sys
try:
    import gui
    print("gui imports OK", file=sys.stderr)
except Exception as e:
    import traceback
    with open("gui_error.txt", "w") as f:
        traceback.print_exc(file=f)
    print("ERROR: see gui_error.txt")