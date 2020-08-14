import socket
import os
import sys
import xml.dom.minidom as minidom
import xml.etree.ElementTree as ET
from threading import Thread
import time
import serial
from datetime import datetime, timedelta
import struct
from math import ceil
import subprocess
import netifaces
import RPi.GPIO as GPIO

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
INTERRUPT_PIN = 27

PORTA_BASE_PADRAO = 32000
MAQUINA = 3
PORT = PORTA_BASE_PADRAO + MAQUINA

SIM = 69

NAO_INFORMADO = "Nao informada"

#
#Declaração de portas
#
ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate=19200,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=0.1 #mudar pra 0 que fica bem mais rapido. 1 é melhor pra debug
    )
    
ff = struct.pack('B', 0xff)

GPIO.setmode(GPIO.BCM)
GPIO.setup(INTERRUPT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

#
#Variaveis Globais
#
producao = 0
parada = False
produzindo = False
configurando = True
bateu = False
flagVazio = True

dictOperadores = {}
dictParadas = {}
horario = ''
data = ''
op = ''
lote = ''
operador = ''
meta = ''
rolo = ''

if MAQUINA is 1:
    rolos = {0:'25x10', 1:'25x09', 2:'25x45'} 
elif MAQUINA is 2:
    rolos = {0:'50x10', 1:'50x4,5'}
elif MAQUINA is 3:
    rolos = {0:'100x10', 1:'100x4,5', 2:'12x10', 3:'12x4,5'} 
dictXmlProd = {'lote':'', 'op':'', 'inicio':'', 'fim':'', 'maquina':str(MAQUINA), 'operador':'', 'eixo':'', 'meta':'', 'qtd':'0', 'rolosad':'', 'rolocad':''}
dictXmlParada = {'data':'', 'lote':'', 'op':'', 'tipo':NAO_INFORMADO, 'maquina':str(MAQUINA), 'operador':'', 'duracao':'300'}

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
arq_config = os.path.abspath(os.path.join(full_file, file_config))
arq_parada = os.path.abspath(os.path.join(full_file, file_paradas))
arq_prod = os.path.abspath(os.path.join(full_file, file_prod))


class Server(Thread): #
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()
        
    def run(self):
        global flagVazio
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1 )
                try:
                    HOST = netifaces.ifaddresses('eth0')[2][0]['addr']
                    sock.bind((HOST, PORT))
                    sock.listen()
                    print('ouve')
                    client, addr = sock.accept()
                    print('oi')
                    with client:
                        print('Connectado a', addr)
                        btipo = client.recv(1)
                        tipo = btipo.decode("utf-8")
                        print("ECHO " + str(tipo))
                        if btipo is 'c' or 'p':  # c = config (ou seja, receber info de maquina), p = prod/paradas (ou seja, enviar xmls)
                            print('masss')
                            client.send(btipo)     # echo
                            if tipo is 'c':
                                stream = client.recv(1024000)
                                root = ET.fromstring(stream)
                                with open(arq_config,'w') as arq:
                                    arq.write(ET.tostring(root).decode())
                                flagVazio = False
                            else:
                                print('entrou')
                                reatualizarParada = False
                                reatualizarProd = False
                                if dictXmlProd['fim'] == '' and idProd:
                                    dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat()
                                    xml.SalvarAlteracoes(True, False)
                                    dictXmlProd['fim'] = ''
                                    print("AQUI")
                                    reatualizarProd = True

                                if dictXmlParada['duracao'] == '' and idParada:
                                    dictXmlParada['duracao'] = (datetime.now().replace(microsecond=0) - datetime.fromisoformat(dictXmlParada['data'])).total_seconds()  #nao é o ideal, mas é o que temos
                                    if dictXmlParada['tipo'] == '':
                                        dictXmlParada['tipo'] = NAO_INFORMADO
                                    print("E AQUI TB")
                                        
                                    xml.SalvarAlteracoes(False, True)
                                    dictXmlParada['tipo'] = ''
                                    dictXmlParada['duracao'] = ''
                                    reatualizarParada = True


                                xmlStream = ET.parse(arq_parada)
                                xmlstr = ET.tostring(xmlStream.getroot()).decode()
                                client.send(bytes(xmlstr, "utf-8"))
                                
                                print("POXA :/")
                                xmlStream = ET.parse(arq_prod)
                                xmlstr = ET.tostring(xmlStream.getroot()).decode()
                                client.send(bytes(xmlstr, "utf-8"))
                                print('saiu, finalmente')
                                xml.SalvarAlteracoes(reatualizarProd, reatualizarParada)
                                
                        else:
                            print('Erro!')
                except:
                    pass


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
                
                startTempo5s = datetime.now()
                        
                while datetime.now() - startTempo5s < timedelta(seconds=5):
                    
                    startTempo = datetime.now()
                    while datetime.now() - startTempo < timedelta(seconds=.1):
                        pass

                    if self.telaAtual is T_DATAHORA and not nextion.atualizando:
                        nextion.Atualizar(True, False)
                    
                    if self.telaAtual is T_PRODUZINDO and not nextion.atualizando:
                        nextion.Atualizar(True, True)
                        
                if self.telaAtual is T_PRODUZINDO and not nextion.atualizando:
                        nextion.Atualizar(False, False)
                        
                    
            if self.telaAtual is T_PRODUZINDO:
                dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat()
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
        
        while True:
            flagAFK = True
            timerAFK = True
            if produzindo:
                startTempo = datetime.now()
                print('oio')
                while datetime.now() - startTempo < timedelta(minutes=2):
                    if not timerAFK or not produzindo:
                        timerAFK = True
                        flagAFK = False
                        break
                if flagAFK:
                    print('aaa deu certo')
                    nextion.Enviar("click tParada,0", False, False) 


