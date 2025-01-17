from tensorflow.keras.models import load_model
import numpy as np

def generate_ports(moduleName,fout,inputSize,outputSize,inputBits,outputBits):

  fout.write(f"module {moduleName}(\n")

  for input_port_num in range(inputSize):
    fout.write(f"input [{inputBits-1}:0] x{input_port_num} ,\n") 

  for out_port_num in range(outputSize-1):
    fout.write(f"output [{outputBits-1}:0] y{out_port_num} ,\n")     

  fout.write(f"output [{outputBits-1}:0] y{outputSize-1} \n);\n")




def helper(inputIndex,weightValue,fout):

  if weightValue==1:
    fout.write(f"+$signed( {{ 5'b0,x{inputIndex}  }}<<<3'd4 )")
  elif weightValue==0.5:
    fout.write(f"+$signed( {{ 4'b0,x{inputIndex} }}<<<3'd3 )")
  elif weightValue==0.25:
    fout.write(f"+$signed( {{ 3'b0,x{inputIndex} }}<<<3'd2 )")
  elif weightValue==0.125: 
    fout.write(f"+$signed( {{ 2'b0,x{inputIndex} }} <<<3'd1 )")
  elif weightValue==0.0625:
    fout.write(f"+$signed( {{ 1'b0,x{inputIndex} }}  )")
  elif weightValue==-0.0625:
    fout.write(f"+$signed( -{{ 1'b0,x{inputIndex} }} )")
  elif weightValue==-0.125:
    fout.write(f"+$signed( -{{ 2'b0,x{inputIndex} }}<<<3'd1 )")
  elif weightValue==-0.25:
    fout.write(f"+$signed( -{{ 3'b0,x{inputIndex} }}<<<3'd2)")
  elif weightValue==-0.5:
    fout.write(f"+$signed( -{{ 4'b0, x{inputIndex} }}<<<3'd3 )")
  elif weightValue==-1:
    fout.write(f"+$signed( -{{ 5'b0,x{inputIndex} }}<<<3'd4 )")




def genconv(input_bits,output_bits,weights,bias,outputFile, moduleName, inputShape, outputShape, channelFirst=False, kernelSize=3, strides=1,shift_amount=0,max=5,output_resolution=0,out_channelFirst=False):

  inputSize = inputShape[0]*inputShape[1]*inputShape[2]
  outputSize = outputShape[0]*outputShape[1]*outputShape[2]
  fout = open(outputFile, 'w')
  generate_ports(moduleName,fout,inputSize,outputSize,input_bits,output_bits)

  #temp_y is before activation
  fout.write(f"wire signed[{output_bits+6}:0] temp_y  [0:{outputSize-1}];\n")

 
  for ho in range(outputShape[0]):
    for wo in range(outputShape[1]):
      for co in range(outputShape[2]):

        ##y[ho][wo][co] output channel last
        ##y[co][ho][wo] output channel first
        outputIndex=0

        if out_channelFirst==False:
          outputIndex = ho*outputShape[1]*outputShape[2] + wo*outputShape[2]+co
        else:
          outputIndex = co*outputShape[0]*outputShape[1] + ho*outputShape[1] + wo
        fout.write(f"assign temp_y[{outputIndex}] = \n")

        for hk in range(kernelSize):
          for wk in range(kernelSize):
            for ci in range(inputShape[2]):
              ##inputShape0:h,inputShape1:w,inputShape2:c
              inputIndex=0
              weightValue=0
              if channelFirst:
                ##inputindex[ci][ho*strides+hk][wk*stride+wk]
                inputIndex= ci*inputShape[0]*inputShape[1] + (ho*strides+hk)*inputShape[1] + wo*strides+wk
                weightValue = weights[hk,wk,ci,co]
              
              else :
                ##inputIndex[ho*strides+hk][wo*stride+wk][ci]
                inputIndex = (ho*strides+hk)*inputShape[1]*inputShape[2] + (wo*strides+wk)*inputShape[2] + ci
                weightValue = weights[hk,wk,ci,co]
               

              helper(inputIndex,weightValue,fout)
              
         
        if bias[co]>0:
          fout.write(f"+")
        else:
          fout.write(f"-")
        fout.write(f"$signed({output_bits+6}'d{abs(int(round(bias[co]*(2**(4+shift_amount)))))});")
        fout.write(f"\n")
        fout.write(f"assign y{outputIndex}=")
        #shift amount 是輸入是到小數地幾位(2進制)
        #start 是個位數起始bit
        #max relu最大值是二的max次方-1
        #output resolution 是輸出到小數地幾位
        start=4+shift_amount
        high = start-output_resolution+output_bits-1
        low = start-output_resolution
        
        fout.write(f'''temp_y[{outputIndex}][{output_bits + 6}] ==1'b1 ? {output_bits}'d0 :  
        temp_y[{outputIndex}][{start + max}] ==1'b1 ? {output_bits}'d{2**(max + output_resolution)-1} : 
        temp_y[{outputIndex}][{low - 1}]==1'b1 ? temp_y[{outputIndex}][{high}:{low}]+1'b1 : temp_y[{outputIndex}][{high}:{low}];\n''')
  
  fout.write(f"endmodule")



