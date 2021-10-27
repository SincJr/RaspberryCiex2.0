import serial 
import struct

ser = serial.Serial(
    port='/dev/ttyS0',
    baudrate=57600,      
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=0.05 #mudar pra 0 que fica bem mais rapido. 1 é melhor pra debug
    )
    
ff = struct.pack('B', 0xff)

ser.write(bytes("otraflag=10", 'iso-8859-1'))
ser.write(bytes("rest", 'iso-8859-1'))
ser.write(ff+ff+ff)
