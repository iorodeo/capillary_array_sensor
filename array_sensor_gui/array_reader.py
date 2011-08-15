import time
import serial
import matplotlib.pylab as pylab

class ArrayReader(serial.Serial):

    def __init__(self,**kwargs):
        super(ArrayReader,self).__init__(**kwargs)
        time.sleep(2.0)

    def getData(self):
        self.write('x\n')
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
            return pylab.array(line_list)
        else:
            return None
