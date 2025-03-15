import sys
import json

if len(sys.argv) > 1:

    fname = sys.argv[1]
    lname = sys.argv[2]

    # Print JSON output
    print(f"{fname}  {lname}")