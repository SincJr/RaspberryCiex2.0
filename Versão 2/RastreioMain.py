import socket
import os
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from threading import Thread
import time
import serial
from datetime import datetime, timedelta
import struct
from math import ceil
import subprocess
from gpiozero import Button

#
#Constantes
#

#Telas
T_INICIAL = 0
T_DATAHORA = 1
T_AJUSTAR = 2
T_OP = 3
T_LOTE = 4
T_METsemAD = 5
T_METcomAD = 6
T_OPERADOR = 7
T_ROLO =8
T_META = 9
T_PRODUZINDO = 10
T_PARADAS = 11
T_VOLTAR = 12
T_NOVAPROD = 13
T_DESLIGAR = 14

#Outras
INTERRUPT_PIN = 17

PORTA_BASE_PADRAO = 32000
MAQUINA = 3
PORT = PORTA_BASE_PADRAO + MAQUINA

SIM = 69

#
#Declaração de portas
#
ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate =19200,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1   #mudar pra 0 que fica bem mais rapido, 1 é melhor pra debug
    )
    
ff = struct.pack('B', 0xff)

fimDeCurso = Button(INTERRUPT_PIN, pull_up=True, bounce_time=300)

#
#Variaveis Globais
#
producao = 0
dictOperadores = {}
dictParadas = {}
horario = ''
data = ''
op = ''
lote = ''
operador = ''
meta = ''
rolo = ''
rolos = {1:'25x10', 2:'25:09', 3:'25x45'}  #mudar esses numeros conforme ID do nextion
dictXmlProd = {'lote':'', 'op':'', 'inicio':'', 'fim':'', 'maquina':str(MAQUINA), 'operador':'', 'eixo':'', 'meta':'', 'qtd':'', 'rolosad':'', 'rolocad':''}
dictXmlParada = {'data':'', 'lote':'', 'op':'', 'tipo':'', 'maquina':str(MAQUINA), 'operador':'', 'duracao':''}

idProd = ''
idParada = ''

conjuntoOperadores = []
colunaAtual = 0

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


class Server(Thread): #
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


class Clock(Thread): #
    
    telaAtual = 0
    
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

                if self.telaAtual is T_DATAHORA:
                    nextion.Atualizar(True, False)
                
                #if produzindo:
                    #nextion.Atualizar(True, True)

            # if produzindo or parada:
                # atualizarXml(flagProd, flagParada)
                

        
    def pegarHora(self):
        now = datetime.now()
        hour = '{:02d}'.format(now.hour)
        hour = str(hour)
        minute = '{:02d}'.format(now.minute)
        minute = str(minute)
        second = '{:02d}'.format(now.second)
        second = str(second)
        
        return hour, minute, second

    def pegarData(self):
        now = datetime.now()
        day = '{:02d}'.format(now.day)
        day = str(day)
        month = '{:02d}'.format(now.month)
        month = str(month)
        year = '{:04d}'.format(now.year)
        year = str(year)
         
        return day, month, year


def FuncInterrupt():

    producao += 1
    flagProd = True
    timerAFK = False

    if producao >= meta:
        nextion.Enviar('page pNovaProd', False, False)


    if produzindo is False:
        nextion.Enviar('page pProduzindo', False, False)

        produzindo = True
        parada = False

        dictXmlParada['tipo'] = SEM_TIPO_PARADA
        dictXmlParada['duracao'] = (datetime.isoformat(datetime.now().replace(microsecond=0)) - dictXmlParada['data']).total_seconds


def progressoMeta():
    global producao
    return int((producao * 100)/dictXmlProd['meta'])


def calculaMeta():
    global rolo
    if rolo is '25x10':
        calculada = dictXmlProd['rolocad'] * 4
    elif rolo is '25x09':
        calculada = (dictXmlProd['rolocad']/10000) * 45.4545 
    elif rolo is '25x45':
        calculada = (dictXmlProd['rolocad']/10000) * 9.0909

    return calculada


