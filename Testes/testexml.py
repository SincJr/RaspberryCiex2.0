import os 
import sys 
from time import sleep
import xml.etree.ElementTree as ET
rolo = '100x4,5'
rolocad = '3450'
qtdRolos = 10



fator = rolo.split("'")
fator = fator[0].replace(',', '.')
_, fator = fator.split('x')
calculada = round((float(rolocad)/float(fator))*qtdRolos)
print(calculada)
print(round(-1))