def generate_ports_dense(moduleName,fout,inputSize,inputBits,outputSize):

  fout.write(f"module {moduleName}(\n")
  
  for input_port_num in range(inputSize):
    fout.write(f"input [{inputBits-1}:0] x{input_port_num} ,\n") 

  fout.write(f"output [{outputSize-1}:0] y \n);\n")    




def gendense(input_bits,outputFile, moduleName, inputSize , outputSize , weight, bias ):

  
  fout = open(outputFile,"w")
  generate_ports_dense(moduleName,fout,inputSize,input_bits,outputSize)
  
  fout.write(f"wire signed[{input_bits+8}:0] temp_y  [0:{outputSize-1}];\n")


  for o in range(outputSize):

    #temp_y 用來算總和
    fout.write(f"assign temp_y[{o}] = \n")
    for i in range(inputSize):

      ##weight[i][o]
      weightValue=weight[i,o]
      helper1(i,weightValue,fout)

    if bias[o]>0:
        fout.write(f"+")
    else:
        fout.write(f"-")

    fout.write(f"$signed({input_bits+8}'d{abs(int(round(bias[o]*(2**(4+1))))) });\n")    
    
    if o > 0:
      if o==1:
        fout.write(f"wire [{input_bits+8}:0] max1;\n")
        fout.write(f"assign max1 = $signed(temp_y[0]) > $signed(temp_y[1]) ? temp_y[0] : temp_y[1];\n")
      else:
        fout.write(f"wire [{input_bits+8}:0] max{o};\n")    
        fout.write(f"assign max{o} = $signed(temp_y[{o}]) > $signed(max{o-1}) ? temp_y[{o}] : max{o-1};\n")


  for i in range(outputSize):

    fout.write(f"assign y[{i}]= max{outputSize-1} == temp_y[{i}] ? 1'b1 : 1'b0;\n")
    
  
  fout.write(f"endmodule")




def helper1(inputIndex,weightValue,fout):


  for i in range(3):

    if weightValue==0:
      return

    elif weightValue>0:

      if weightValue>=0.25:

        fout.write(f"+$signed( {{ 3'b0,x{inputIndex} }}<<<3'd2 )")
        weightValue = weightValue - 0.25

      elif weightValue>=0.125:

        fout.write(f"+$signed( {{ 2'b0,x{inputIndex} }} <<<3'd1 )")
        weightValue = weightValue - 0.125

      elif weightValue>=0.0625:

        fout.write(f"+$signed( {{ 1'b0,x{inputIndex} }}  )")
        weightValue = weightValue - 0.0625


    else:

      if weightValue<=-0.25:

        fout.write(f"+$signed( -{{ 3'b0,x{inputIndex} }}<<<3'd2)")
        weightValue = weightValue + 0.25
      
      elif weightValue<=-0.125:

        fout.write(f"+$signed( -{{ 2'b0,x{inputIndex} }}<<<3'd1 )")
        weightValue = weightValue + 0.125
      
      elif weightValue<=-0.0625:

        fout.write(f"+$signed( -{{ 1'b0,x{inputIndex} }} )")
        weightValue = weightValue + 0.0625



