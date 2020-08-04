import os 
import sys 
from time import sleep





while True:
	print(os.path.abspath(__file__))
	print("oi")
	sleep(2)
	os.execv('/usr/bin/python3', [sys.argv[0],os.path.abspath(__file__)])
	print("tchau")
