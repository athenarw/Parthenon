# build123d example
from build123d import *
from ocp_vscode import *
import time
 
box = Box(1, 2, 3)
cylinder = Cylinder(0.5, 2)

# Deubg
print(f"Box: {box}")
print(f"Cylinder: {cylinder}")
show(box, cylinder)

time.sleep(15)