import numpy as np
import pickle

def getInd(s):
    ind1=s.find('[')
    ind2=s.find(']')
    return int(s[ind1+1:ind2])

def getXInd(s):
    ind1=s.find('x')
    ind2=s.find(' }')
    return int(s[ind1+1:ind2])

def getShift(s):
    ind1=s.find('<<<')
    if ind1==-1:
        return 0
    else:
        #ind2=s.find('')
        # print(s)
        # print("s:",s[ind1+3:ind2])
        return int(s[ind1+6:ind1+7])

numBits=5
cktFolder="cktFolder"
layerNames=["conv11","conv21","conv22","dense1","dense"]
zeroMats=[np.zeros((640,numBits*768)),np.zeros((288,numBits*512)),np.zeros((208,numBits*384)),np.zeros((20,numBits*496)),np.zeros((10,numBits*20))]
#layerNames=["conv11"]
stringRec=dict()
matrices=dict()

for i,layer in enumerate(layerNames):
    stringRec[layer]=[]
    matrices[layer]=zeroMats[i]
    f=open(f"{cktFolder}/{layer}.v",'r')
    lines=f.readlines()
    lInd=0
    while lInd<len(lines):
        l=lines[lInd]
        #print(l)
        if l.find("assign temp_y")!=-1:
            oInd=getInd(l)
            lInd+=1
            l=lines[lInd][1:]
            terms=l.split('+')
            for j,term in enumerate(terms):
                if term.find("-$signed")!=-1:
                    terms[j]=term.split("-$signed")[0]
            stringRec[layer].append(terms)
            #print(terms)
            for term in terms:
                if term.find("x")== -1:
                    continue
                #print("term: " ,term)
                neg=(term.find("-")!=-1)
                xInd=getXInd(term)
                shift=getShift(term)
                #print(neg,xInd,shift,sep=' ')
                if matrices[layer][oInd,xInd*numBits+(numBits-shift)-1]!=0:
                    matrices[layer][oInd,xInd*numBits+(numBits-shift)-1]=0
                    matrices[layer][oInd,xInd*numBits+(numBits-shift-1)-1]= -1 if neg else 1
                    assert(shift+1<=4)
                else:
                    matrices[layer][oInd,xInd*numBits+(numBits-shift)-1]= -1 if neg else 1
            
        lInd+=1

for i,layer in enumerate(layerNames):
    with open(f"parseRet/{layer}.npy",'wb') as f:
        np.save(f,matrices[layer])