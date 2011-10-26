import time
import serial
import struct
import matplotlib.pylab as pylab

ARRAY_SZ = 768
INWAITING_DT = 0.05
BUF_EMPTY_NUM = 3
BUF_EMPTY_DT = 0.01

class ArrayReader(serial.Serial):

    def __init__(self,**kwargs):
        try:
            self.streamStyle = kwargs.pop('stream_style')
        except KeyError:
            self.streamStyle = 'new'

        super(ArrayReader,self).__init__(**kwargs)
        time.sleep(2.0)

    def emptyBuffer(self):
        """
        Empty the serial input buffer.
        """
        for i in range(0,BUF_EMPTY_NUM):
            self.flushInput()
            time.sleep(BUF_EMPTY_DT)

    def getFakeData(self):
        fakeData = 800*pylab.ones((ARRAY_SZ,))
        fakeData[:200] = 0.0*fakeData[:200]
        return fakeData

    def getData(self):
        self.emptyBuffer()
        self.write('x\n')
        # Wait until all data has arrived.
        while self.inWaiting() < ARRAY_SZ*2: # 2 bytes per data point
            time.sleep(INWAITING_DT)

        if self.streamStyle == 'new':

            # Handles data from new firmware stream style
            data = []
            while len(data) < ARRAY_SZ and self.inWaiting() > 0:
                byteVals = self.read(2)
                value = struct.unpack('<h',byteVals[0:2])[0]
                data.append(value)

            if len(data) == ARRAY_SZ:
                return pylab.array(data)
            else:
                return None

        else:
            # Handles the old style streaming.
            line_list = []
            data_ok = True
            for line in self.readlines():
                line = line.split()
                if line:
                    try:
                        line = [int(x) for x in line]
                        line_list.extend(line)
                    except:
                        data_ok = False
            if data_ok:
                print 'ok'
                return pylab.array(line_list)
            else:
                return None
