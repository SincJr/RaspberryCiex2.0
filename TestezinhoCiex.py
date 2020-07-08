import socket
import os
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from threading import Thread
import time
from datetime import datetime, timedelta
import serial
import struct
import subprocess
from gpiozero import Button

#
#Constantes
#
NEXTION_TELA = 1


PORTA_BASE_PADRAO = 32000
MAQUINA = 3
PORT = PORTA_BASE_PADRAO + MAQUINA

#
#Declaracao dos pinos
#
ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate =9600,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
    )
        
ff = struct.pack('B', 0xff)

fimDeCurso = Button(INTERRUPT_PIN, pull_up=True, bounce_time=300)



#
#Variaveis dos arquivos xml
#
file_config = 'ConfigM.xml'
file_prod = 'producao.xml'
file_paradas = 'paradas.xml'

full_file = os.path.abspath(os.path.join('data'))
arq_config = os.path.abspath(os.path.join('data', file_config))
arq_parada = os.path.abspath(os.path.join('data', file_paradas))
arq_prod = os.path.abspath(os.path.join('data', file_prod))

#
#Variaveis Normais
#
dictOperadores = {}
dia, mes, ano, hora, minuto = 0
op = ''
lote = ''
operador = ''
meta = ''
rolos = {1:'25x10', 2:'25:09', 3:'25x45'}  #mudar esses numeros conforme ID do nextion

idProd = 0
idParada = 0

flagParada = False
flagProd = False


class Server(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
    def run(self):
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1 )
                HOST = socket.gethostname()
                sock.bind((HOST, PORT))
                sock.listen()

                client, addr = sock.accept()

                with client:
                    print('Connectado a', addr)
                    btipo = client.recv(1)
                    tipo = btipo.decode("utf-8")
                    if btipo is 'c' or 'p':  # c = config (ou seja, receber info de maquina), p = prod/paradas (ou seja, enviar xmls)
                        client.send(btipo)     # echo
                        if tipo is 'c':
                            stream = client.recv(1024000)
                            root = ET.fromstring(stream)
                            with open(arq_config,'w') as arq:
                                arq.write(ET.tostring(root).decode())
                        else:
                            xmlStream = ET.parse(arq_parada)
                            xmlstr = ET.tostring(xmlStream.getroot()).decode()
                            client.send(bytes(xmlstr, "utf-8"))

                            xmlStream = ET.parse(arq_prod)
                            xmlstr = ET.tostring(xmlStream.getroot()).decode()
                            client.send(bytes(xmlstr, "utf-8"))
                    else:
                        print('Erro!')
                