class MexerXml():
    def __init__(self):
        global idProd
        global idParada
        global MAQUINA
    
    
    def GerarNovaProd(self):
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


    def GerarNovaParada(self):        
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
 
 
    def PegarOpcoes(self, tipo):
        xmlConfig = minidom.parse(arq_config)

        listaXml = xmlConfig.getElementsByTagName(tipo)

        dictOpcoes = {}

        for index, nome  in enumerate(listaXml):
            dictOpcoes[index] = nome.firstChild.nodeValue    

        return dictOpcoes, len(dictOpcoes)
    
    
    def SalvarAlteracoes(self, atualizarProd, atualizarParada): 
        if atualizarProd:
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

    
class Nextion(Thread): #
    def __init__(self):
        global rolo
        Thread.__init__(self)
        self.daemon = True
        self.start()


    def run(self):
        sair = False

        while True:
            flagRecebeu = False
            temMensagem = False
            botaoApertado = False
            botaoAlternativas = False
            sinalTela = -1
            
            msg = ser.read()
            print('por quê?')
            while msg:
                msg = msg.decode('iso-8859-1')
                
                if msg == 'e':          #BOTAO OK
                    sair = False
                    sinais = []
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            sair = True
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 16)
                            sinais.append(msg)
                    botaoTela = sinais[0]
        
        
                elif msg == 'p':        #INFORMACAO
                    sair = False
                    strRecebida = ''
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            msg = ser.read()
                            msg = ser.read()
                            sair = True
                        else:            
                            msg = msg.decode('iso-8859-1')
                            strRecebida += msg
                    temMensagem = True
                    logicaPrincipal(botaoTela, False, strRecebida)  #vai pra funcao das telas
                            
                            
                elif msg == 'z': #NOVA TELA
                    sair = False
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            sair = True
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 16)
                            sinalTela = msg
                            print('CCC' + str(sinalTela))
                            
                    
                    
                elif msg == 'y':        #INFO BOTAO ALTERNATIVAS
                    sair = False
                    sinais = []
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            sair = True
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 16)
                            sinais.append(msg)
                    botaoTela = sinais[0]
                    qualOpcao = sinais[1]
                    logicaPrincipal(botaoTela, False, qualOpcao)
                    
                elif msg  == 'k':
                    sair = False
                    sinais = []
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            sair = True
                        else:
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            sinais.append(msg)
                    scrollTela = int(sinais[0], 16)
                    direcao = sinais[1]
                    logicaPrincipal(scrollTela, False, direcao)

                msg = ser.read()
                
            if sinalTela is not -1:
                print('DDddDD')
                logicaPrincipal(sinalTela, True, False)


    def Atualizar(self, menosInfo, progresso):
        if not menosInfo:
            nextion.Enviar('tOP', dictXmlProd['op'])
            nextion.Enviar('tLote', dictXmlProd['lote'])
            nextion.Enviar('tOperador', dictXmlProd['operador'])
            nextion.Enviar('tRolo', rolo)
            nextion.Enviar('tMeta', dictXmlProd['meta'])
        
        if progresso:
            nextion.Enviar("tProgresso", str(progressoMeta())*100 + '%')
            nextion.Enviar("tBarra.val", str(progressoMeta()), False)


        nextion.Enviar("tHora", ':'.join(rtc.pegarHora()))
        nextion.Enviar("tData", '/'.join(rtc.pegarData()))


    def Enviar(self, varNextion, msgEnviar, texto = True): #
        varNextion = bytes(varNextion, encoding='iso-8859-1')
        ser.write(varNextion)

        if msgEnviar:
            if texto:
                msgEnviar = bytes('.txt="'+str(msgEnviar)+'"', encoding='iso-8859-1')

            else:
                msgEnviar = bytes('="'+str(msgEnviar)+'"', encoding='iso-8859-1')
            ser.write(msgEnviar)
        
        ser.write(ff+ff+ff)
        
        