class BateuMeta(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.daemon = True
        self.start()

    def run(self):
        flag = True
        global produzindo
        global bateu
        while True:
            if produzindo:
                if int(dictXmlProd['meta']) <= int(dictXmlProd['qtd']) and not bateu and produzindo and not nextion.atualizando and int(dictXmlProd['qtd']) >= 1:
                    dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat()
                    bateu = True
                    nextion.Atualizar(False, True)
                    nextion.Enviar("click bProd,0", False, False)
                    

def FuncInterrupt(porta):
    global producao
    global parada
    global produzindo
    global flagProd
    global timerAFK
    
    print("EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE")
    
    if not configurando:
        producao += 1
        dictXmlProd['qtd'] = str(producao)
        timerAFK = False
        dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat() 
        
        if produzindo is False:
            produzindo = True
            parada = False

            dictXmlParada['tipo'] = NAO_INFORMADO
            dictXmlParada['duracao'] = (datetime.now().replace(microsecond=0) - datetime.fromisoformat(dictXmlParada['data'])).total_seconds()

            xml.SalvarAlteracoes(True, True)

            nextion.Enviar('page pProducao', False, False)


def progressoMeta():
    global producao
    return int((producao * 100)/int(dictXmlProd['meta']))


def calcularMeta():
    print(dictXmlProd['rolocad'])
    print(type(dictXmlProd['rolocad']))
    if rolo is '25x10':
        calculada = dictXmlProd['rolocad'] * 4
    elif rolo is '25x09':
        calculada = (dictXmlProd['rolocad']) * 4.4545 
    elif rolo is '25x45':
        calculada = (dictXmlProd['rolocad']) * 9.0909
    else:
        calculada = 2000

    return round(calculada)


class MexerXml():
    def PegarEixo(self, rolo):
        global arq_config
        
        xml = ET.parse(arq_config)
        xmlRoot = xml.getroot()
        eixo =''
        
        try:
            for eixos in xmlRoot.findall('./eixos/eixo'):
                nomeRolo = eixos.find('./rolos/rolo/nome').text
                if nomeRolo == rolo:
                    eixo = eixos.find('./nome').text
        except:
            eixo = 'Nao encontrado'

        if eixo == '':
            eixo = 'Nao encontrado'
    
        dictXmlProd['eixo'] = eixo
        
    
    def GerarNovaProd(self):
        global arq_prod
        global idProd
        xmlProd = ET.parse(arq_prod)
        xmlProdRaiz = xmlProd.getroot()

        for prodFeita in xmlProdRaiz.findall('./producoesM' + str(MAQUINA) + '/producao'):
            idProd = prodFeita.get('id')

        idProd = str(int(idProd) + 1) if idProd != '' else '1'
            
        print(idProd)
        
        xmlProdRaiz = xmlProdRaiz.find('./producoesM' + str(MAQUINA))
        ET.SubElement(xmlProdRaiz, 'producao').set('id', idProd)
        
        

        xmlProdRaiz = xmlProdRaiz.find('./producao[@id="'+ idProd +'"]')

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
        global arq_parada
        global idParada        
        xmlParada = ET.parse(arq_parada)
        xmlParadaRaiz = xmlParada.getroot()

        for paradaFeita in xmlParadaRaiz.findall('./paradasM' + str(MAQUINA) + '/parada'):
            idParada = paradaFeita.get('id')
            

        idParada = str(int(idParada) + 1) if idParada != '' else '1'

        xmlParadaRaiz = xmlParadaRaiz.find('./paradasM' + str(MAQUINA))
        ET.SubElement(xmlParadaRaiz, 'parada').set('id', idParada)
        
        
        xmlParadaRaiz = xmlParadaRaiz.find('./parada[@id="'+ idParada +'"]')

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
            
            print("aaa" + idProd)
            rootProducoes = rootProducoes.find('./producoesM' + str(MAQUINA) + '/producao[@id="' + idProd + '"]')
            print(rootProducoes.text)
            
            for tipo, _ in dictXmlProd.items():
                print(tipo)
                xmlProd = rootProducoes.find('./' + tipo)
                xmlProd.text = str(dictXmlProd[tipo])
            xmlProducoes.write(arq_prod)

        if atualizarParada:
            xmlParadas = ET.parse(arq_parada)
            rootParadas = xmlParadas.getroot()

            rootParadas = rootParadas.find('./paradasM' + str(MAQUINA) + '/parada[@id="'+ idParada +'"]')
            
            for tipo, _ in dictXmlParada.items():
                xmlParada = rootParadas.find('./' + tipo)
                xmlParada.text = str(dictXmlParada[tipo])
            xmlParadas.write(arq_parada)

    
class Nextion(Thread): #
    
    atualizando = False
    
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
            self.atualizando = False
            opa = False
            OK = False
            Alt = False
            Setinha = False
            texto = []
            
            msg = ser.read()
            print('.')
            while msg:
                msg = msg.decode('iso-8859-1')
                print(msg)
                self.atualizando = True
                
                if msg == 'e':          #BOTAO OK
                    sair = False
                    OK = True
                    sinais = []
                    while not sair:
                        msg = ser.read()
                        print(msg)
                        if msg == b'\xff':
                            sair = True
                        elif msg == b'\t':
                            msg = 9
                            sinais.append(msg)
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 10)
                            sinais.append(msg)
                    botaoOK = sinais[0]
        
        
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
                    texto.append(strRecebida)
                    temMensagem = True
                    
                            
                            
                elif msg == 'z': #NOVA TELA
                    sair = False
                    while not sair:
                        print(msg)
                        msg = ser.read()
                        print(msg)
                        if msg == b'\xff':
                            sair = True
                        elif msg == b'\t':
                            sinalTela = 9
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 10)
                            sinalTela = msg
                            print('CCC' + str(sinalTela))
                            
                    
                    
                elif msg == 'y':        #INFO BOTAO ALTERNATIVAS
                    sair = False
                    sinais = []
                    Alt = True
                    while not sair:
                        print(msg)
                        msg = ser.read()
                        if msg == b'\xff':
                            sair = True
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            if msg == 'i':
                                msg = 69
                            else:
                                msg = int(msg, 10)
                            sinais.append(msg)
                    botaoTela = sinais[0]
                    qualOpcao = sinais[1]
                    
                elif msg  == 'k':
                    sair = False
                    sinais = []
                    Setinha = True
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
                    print('q porra' + str(sinais[0]))
                    print('q porra' + str(sinais[1]))
                    scrollTela = int(sinais[0], 10)
                    direcao = sinais[1]

                    
                msg = ser.read()
    
                
            self.atualizando = False

            if texto:
                for coisa in texto:
                    logicaPrincipal(botaoOK, False, coisa)  #vai pra funcao das telas
                    
            if Alt:
                logicaPrincipal(botaoTela, False, qualOpcao)
                
            if Setinha:
                logicaPrincipal(scrollTela, False, direcao)

            if sinalTela is not -1:
                logicaPrincipal(sinalTela, True, False)


    def Atualizar(self, menosInfo, progresso):
        global bateu
        
        if not menosInfo:
            telinhaTemp = rtc.telaAtual
            self.atualizando = True
            rtc.telaAtual = 0
            nextion.Enviar('tLote', str(dictXmlProd['lote']))
            nextion.Enviar('tOperador', str(dictXmlProd['operador']))
            nextion.Enviar('tRolo', str(rolo))
            nextion.Enviar('tMeta', str(dictXmlProd['meta']))
            nextion.Enviar('tOP', str(dictXmlProd['op']))
            
            if bateu:
                nextion.Enviar("vis bProd,1", False, False)
        
            self.atualizando = False
            rtc.telaAtual = telinhaTemp
        
        if progresso:
            prog = progressoMeta()
            nextion.Enviar("tProgresso", str(prog) + '%')
            if prog > 100:
                nextion.Enviar('tBarra.val=', str(100), False)
            else:
                nextion.Enviar('tBarra.val=', str(prog), False)
        
        nextion.Enviar("tHora", ':'.join(rtc.pegarHora()))
        nextion.Enviar("tData", '/'.join(rtc.pegarData()))
        
        
        
        
        

    def Enviar(self, varNextion, msgEnviar, texto = True): #
        varNextion = bytes(varNextion, encoding='iso-8859-1')
        ser.write(varNextion)

        if msgEnviar:
            if texto:
                msgEnviar = bytes('.txt="'+str(msgEnviar)+'"', encoding='iso-8859-1')

            else:
                msgEnviar = bytes(msgEnviar, encoding='iso-8859-1')
            ser.write(msgEnviar)
        
        ser.write(ff+ff+ff)
        
        
