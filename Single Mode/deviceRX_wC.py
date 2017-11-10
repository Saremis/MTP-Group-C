import RPi.GPIO as GPIO
from lib_nrf24 import NRF24
from math import *
import time
import spidev
import sys
import os.path
import pickle

def decompress(compressed):
    """Decompress a list of output ks to a string."""
    from cStringIO import StringIO
 
    # Build the dictionary.
    dict_size = 256
    dictionary = dict((i, chr(i)) for i in xrange(dict_size))
    # in Python 3: dictionary = {i: chr(i) for i in range(dict_size)}
 
    # use StringIO, otherwise this becomes O(N^2)
    # due to string concatenation in a loop
    result = StringIO()
    w = chr(compressed.pop(0))
    result.write(w)
    for k in compressed:
        if k in dictionary:
            entry = dictionary[k]
        elif k == dict_size:
            entry = w + w[0]
        else:
            raise ValueError('Bad compressed k: %s' % k)
        result.write(entry)
 
        # Add w+entry[0] to the dictionary.
        dictionary[dict_size] = w + entry[0]
        dict_size += 1
 
        w = entry
    return result.getvalue()

def main():	    
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(24, GPIO.OUT)
	GPIO.output(24,1)
	GPIO.setup(22, GPIO.OUT)
	GPIO.output(22,1)

	print("Receiver")
	pipes = [[0xe7, 0xe7, 0xe7, 0xe7, 0xe7], [0xc2, 0xc2, 0xc2, 0xc2, 0xc2]]
	payloadSize = 32
	channel_RX = 0x60
	channel_TX = 0x65

	#Initializa the radio transceivers with the CE ping connected to the GPIO22 and GPIO24
	radio_Tx = NRF24(GPIO, spidev.SpiDev())
	radio_Rx = NRF24(GPIO, spidev.SpiDev())
	radio_Tx.begin(0, 22)
	radio_Rx.begin(1, 24)

	#We set the Payload Size to the limit which is 32 bytes
	radio_Tx.setPayloadSize(payloadSize)
	radio_Rx.setPayloadSize(payloadSize)

	#We choose the channels to be used for one and the other transceiver
	radio_Tx.setChannel(channel_TX)
	radio_Rx.setChannel(channel_RX)

	#We set the Transmission Rate
	radio_Tx.setDataRate(NRF24.BR_250KBPS)
	radio_Rx.setDataRate(NRF24.BR_250KBPS)

	#Configuration of the power level to be used by the transceiver
	radio_Tx.setPALevel(NRF24.PA_LOW)
	radio_Rx.setPALevel(NRF24.PA_LOW)

	#We disable the Auto Acknowledgement
	radio_Tx.setAutoAck(False)
	radio_Rx.setAutoAck(False)
	radio_Tx.enableDynamicPayloads()
	radio_Rx.enableDynamicPayloads()

	#Open the writing and reading pipe
	radio_Tx.openWritingPipe(pipes[1])
	radio_Rx.openReadingPipe(1, pipes[0])

	#We print the configuration details of both transceivers
	radio_Tx.printDetails()
	print("*------------------------------------------------------------------------------------------------------------*")
	radio_Rx.printDetails()
	print("*------------------------------------------------------------------------------------------------------------*")

	original_flag = 'A'
	flag = ""
	flag_n = 0
	ctrl_flag_n = 0
	frame = []
	ctrlFrame = []
	str_frame = ""
	time_ack = 1
	outputFile = open("RxFileCompressed.txt", "wb")
	receivedPacket = 0
	receivedHandshakePacket = 0
	receivedControlPacket = 0
	numberOfPackets = 0

	#We listen for the control packet
	radio_Rx.startListening()
	while not (receivedHandshakePacket):
		str_Controlframe = ""
		if radio_Rx.available(0):
			print("RECEIVED CTRL")
			radio_Rx.read(frame, radio_Rx.getDynamicPayloadSize())
			for c in range(0, len(frame)):
				str_Controlframe = str_Controlframe + chr(frame[c])
			#print("CTRL frame: " + str_Controlframe)
			print("Sending ACK to CTRL")
			radio_Tx.write(list("ACK"))
			receivedHandshakePacket = 1

	numberOfPackets, numberofControlPackets = str_Controlframe.split(",")
	print(numberOfPackets)
	print(numberofControlPackets)
	
	radio_Rx.startListening()

	for x in range(0,int(numberofControlPackets)):
		ctrl_flag = chr(ord(original_flag) + ctrl_flag_n)
		timeout = time.time() + time_ack
		while not (receivedControlPacket):
			str_frame = ""
			if radio_Rx.available(0):
				radio_Rx.read(ctrlFrame, radio_Rx.getDynamicPayloadSize())
				print(ctrlFrame)
				print(ctrl_flag)
				if(chr(ctrlFrame[0]) == ctrl_flag):
					radio_Tx.write(list("ACK") + list(ctrl_flag))
					receivedControlPacket = 1
				else:
					print("Wrong message -> asking for retransmission")
					if flag_n == 0:
						radio_Tx.write(list("ACK") + list('J'))
					else:
						radio_Tx.write(list("ACK") + list(chr(ord(original_flag) + ctrl_flag_n-1)))
					timeout = time.time() + time_ack

		ctrl_flag_n = (ctrl_flag_n + 1) % 10
		receivedControlPacket = 0

	for i in range(0,int(numberOfPackets)):
		timeout = time.time() + time_ack
		flag = chr(ord(original_flag) + flag_n)
		while not (receivedPacket):
			str_frame = ""
			if radio_Rx.available(0):
				#print("RECEIVED PKT")
				radio_Rx.read(frame, radio_Rx.getDynamicPayloadSize())
				if(chr(frame[0]) == flag):
					for c in range(1, len(frame)):
					    str_frame = str_frame + chr(frame[c])
					str_decompressed = decompress(frame)
					outputFile.write(str_decompressed)
					radio_Tx.write(list("ACK") + list(flag))
					receivedPacket = 1
				else:
					print("Wrong message -> asking for retransmission")
					if flag_n == 0:
						radio_Tx.write(list("ACK") + list('J'))
					else:
						radio_Tx.write(list("ACK") + list(chr(ord(original_flag) + flag_n-1)))
					timeout = time.time() + time_ack
		flag_n = (flag_n + 1) % 10
		receivedPacket = 0
	outputFile.close()

if __name__ == '__main__':
	main()