def logicaPrincipal(tela, entrando, mensagem):   #
             #aqui se poe os comandos que vao rodar quando ENTRAR na pagina
    if entrando:  
        Clock.telaAtual = tela
    else:
        Clock.telaAtual = 0
    
    if tela is T_INICIAL:
        pass
        
    if tela is T_DATAHORA or tela is T_AJUSTAR:
        if entrando:
            if tela is T_DATAHORA:
                nextion.Atualizar(True, False)
        else:
            global horario
            global data
            mudarDH = False 
            if len(mensagem) is 8:
                horario = mensagem
            elif len(mensagem) is 10:
                data = mensagem
            
                hora, minuto, segundo = horario.split(':')
                dia, mes, ano = data.split('/')
                
                dataNova = datetime(int(ano), int(mes), int(dia), int(hora), int(minuto), int(segundo))
                
                if dataNova - datetime.now() > timedelta(minutes = 5):
                    mudarDH = True
                
                if mudarDH:
                    dataNova = dataNova.strftime('%Y-%m-%d %H:%M:%S')

                    subprocess.Popen(['sudo','date','-s', dataNova])
                 
    if tela is T_OP:
        if entrando:
            pass
        else:
            dictXmlProd['op'] = mensagem
            dictXmlParada['op'] = mensagem
            
    if tela is T_LOTE:
        if entrando:
            ano = datetime.today()
            ano = ano.strftime('%y')
            nextion.Enviar('tAno', ('/'+ano))
        else:
            dictXmlProd['lote'] = mensagem
            dictXmlParada['lote'] = mensagem
            
    if tela is T_METsemAD:
        if entrando:
            pass
        else:
            dictXmlProd['rolosad'] = mensagem
            pass
            
    if tela is T_METcomAD:
        if entrando:
            pass
        else:
            dictXmlProd['rolocad'] = mensagem
            pass
            
    if tela is T_OPERADOR:
        global conjuntoOperadores
        global colunaAtual
        global colunas
        global dictOperadores
        global visivel
        linhas = 3 #operadores na tela
        if entrando:            #nesse caso não é só entrando, é trocando de tela tambem
            visivel = [1 for x in range(linhas)]
            dictOperadores, qtdOperadores = xml.PegarOpcoes('operador')
            print(dictOperadores)
            colunas = ceil(qtdOperadores/linhas)

            conjuntoOperadores = [[0 for x in range(linhas)] for y in range(colunas)]

            index = 0
            for col in range(colunas):
                for lin in range(linhas):
                    if qtdOperadores is not index:
                        conjuntoOperadores[col][lin] = dictOperadores[index]
                        index +=1
                    else:
                        conjuntoOperadores[col][lin] = ' '

            for lin in range(linhas):
                nextion.Enviar("tO"+str(lin), conjuntoOperadores[colunaAtual][lin])
                  
            if colunas > 1:
                nextion.Enviar("vis bR,1", False, False)

        else:
            if mensagem == '>' or mensagem == '<':
                colunaAtual = colunaAtual + 1 if mensagem == '>' else colunaAtual - 1
                
                for lin in range(linhas):
                    nome = conjuntoOperadores[colunaAtual][lin]
                    if nome == ' ':
                        nextion.Enviar("vis tO" + str(lin) + ",0", False, False)
                        visivel[lin] = 0
                    else:
                        if visivel[lin] is not 1:
                            nextion.Enviar("vis tO" + str(lin) + ",1", False, False)
                        nextion.Enviar("tO"+str(lin), nome)
                        visivel[lin] = 1
                
                if colunas > (1+colunaAtual):
                    nextion.Enviar("vis bR,1",False,False)  
                else:
                    nextion.Enviar("vis bR,0",False,False)
                    
                if colunaAtual > 0:
                    nextion.Enviar("vis bL,1",False,False)
                else:
                    nextion.Enviar("vis bL,0",False,False)
                
                
            else:
                operador = dictOperadores[mensagem]
                dictXmlProd['operador'] = operador
                dictXmlParada['operador'] = operador
            
    if tela is T_ROLO:
        if entrando:
            pass
        else:
            global rolo
            rolo = rolos[mensagem]
            pass
            
    if tela is T_META:
        if entrando:
            nextion.Enviar('tMeta', str(calcularMeta()))
        else:
            dictXmlProd['meta'] = mensagem

    if tela is T_PRODUZINDO:
        if entrando:
            nextion.Atualizar(False, True)
            pass
        else:
            pass
            
    if tela is T_PARADAS:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_NOVAPROD:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_DESLIGAR:
        if entrando:
            pass
        else:
            if mensagem is DESLIGAR:
                atualizarValores()
                subprocess.Popen(['sudo','shutdown','-h','now'])
            pass


nextion = Nextion()
Server()
xml = MexerXml()
rtc = Clock()

fimDeCurso.when_pressed = FuncInterrupt
                
while True:
    pass
                    
            
        
