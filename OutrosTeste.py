import serial
from threading import Thread
from datetime import datetime, timedelta
import struct

ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate =9600,           
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=1
    )
    
ff = struct.pack('B', 0xff)

#
#Telas
#
T_INICIAL = 0
T_DATAHORA = 1
T_AJUSTAR = 3
T_OP = 2
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



MAQUINA = 3
#
#Variaveis Normais
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


class Clock(Thread):
    
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
                    print(self.telaAtual)
                    atualizarNextion(True, False)
                #if produzindo:
                    #atualizarNextion(True, True)

            # if produzindo or parada:
                # atualizarXml(flagProd, flagParada)
                

        
    def pegarHoraRTC(self):
        now = datetime.now()
        hour = '{:02d}'.format(now.hour)
        hour = str(hour)
        minute = '{:02d}'.format(now.minute)
        minute = str(minute)
        second = '{:02d}'.format(now.second)
        second = str(second)
        
        return hour, minute, second

    def pegarDataRTC(self):
        now = datetime.now()
        day = '{:02d}'.format(now.day)
        day = str(day)
        month = '{:02d}'.format(now.month)
        month = str(month)
        year = '{:04d}'.format(now.year)
        year = str(year)
         
        return day, month, year


def atualizarNextion(menosInfo, progresso):
    if not menosInfo:
        enviar('tOP', op)
        enviar('tLote', lote)
        enviar('tOperador', operador)
        enviar('tRolo', rolo)
        enviar('tMeta', meta)
    
    if progresso:
        enviar("tProgresso", str(progressoMeta()))

    enviar("tHora", ':'.join(rtc.pegarHoraRTC()))
    enviar("tData", '/'.join(rtc.pegarDataRTC()))


def enviar(varNextion, msgEnviar, texto = True):
    
    varNextion = bytes(varNextion, encoding='iso-8859-1')
    ser.write(varNextion)

    if msgEnviar:
        if texto:
            msgEnviar = bytes('.txt="'+str(msgEnviar)+'"', encoding='iso-8859-1')

        else:
            msgEnviar = bytes('="'+str(msgEnviar)+'"', encoding='iso-8859-1')
        ser.write(msgEnviar)
    
    ser.write(ff+ff+ff)

    
class LeitorNextion(Thread):
    def __init__(self):
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
            print('Oi')
            msg = ser.read()
            while msg:
                msg = msg.decode('iso-8859-1')
                
                
                if msg == 'e':          #BOTAO OK
                    sair = False
                    sinais = []
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            msg = ser.read()
                            msg = ser.read()
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
                            
                            
                elif msg == bytes.fromhex('aa').decode('iso-8859-1'): #NOVA TELA
                    msg = ser.read()
                    sair = False
                    while not sair:
                        if msg == b'\xff':
                            msg = ser.read()
                            msg = ser.read()
                            sair = True
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 16)
                            sinalTela = msg
                            break
                    
                    
                elif msg == 'b':        #INFO BOTAO ALTERNATIVAS
                    sair = False
                    sinais = []
                    while not sair:
                        msg = ser.read()
                        if msg == b'\xff':
                            msg = ser.read()
                            msg = ser.read()
                            sair = True
                        else:            
                            msg = str(msg)
                            msg = msg.replace('b', '', 1)
                            msg = msg.replace("'", '')
                            msg = msg.replace('\\x', '')
                            msg = int(msg, 16)
                            sinais.append(msg)
                        sair = True #
                    botaoTela = sinais[0]
                    qualOpcao = sinais[1]
                    logicaPrincipal(botaoTela, False, qualBotao)
                    
                msg = ser.read()
                print(msg)
                
            if sinalTela is not -1:
                print(sinalTela)
                logicaPrincipal(sinalTela, True, False)
                

def logicaPrincipal(tela, entrando, mensagem):  
             #aqui se poe os comandos que vao rodar quando ENTRAR na pagina
    print('AA ' + str(tela))
    rtc.telaAtual = tela
    
    if tela is T_INICIAL:
        pass
        
    if tela is T_DATAHORA:
        if entrando:
            atualizarNextion(True, False)
            pass
        else:
            global horario
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
                else:
                    print('EBA')
                    
                
                
            pass
            
    if tela is T_OP:
        if entrando:
            print('A')
            enviar('tOp', 'TOP')
        else:
            print(mensagem)
            pass
            
    if tela is T_LOTE:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_METsemAD:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_METcomAD:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_OPERADOR:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_ROLO:
        if entrando:
            pass
        else:
            print(mensagem)
            pass
            
    if tela is T_PRODUZINDO:
        if entrando:
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
            print(mensagem)
            pass
            
    if tela is -1:
        print('fudeu')
    

  

LeitorNextion()
rtc = Clock()
                
while True:
    pass
                    
            
        
