import socket
import os
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from threading import Thread
import time
import serial
from datetime import datetime, timedelta
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

SEM_TIPO_PARADA = 'Não informada'

DESLIGAR = 1 #Colocar aqui ID do botão "Sim" na tela de desligar

ID_PAG = 0
ID_OK = 4 #definir ID do botao do OK do Nextion


QUERO_TELA = 1
QUERO_TUDO = 2

T_INICIAL = 0
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
T_NOVAPROD
T_DESLIGAR = 14


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
producao = 0
dictOperadores = {}
dictParadas = {}
dia, mes, ano, hora, minuto = 0
op = ''
lote = ''
operador = ''
meta = ''
rolos = {1:'25x10', 2:'25:09', 3:'25x45'}  #mudar esses numeros conforme ID do nextion
dictXmlProd = {'lote':'', 'op':'', 'inicio':'', 'fim':'', 'maquina':str(MAQUINA), 'operador':'', 'eixo':'', 'meta':'', 'qtd':'', 'rolosad':'', 'rolocad':''}
dictXmlParada = {'data':'', 'lote':'', 'op':'', 'tipo':'', 'maquina':str(MAQUINA), 'operador':'', 'duracao':''}

timerAFK = False

idProd = ''
idParada = ''

flagParada = False
flagProd = False
atualizarParada = False
atualizarProd = False

sinalTela = T_INICIAL


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
                

class Clock(Thread):
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
                if sinalTela is T_DATAHORA:
                    atualizarNextion(True)
                if produzindo:
                    atualizarNextion(True, True)

            if produzindo or parada:
                atualizarXml(flagProd, flagParada)
                

        
    def pegarHoraRTC(self):
        now = datetime.now()
        second = '{:02d}'.format(now.second)
        second = str(second)
        minute = '{:02d}'.format(now.minute)
        minute = str(minute)
        hour = '{:02d}'.format(now.hour)
        hour = str(hour)

        return hour, minute, second

    def pegarDataRTC(self):
        now = datetime.now()
        day = '{:02d}'.format(now.day)
        day = str(day)
        month = '{:02d}'.format(now.month)
        month = str(month)
        year = '{:02d}'.format(now.year)
        year = str(year)
         
        return day, month, year


class DetectaAFK(Thread):
    def __init__(self):
        self.__init__(Thread)
        self.daemon = True
        self.start()

    def run(self):
        startTempo = datetime.now()
        flagAFK = True
        timerAFK = True
        while datetime.now() - startTempo < timedelta(minutes=2):
            if not timerAFK:
                timerAFK = True
                flagAFK = False
                break
        if flagAFK:
            enviar('page pParada', False, False) 


def FuncInterrupt():

    producao += 1
    flagProd = True
    timerAFK = False

    if producao >= meta:
        enviar('page pNovaProd', False, False)


    if produzindo is False:
        enviar('page pProduzindo', False, False)

        produzindo = True
        parada = False

        dictXmlParada['tipo'] = SEM_TIPO_PARADA
        dictXmlParada['duracao'] = (datetime.isoformat(datetime.now().replace(microsecond=0)) - dictXmlParada['data']).total_seconds
    
    
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


def pegarParadas():
    xmlConfig = minidom.parse(arq_config)

    listaParadasXml = xmlConfig.getElementsByTagName('parada')

    listaParadas = {}

    for index, nomeParada in enumerate(listaParadasXml):
        listaParadas[index + 1] = nomeParada     # esse mais 1 depende das ids dos botoes no nextion

    return listaParadas


def atualizarNextion(soHora = False, barra=False):
    if not soHora:
        enviar('tOP.txt', op)
        enviar('tLote.txt', lote)
        enviar('tOperador.txt', operador)
        enviar('tRolo.txt', rolo)
        enviar('tMeta.txt', meta)
    
    if barra:
        enviar("tProgresso", str(progressoMeta()))

    enviar("tData", '/'.join(Clock.pegarDiaRTC))
    enviar("tHora", ':'.join(Clock.pegarHoraRTC()))
    
