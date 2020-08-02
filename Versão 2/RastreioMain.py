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

NAO_INFORMADO = "Não informada"

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
parada = False
produzindo = False
configurando = True

dictOperadores = {}
dictParadas = {}
horario = ''
data = ''
op = ''
lote = ''
operador = ''
meta = ''
rolo = ''
rolos = {0:'25x10', 1:'25:09', 2:'25x45'} 
dictXmlProd = {'lote':'', 'op':'', 'inicio':'', 'fim':'', 'maquina':str(MAQUINA), 'operador':'', 'eixo':'', 'meta':'', 'qtd':'', 'rolosad':'', 'rolocad':''}
dictXmlParada = {'data':'', 'lote':'', 'op':'', 'tipo':'', 'maquina':str(MAQUINA), 'operador':'', 'duracao':''}

idProd = ''
idParada = ''

conjuntoOperadores = []
colunaAtual = 0

primeiro = True
inicioProd = True
inicioParada = False

timerAFK = False
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
                
                if self.telaAtual is T_PRODUZINDO:
                    nextion.Atualizar(True, True)

            xml.SalvarAlteracoes(True, False)
        
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


class DetectaAFK(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        global produzindo
        global timerAFK

        flagAFK = True
        timerAFK = True
        if produzindo:
            startTempo = datetime.now()
            while datetime.now() - startTempo < timedelta(minutes=2):
                if not timerAFK:
                    timerAFK = True
                    flagAFK = False
                    break
            if flagAFK:
                enviar("click 4,0", False, False) 


class BateuMeta(Thread):

    bateu = False
    flag = True
    telaAtual = 0

    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        global producao
        global 
        if dictXmlProd['meta'] >= producao and self.flag and self.telaAtual is T_PRODUZINDO:
            self.bateu = True
            nextion.Enviar("page pNovaProd", False, False)
            self.flag = False 
        
        if bateu and self.telaAtual is T_PRODUZINDO:
            nextion.Enviar("vis bProd,1", False, False)


def FuncInterrupt():
    global producao
    global parada
    global produzindo
    global flagProd
    global timerAFK

    if not configurando:
        producao += 1
        timerAFK = False

        if producao >= meta:
            pass


        if produzindo is False:
            produzindo = True
            parada = False

            dictXmlParada['tipo'] = NAO_INFORMADO
            dictXmlParada['duracao'] = (datetime.now().replace(microsecond=0) - datetime.fromisoformat(dictXmlParada['data'])).total_seconds()

            xml.SalvarAlteracoes(True, True)

            nextion.Enviar('page pProduzindo', False, False)


def progressoMeta():
    global producao
    return int((producao * 100)/dictXmlProd['meta'])


def calcularMeta():
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

            for tipo, _ in dictXmlProd.items():
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
    global configurando
             #aqui se poe os comandos que vao rodar quando ENTRAR na pagina
    if entrando:  
        Clock.telaAtual = tela
    else:
        Clock.telaAtual = 0
    
    if tela is T_INICIAL:
        global primeiro 
        global inicioProd
        
        nextion.Enviar("tIP", socket.gethostname())

        nextion.Enviar("dim=100", False, False)
        nextion.Enviar("tsw 255,1", False, False)

        primeiro = False
        inicioProd = True
        pass
        
    if tela is T_DATAHORA or tela is T_AJUSTAR:
        configurando = True
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
        configurando = True
        if entrando:
            pass
        else:
            dictXmlProd['op'] = mensagem
            dictXmlParada['op'] = mensagem
            
    if tela is T_LOTE:
        configurando = True
        ano = datetime.today()
        anoLote = '/' + ano.strftime('%y')
        if entrando:
            nextion.Enviar('tAno', (anoLote))
        else:
            dictXmlProd['lote'] = 'FP' + mensagem + anoLote
            dictXmlParada['lote'] = 'FP' + mensagem + anoLote
            
    if tela is T_METsemAD:
        configurando = True
        if entrando:
            pass
        else:
            dictXmlProd['rolosad'] = mensagem
            
    if tela is T_METcomAD:
        configurando = True
        if entrando:
            pass
        else:
            dictXmlProd['rolocad'] = mensagem
            
    if tela is T_OPERADOR:
        configurando = True
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

            colunaAtual = 0

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
        configurando = True
        if entrando:
            pass
        else:
            global rolo
            rolo = rolos[mensagem]
            
    if tela is T_META:
        configurando = True
        if entrando:
            nextion.Enviar('tMeta', str(calcularMeta()))
        else:
            dictXmlProd['meta'] = mensagem

    if tela is T_PRODUZINDO:
        configurando = False
        global inicioProd
        global produzindo
        global parada
        if entrando:
            if inicioProd:
                BateuMeta()
                xml.GerarNovaProd()
                dictXmlProd['inicio'] = datetime.now().replace(microsecond=0).isoformat()

            produzindo = True
            parada = False
            nextion.Atualizar(False, True)
            xml.SalvarAlteracoes(True, False)

            
        else:
            xml.SalvarAlteracoes(True, False)
            produzindo = False
            pass
            
    if tela is T_PARADAS:
        configurando = False
        global inicioParada
        global produzindo
        global parada
        global conjuntoParadas
        global colunaAtual
        global colunas
        global dictParadas
        global visivel
        linhas = 3
        if entrando:
            xml.GerarNovaParada()
            dictXmlParada['data'] = datetime.now().replace(microsecond=0).isoformat()
            xml.SalvarAlteracoes(False, True)

            colunaAtual = 0

            visivel = [1 for x in range(linhas)]
            dictParadas, qtdParadas = xml.PegarOpcoes('parada')
            print(dictParadas)
            colunas = ceil(qtdParadas/linhas)

            conjuntoParadas = [[0 for x in range(linhas)] for y in range(colunas)]

            index = 0
            for col in range(colunas):
                for lin in range(linhas):
                    if qtdParadas is not index:
                        conjuntoParadas[col][lin] = dictParadas[index]
                        index +=1
                    else:
                        conjuntoParadas[col][lin] = ' '

            for lin in range(linhas):
                nextion.Enviar("tP"+str(lin), conjuntoParadas[colunaAtual][lin])
                  
            if colunas > 1:
                nextion.Enviar("vis bR,1", False, False)
            pass
        else:
            if mensagem == '>' or mensagem == '<':
                colunaAtual = colunaAtual + 1 if mensagem == '>' else colunaAtual - 1
                
                for lin in range(linhas):
                    tipo = conjuntoParadas[colunaAtual][lin]
                    if tipo == ' ':
                        nextion.Enviar("vis tP" + str(lin) + ",0", False, False)
                        visivel[lin] = 0
                    else:
                        if visivel[lin] is not 1:
                            nextion.Enviar("vis tP" + str(lin) + ",1", False, False)
                        nextion.Enviar("tP"+str(lin), tipo)
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
                tipoParada = dictParadas[mensagem]
                dictXmlProd['tipo'] = tipoParada
                dictXmlParada['tipo'] = tipoParada
            
    if tela is T_VOLTAR:
        configurando = False
        if entrando:
            pass
        else:
            dictXmlParada['duracao'] = (datetime.now().replace(microsecond=0) - datetime.fromisoformat(dictXmlParada['data'])).total_seconds()
            xml.SalvarAlteracoes(False, True)
            pass

    if tela is T_NOVAPROD:
        configurando = False
        if entrando:
            nextion.Enviar("tMeta", dictXmlProd['meta'])
            produzindo = True
            pass
        else:
            if mensagem is SIM:
                xml.SalvarAlteracoes(True, False)
                nextion.Enviar("page pInicial", False, False)
                os.execv(__file__, sys.argv)
                
    if tela is T_DESLIGAR:
        configurando = True
        if entrando:
            pass
        else:
            if mensagem is SIM:
                dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat()
                xml.SalvarAlteracoes(True, False)
                nextion.Enviar("rest", False, False)
                subprocess.Popen(['sudo','shutdown','-h','now'])
            pass


nextion = Nextion()
Server()
xml = MexerXml()
rtc = Clock()
DetectaAFK()

fimDeCurso.when_pressed = FuncInterrupt
                
if primeiro:
        logicaPrincipal(T_INICIAL, True, False)

while True:
    pass
                    
            
        