def gen_inner_dense(input_bits,outputFile, moduleName, inputSize , outputSize , weight , bias , shift_amount , output_resolution ,output_bits,max):

  fout = open(outputFile,"w")
  #generate_ports_dense(moduleName,fout,inputSize,input_bits,outputSize)

  generate_ports(moduleName,fout,inputSize,outputSize,input_bits,output_bits)
  
  fout.write(f"wire signed[{input_bits+8}:0] temp_y  [0:{outputSize-1}];\n")


  for o in range(outputSize):

    #temp_y 用來算總和
    fout.write(f"assign temp_y[{o}] = \n")
    for i in range(inputSize):

      ##weight[i][o]
      weightValue=weight[i,o]
      helper(i,weightValue,fout)

    if bias[o]>0:
        fout.write(f"+")
    else:
        fout.write(f"-")

    fout.write(f"$signed({input_bits+8}'d{abs(int(round(bias[o]*(2**(4+shift_amount))))) });\n")    
    
    start=4+shift_amount
    high = start-output_resolution+output_bits-1
    low = start-output_resolution
    
    fout.write(f"assign y{o}=")
    fout.write(f'''temp_y[{o}][{input_bits + 8}] ==1'b1 ? {output_bits}'d0 :  
    temp_y[{o}][{start + max}] ==1'b1 ? {output_bits}'d{2**(max + output_resolution)-1} : 
    temp_y[{o}][{low - 1}]==1'b1 ? temp_y[{o}][{high}:{low}]+1'b1 : temp_y[{o}][{high}:{low}];\n''')

  fout.write(f"endmodule")



##channel first
##from 32*32*3 8bits to 16*16*3 7bits
def bind(outputFile,moduleName,inputSize,outputSize,inputShape,outputShape):

  fout = open(outputFile,"w")
  generate_ports(moduleName,fout,inputSize,outputSize,8,7)

  for ho in range(outputShape[0]):
    for wo in range(outputShape[1]):
      for co in range(outputShape[2]):
        #x[co][ho*2][wo*2]
        input_index = co*inputShape[0]*inputShape[1]+ho*inputShape[1]*2+wo*2
        #y[co][ho][wo]
        output_index = co*outputShape[0]*outputShape[1]+ho*outputShape[1]+wo
        fout.write(f"assign y{output_index}=x{input_index}[7:1];\n")

  fout.write(f"endmodule")



def connect(fout,moduleType,instanceName,inWireName,outWireName,inputSize,outputSize,start):

  fout.write(f"{moduleType} {instanceName}(")

  for wire_in in range(start,start+inputSize):
    fout.write(f".x{wire_in-start}({inWireName}[{wire_in}]),\n")

  for wire_out in range(outputSize-1):
    fout.write(f".y{wire_out}({outWireName}[{wire_out}]),\n")
   
  fout.write(f".y{outputSize-1}({outWireName}[{outputSize-1}]) );\n")




def connect_input(fout,moduleType,instanceName,inWireName,outWireName,inputSize,outputSize):

  fout.write(f"{moduleType} {instanceName}(")

  for wire_in in range(inputSize):
    fout.write(f".x{wire_in}({inWireName}{wire_in}),\n")

  for wire_out in range(outputSize-1):
    fout.write(f".y{wire_out}({outWireName}[{wire_out}]),\n")
   
  fout.write(f".y{outputSize-1}({outWireName}[{outputSize-1}]) );\n")



def connect_output(fout,moduleType,instanceName,inWireName,inputSize):

  fout.write(f"{moduleType} {instanceName}(")

  for wire_in in range(inputSize):
    fout.write(f".x{wire_in}({inWireName}[{wire_in}]),\n")
  
  fout.write(f".y(y));\n")




def concatenate(fout,moduleType,instanceName,inWireName1,inWireName2,inputSize1,inputSize2,isOutput,outputSize,outWireName):
  
  fout.write(f"{moduleType} {instanceName}(")

  for wire_in in range(inputSize1):
    fout.write(f".x{wire_in}({inWireName1}[{wire_in}]),\n")

  for wire_in in range(inputSize1,inputSize1+inputSize2):
    fout.write(f".x{wire_in}({inWireName2}[{wire_in - inputSize1}]),\n")

  if isOutput:
    fout.write(f".y(y));\n")
  else:
    for wire_out in range(outputSize-1):
      fout.write(f".y{wire_out}({outWireName}[{wire_out}]),\n")
    fout.write(f".y{outputSize-1}({outWireName}[{outputSize-1}]) );\n")


def connect_tb(fout ,moduleType,instanceName,inwireName,internalwireName,inputSize):

  fout.write(f"{moduleType} {instanceName}(")

  for wire_in in range(inputSize):
    fout.write(f".{internalwireName}{wire_in}({inwireName}[{wire_in}]),\n")

  fout.write(f".y(out));\n")   