class TimeRTC(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
    def run(self):
        while True:
            startTempo2min = datetime.now()
            while datetime.now() - startTempo2min < timedelta(minutes=2):
                
                startTempo = datetime.now()
                while datetime.now() - startTempo < timedelta(seconds=.1):
                    pass

                if produzindo:
                    atualizarNextion(True)
            
            if produzindo or parada:
                atualizarXml(flagProd, flagParada)


        
    def pegarHora(self):
        now = datetime.now()
        second = '{:02d}'.format(now.second)
        second = str(second)
        minute = '{:02d}'.format(now.minute)
        minute = str(minute)
        hour = '{:02d}'.format(now.hour)
        hour = str(hour)

        return hour, minute, second
         

def FuncInterrupt():

    producao += 1
    flagProd = True

    if produzindo is False:
        enviar('page pProduzindo', False, False)
        produzindo = True
        parada = False
        duracaoParada = 0
        
    
def enviar(varNextion, msgEnviar, texto = True):
    
    varNextion = bytes(varNextion, encoding='iso-8859-1')
    ser.write(varNextion)

    if msgEnviar:
        msgEnviar = bytes('"'+str(msgEnviar)+'"', encoding='iso-8859-1')
        ser.write(msgEnviar)
    
    ser.write(ff+ff+ff)


def receberInfo(tipo):
    while True:
        msgSerial = ser.readlines()
        if msgSerial:
            for linha in msgRecebida:
                _, hexRecebido, _ = str(linha).split("'")
                hexRecebido = hexRecebido.replace('\\xff\\xff\\xff', '')
                hexDesejado = hexRecebido.split('\\x')
                
                break
        break
   
    if tipo is QUERO_TELA:
        return hexDesejado[1], hexDesejado[2]
    if tipo is QUERO_TUDO:
        return hexDesejado


def pegarOperadores():
    xmlConfig = minidom.parse(arq_config)

    listaOperadoresXml = xmlConfig.getElementsByTagName('operador')

    listaOperadores = {}

    for index, nomeOperador  in enumerate(listaOperadoresXml):
        listaOperadores[index + 1] = nomeOperador     # esse mais 1 depende das ids dos botoes no nextion

    return listaOperadores


def atualizarNextion(soHora = False):
    if not soHora:
        enviar('tOP.txt', op)
        enviar('tLote.txt', lote)
        enviar('tOperador.txt', operador)
        enviar('tRolo.txt', rolo)
        enviar('tMeta.txt', meta)
    enviar('tData.txt', data.strftime('%d/%m/%Y'))
    enviar('tHora.txt', horario.strftime('%H:%M'))
  
    
def atualizarXml(atualizarProd, atualizarParada):
    if atualiizarProd:
        xmlProducoes = ET.parse(arq_prod)
        rootProducoes = xmlProducoes.getroot()

        for tipo, valor in dictXmlProd.items():
            xmlProd = rootProducoes.find('./producoesM' + str(MAQUINA) + '/producao[@id="'+ str(idProd) +'"]/' + tipo)
            xmlProd.text = dicti[tipo]
        xmlProducoes.write(arq_prod)

    if atualizarParada:
        xmlParadas = ET.parse(arq_parada)
        rootParadas = xmlParadas.getroot()

        for tipo, valor in dictXmlParada.items():
            xmlParada = rootParadas.find('./paradasM' + str(MAQUINA) + '/parada[@id="'+ str(idParada) +'"]/' + tipo)
            xmlParada.text = dicti[tipo]
        xmlParadas.write(arq_parada)


DESLIGAR = 1 #Colocar aqui ID do botão "Sim" na tela de desligar

ID_PAG = 0
ID_OK = 6 #definir ID do botao do OK do Nextion


QUERO_TELA = 1
QUERO_TUDO = 2

T_DATAHORA = 1
T_AJUSTAR = 2
T_OP = 3
T_LOTE = 4
T_METsemAD = 5
T_METcomAD = 6
T_OPERADOR = 7
T_ROLO = 8
T_META = 9
T_PRODUZINDO = 10
T_PARADAS = 11
T_VOLTAR = 12
T_DESLIGAR = 13

Server()
TimeRTC()

fimDeCurso.when_pressed = FuncInterrupt

while True:

    sinalTela, botaoApertado = receberInfo(QUERO_TELA)

    if sinalTela is T_DATAHORA or T_AJUSTAR:
        if botaoApertado is ID_PAG:
            enviar("tData", '/'.join(TimeRTC.pegarHora()))
        else:
            _, dia, _, mes, _, ano = receberInfo(QUERO_TUDO)
            _, hora, _, minuto =  receberInfo(QUERO_TUDO)
            data = datetime(ano, mes, dia)
            horario = datetime(hora, minuto)

    if sinalTela is T_OP and botaoApertado is ID_OK:
        _, *op = receberInfo(QUERO_TUDO)
        op = ''.join(op)

    if sinalTela is T_LOTE and botaoApertado is ID_OK:
        _, *lote = receberInfo(QUERO_TUDO)
        lote = ''.join(lote)

    if sinalTela is T_METsemAD and botaoApertado is ID_OK:
        _, *metSemAd = receberInfo(QUERO_TUDO)
        metaSemdAd = ''.join(metaSemdAd)

    if sinalTela is T_METcomAD and botaoApertado is ID_OK:
        _, *metComAd = receberInfo(QUERO_TUDO)
        metComAd = ''.join(metComAd)

    if sinalTela is T_OPERADOR:
        if botaoApertado is ID_PAG:
            dictOpeadores = pegarOperadores()
            for idOperador, nomeOperador in dictOperadores.items():   #acrescentar logica pra pagina dois
                variavelNextion = "tOperador" + str(idOperador) + '.txt'
                enviar(variavelNextion, nomeOperador)
        else:
            idOperador = botaoApertado #cuidado que tem que ver qual numero tem que ser somado/subtraido conforme as ID dos botoes da tela
            operador = dictOperadores[idOperador]


    if sinalTela is T_ROLO and botaoApertado is not ID_PAG:
        rolo = rolos[botaoApertado] #cuidado que tem que ver qual numero tem que ser somado/subtraido conforme as ID dos botoes da tela

    if sinalTela is T_META:
        if botaoApertado is ID_PAG:
            enviar(calcularMeta(), 'tMeta.txt')
        if botaoApertado is ID_OK:
            _, *meta = receberInfo(QUERO_TUDO)
            meta = ''.join(meta)

    if sinalTela is T_PRODUZINDO:
        if botaoApertado is ID_PAG:
            atualizarNextion()


    if sinalTela is T_PARADAS:
        idParada = botaoApertado

    if sinalTela is T_DESLIGAR:
        if botaoApertado is DESLIGAR:
            atualizarValores()
            subprocess.Popen(['sudo','shutdown','-h','now'])