def atualizarXml(atualizarProd, atualizarParada):
    if atualiizarProd:
        xmlProducoes = ET.parse(arq_prod)
        rootProducoes = xmlProducoes.getroot()

        for tipo, valor in dictXmlProd.items():
            xmlProd = rootProducoes.find('./producoesM' + str(MAQUINA) + '/producao[@id="'+ idProd +'"]/' + tipo)
            xmlProd.text = dictXmlProd[tipo]
        xmlProducoes.write(arq_prod)

    if atualizarParada:
        xmlParadas = ET.parse(arq_parada)
        rootParadas = xmlParadas.getroot()

        for tipo, valor in dictXmlParada.items():
            xmlParada = rootParadas.find('./paradasM' + str(MAQUINA) + '/parada[@id="'+ idParada +'"]/' + tipo)
            xmlParada.text = dictXmlParada[tipo]
        xmlParadas.write(arq_parada)


def gerarXmlProd():
    xmlProd = ET.parse(arq_prod)
    xmlProdRaiz = xmlProd.getroot()

    for prodFeita in xmlProdRaiz.findall('./producoesM' + str(MAQUINA) + '/producao'):
        idProd = prodFeita.get('id')

    idProd = str(int(idProd) + 1)

    xmlProdRaiz = xmlProdRaiz.find('./producoesM' + str(MAQUINA) + '/producao[@id="'+ idProd +'"]')

    ET.SubElement(xmlProdRaiz, 'lote')
    ET.SubElement(xmlProdRaiz, 'op')
    ET.SubElement(xmlProdRaiz, 'inicio')
    ET.SubElement(xmlProdRaiz, 'fim')
    ET.SubElement(xmlProdRaiz, 'maquina')
    ET.SubElement(xmlProdRaiz, 'operador')
    ET.SubElement(xmlProdRaiz, 'eixo')
    ET.SubElement(xmlProdRaiz, 'meta')
    ET.SubElement(xmlProdRaiz, 'qtd')
    ET.SubElement(xmlProdRaiz, 'rolosad')
    ET.SubElement(xmlProdRaiz, 'rolocad')

    xmlProd.write(arq_prod)


def gerarXmlParada():
    xmlParada = ET.parse(arq_parada)
    xmlParadaRaiz = xmlParada.getroot()

    for paradaFeita in xmlParadaRaiz.findall('./paradasM' + str(MAQUINA) + '/parada'):
        idParada = paradaFeita.get('id')

    idParada = str(int(idParada) + 1)

    xmlParadaRaiz = xmlParadaRaiz.find('./paradasM' + str(MAQUINA) + '/parada[@id="'+ idParada +'"]')

    ET.SubElement(xmlParadaRaiz, 'data')
    ET.SubElement(xmlParadaRaiz, 'lote')
    ET.SubElement(xmlParadaRaiz, 'op')
    ET.SubElement(xmlParadaRaiz, 'tipo')
    ET.SubElement(xmlParadaRaiz, 'maquina')
    ET.SubElement(xmlParadaRaiz, 'operador')
    ET.SubElement(xmlParadaRaiz, 'duracao')


    xmlParada.write(arq_parada)


def calculaMeta():
    if rolo is '25x10':
        calculada = metComAd * 4
    elif rolo is '25x09':
        calculada = (metComAd/10000) * 45.4545 
    elif rolo is '25x45':
        calculada = (metComAd/10000) * 9.0909

    return calculada


def progressoMeta():

    return int((producao * 100)/meta)


Server()
Clock()
DetectaAFK()

fimDeCurso.when_pressed = FuncInterrupt