def logicaPrincipal(tela, entrando, mensagem):   #
    global configurando
             #aqui se poe os comandos que vao rodar quando ENTRAR na pagina
    rtc.telaAtual = 0
    
    print('logica principal ' + str(tela) + ' = ' + str(mensagem))
    
    if tela is T_INICIAL:
        global flagVazio
        global primeiro 
        global inicioProd
        
        startConectando = datetime.now()
        
        nextion.Enviar("dim=100", False, False)
        
        sucessoRede = False
        
        while datetime.now() - startConectando < timedelta(minutes=0.5):
            try:
                ip = netifaces.ifaddresses('eth0')[2][0]['addr']
                nextion.Enviar("tIP", ip)
                sucessoRede = True
                break
            except:
                nextion.Enviar("tIP", "Aguarde. Conectando à Internet")
            
        if not sucessoRede:
            nextion.Enviar("tIP", "Falha ao conectar à Internet")
            
        while flagVazio: 
            try:     
                xmlConf = ET.parse(arq_config)
                raiz = xmlConf.getroot()
            
                for pessoa in raiz.findall('./operadores/operador'):
                    flagVazio = False
                    break;
                for pausa in raiz.findall('./paradas/parada'):
                    flagVazio = False
                    break
                for eixo2 in raiz.findall('./eixos/eixo'):
                    flagVazio = False
                    break
            
                nextion.Enviar("tMsg", "Sem arquivo de Configuracao!")
                nextion.Enviar("tMsg2", "Importe o arquivo de Configuracao!")
            except:
                nextion.Enviar("tMsg", "Sem arquivo de Configuracao!")
                nextion.Enviar("tMsg2", "Importe o arquivo de Configuracao!")
           
            
        nextion.Enviar("tMsg", "Arquivo de Configuracao Importado!")
        nextion.Enviar("tMsg2", " ")
        nextion.Enviar("tsw 255,1", False, False)

        primeiro = False
        inicioProd = True
        pass
        
    if tela is T_DATAHORA or tela is T_AJUSTAR:
        configurando = True
        if entrando:
            if tela is T_DATAHORA:
                nextion.Atualizar(True, False)
                rtc.telaAtual = 1
        else:
            rtc.telaAtual = 0
            if tela is not T_DATAHORA:
                print('wasssss')
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
        print(dictXmlProd['op'])
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
            dictXmlProd['rolocad'] = int(mensagem)
            print(mensagem)
            print(type(mensagem))
            
    if tela is T_OPERADOR:
        configurando = True
        global conjuntoOperadores
        global colunaAtual
        global colunas
        global dictOperadores
        global visivel
        linhas = 4 #operadores na tela
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
                        conjuntoOperadores[col][lin] = " "

            for lin in range(linhas):
                nextion.Enviar("tO"+str(lin), conjuntoOperadores[colunaAtual][lin])
                  
            if colunas > 1:
                nextion.Enviar("vis bR,1", False, False)

        else:
            if mensagem == '>' or mensagem == '<':
                colunaAtual = colunaAtual + 1 if mensagem == '>' else colunaAtual - 1
                
                
                if colunas > (1+colunaAtual):
                    nextion.Enviar("vis bR,1",False,False)  
                else:
                    nextion.Enviar("vis bR,0",False,False)
                    
                if colunaAtual > 0:
                    nextion.Enviar("vis bL,1",False,False)
                else:
                    nextion.Enviar("vis bL,0",False,False)
                    
                    
                for lin in range(linhas):
                    nome = conjuntoOperadores[colunaAtual][lin]
                    if nome == ' ':
                        nextion.Enviar("tO" + str(lin), " ")
                    else:
                        nextion.Enviar("tO"+str(lin), nome)

                
                
                
                
            else:
                escolha = mensagem + colunaAtual*4
                operador = dictOperadores[escolha]
                dictXmlProd['operador'] = operador
                dictXmlParada['operador'] = operador
            
    if tela is T_ROLO:
        configurando = True
        global rolo
        if entrando:
            for chave, valor in rolos.items():
                nextion.Enviar('tR' + str(chave), valor)
        else:
            rolo = rolos[mensagem]
            xml.PegarEixo(rolo)
            print(dictXmlProd['eixo'])
            
    if tela is T_META:
        configurando = True
        if entrando:
            nextion.Enviar('tMeta', str(calcularMeta()))
            print(str(calcularMeta()))
        else:
            dictXmlProd['meta'] = mensagem

    if tela is T_PRODUZINDO:
        configurando = False
        global produzindo
        global parada
        print('Foiiii')
        if entrando:
            if inicioProd:
                print(dictXmlProd)
                xml.GerarNovaProd()
                dictXmlProd['inicio'] = datetime.now().replace(microsecond=0).isoformat()
                dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat()
                inicioProd = False

            produzindo = True
            parada = False
            start = datetime.now()
            nextion.Atualizar(False, True)
            rtc.telaAtual = 10
            xml.SalvarAlteracoes(True, False)

            
        else:
            xml.SalvarAlteracoes(True, False)
            produzindo = False
            rtc.telaAtual = 0
            
    if tela is T_PARADAS:
        configurando = False
        global inicioParada
        global conjuntoParadas
        global dictParadas
        linhas = 4
        print("PARADA" + str(mensagem))
        if entrando:
            produzindo = False
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
                        conjuntoParadas[col][lin] = " "

            for lin in range(linhas):
                    nextion.Enviar("tP"+str(lin), conjuntoParadas[colunaAtual][lin])
                  
            if colunas > 1:
                nextion.Enviar("vis bR,1", False, False)
                
        else:
            if mensagem == '>' or mensagem == '<':
                colunaAtual = colunaAtual + 1 if mensagem == '>' else colunaAtual - 1
                
                
                if colunas > (1+colunaAtual):
                    nextion.Enviar("vis bR,1",False,False)  
                else:
                    nextion.Enviar("vis bR,0",False,False)
                    
                if colunaAtual > 0:
                    nextion.Enviar("vis bL,1",False,False)
                else:
                    nextion.Enviar("vis bL,0",False,False)
                    
                for lin in range(linhas):
                    tipo = conjuntoParadas[colunaAtual][lin]
                    
                    if tipo == ' ':
                        nextion.Enviar("tP" + str(lin), " ")
                        
                    else:
                        nextion.Enviar("tP"+str(lin), tipo)
                
            else:
                escolha = mensagem + colunaAtual*4
                tipoParada = dictParadas[escolha]
                dictXmlParada['tipo'] = tipoParada
                print(dictXmlParada['tipo'])
                xml.SalvarAlteracoes(False, True)
                            
    if tela is T_VOLTAR:
        configurando = False
        print(str(mensagem) + " kk")
        if entrando:
            pass
        else:
            dictXmlParada['duracao'] = str(round((datetime.now().replace(microsecond=0) - datetime.fromisoformat(dictXmlParada['data'])).total_seconds()))
            xml.SalvarAlteracoes(False, True)
            pass

    if tela is T_NOVAPROD:
        configurando = False
        if entrando:
            produzindo = True
            pass
        else:
            global full_file
            if mensagem is SIM:
                xml.SalvarAlteracoes(True, False)
                nextion.Enviar("rest", False, False)
                GPIO.cleanup()
                os.execv('/usr/bin/python3', [sys.argv[0],os.path.abspath(__file__)])
                
    if tela is T_DESLIGAR:
        configurando = True
        if entrando:
            pass
        else:
            if mensagem is SIM:
                print("AAA")
                if not inicioProd:
                    dictXmlProd['fim'] = datetime.now().replace(microsecond=0).isoformat()
                    xml.SalvarAlteracoes(True, False)
                nextion.Enviar("rest", False, False)
                ser.close()
                GPIO.cleanup()
                subprocess.Popen(['sudo','shutdown','-h','now'])
            pass


nextion = Nextion()
Server()
xml = MexerXml()
rtc = Clock()
DetectaAFK()
BateuMeta()

GPIO.add_event_detect(INTERRUPT_PIN, GPIO.RISING, callback=FuncInterrupt, bouncetime=300)
                
if primeiro:
        logicaPrincipal(T_INICIAL, True, False)

while True:
    pass
                    
            
        
