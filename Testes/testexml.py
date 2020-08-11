import os 
import sys 
from time import sleep
import xml.etree.ElementTree as ET
file_config = 'ConfigM.xml'
file_prod = 'producao.xml'
file_paradas = 'paradas.xml'

full_file = os.path.abspath(os.path.join('data'))
arq_config = os.path.abspath(os.path.join(full_file, file_config))
arq_parada = os.path.abspath(os.path.join(full_file, file_paradas))
arq_prod = os.path.abspath(os.path.join(full_file, file_prod))


xml = ET.parse(arq_config)
raiz = xml.getroot()

for coisa in raiz.findall('./operadores'):
	if not coisa:
		print("Tem nada parceiro")
	else:
		print('deu bom')