while True:

    sinalTela, botaoApertado = receberInfo(QUERO_TELA)

    if sinalTela is T_INICIAL:
        primeiro = True
        produzindo = False
        parada = False
        producao = 0

    elif sinalTela is T_DATAHORA or T_AJUSTAR:
        if botaoApertado is ID_PAG:
            atualizarNextion(True)
        elif sinalTela is T_AJUSTAR and botaoApertado is ID_OK:
            _, hora, _, minuto, _, segundo = receberInfo(QUERO_TUDO)
            _, dia, _, mes, _, ano = receberInfo(QUERO_TUDO)

            dataNova = datetime(ano, mes, dia, hora, minuto, segundo)
            dataNova = dataNova.strftime('%Y-%m-%d %H:%M:%S')

            subprocess.Popen(['sudo','date','-s', dataNova])
       

    elif sinalTela is T_OP and botaoApertado is ID_OK:
        _, *op = receberInfo(QUERO_TUDO)
        op = ''.join(op)
        dictXmlProd['op'] = op
        dictXmlParada['op'] = op

    elif sinalTela is T_LOTE and botaoApertado is ID_OK:
        _, *lote = receberInfo(QUERO_TUDO)
        lote = ''.join(lote)
        dictXmlProd['lote'] = lote
        dictXmlParada['lote'] = lote

    elif sinalTela is T_METsemAD and botaoApertado is ID_OK:
        _, *metSemAd = receberInfo(QUERO_TUDO)
        metaSemdAd = ''.join(metaSemdAd)
        dictXmlProd['rolosad'] = metSemAd

    elif sinalTela is T_METcomAD and botaoApertado is ID_OK:
        _, *metComAd = receberInfo(QUERO_TUDO)
        metComAd = ''.join(metComAd)
        dictXmlProd['rolocad'] = metComAd

    elif sinalTela is T_OPERADOR:
        if botaoApertado is ID_PAG:
            dictOpeadores = pegarOperadores()
            for idOperador, nomeOperador in dictOperadores.items():   #acrescentar logica pra pagina dois
                variavelNextion = "tOperador" + str(idOperador) + '.txt'
                enviar(variavelNextion, nomeOperador)
        else:
            idOperador = botaoApertado #cuidado que tem que ver qual numero tem que ser somado/subtraido conforme as ID dos botoes da tela
            operador = dictOperadores[idOperador]
            dictXmlProd['operador'] = operador
            dictXmlParada['operador'] = operador


    elif sinalTela is T_ROLO and botaoApertado is not ID_PAG:
        rolo = rolos[botaoApertado] #cuidado que tem que ver qual numero tem que ser somado/subtraido conforme as ID dos botoes da tela

    elif sinalTela is T_META:
        if botaoApertado is ID_PAG:
            enviar(str(calculaMeta()), 'tMeta.txt')
        if botaoApertado is ID_OK:
            _, *meta = receberInfo(QUERO_TUDO)
            meta = ''.join(meta)
            dictXmlProd['meta'] = meta

    elif sinalTela is T_PRODUZINDO:
        if botaoApertado is ID_PAG:
            atualizarNextion(False, True)
            produzindo = True
            parada = False
            if primeiro:
                primeiro = False
                gerarXmlProd()
                gerarXmlParada()
                atualizarXml(True, True)
                dictXmlProd['inicio'] = datetime.isoformat(datetime.now().replace(microsecond=0))
                producao = 0

    elif sinalTela is T_PARADAS:
        flagParada = True
        flagProd = False
        atualizarParada = True
        if botaoApertado is ID_PAG:
            dictXmlParada['data'] = datetime.isoformat(datetime.now().replace(microsecond=0))
            dictParadas = procurarParadas() 
            for idParada, nomeParada in dictParadas.items():   #acrescentar logica pra pagina dois
                variavelNextion = "tParada" + idParada + '.txt'
                enviar(variavelNextion, nomeParada)
        else:
            tipoParada = dictParadas[botaoApertado]
            dictXmlParada['tipo'] = tipoParada
            dictXmlParada['duracao'] = (datetime.isoformat(datetime.now().replace(microsecond=0)) - dictXmlParada['data']).total_seconds

    elif sinalTela is T_NOVAPROD:
        if botaoApertado is ID_PAG:
            atualizarNextion()
        if botaoApertado is ID_OK:
            atualizarXml(True, True)
            enviar('page pInicial', False, False)

    elif sinalTela is T_DESLIGAR:
        if botaoApertado is DESLIGAR:
            atualizarValores()
            subprocess.Popen(['sudo','shutdown','-h','now'])

