# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022-2023 Gergely Gálfi
#

import os

from .lazyalg import *
from .lexer import *
from .parser import *
from .types import *
from .error import *
        
def assertArgType(funcname, args, argidx, validtypes, pos = None, word = False, singlearg = False):
    if type(validtypes) != list:
        validtypes = [validtypes]
    if type(argidx) != list:
        argidx = [argidx]
        n = [0]
        retsingle = True
    else:
        n = range(len(argidx))
        retsingle = False
    argtype = []
    for i in n:
        at = args[argidx[i]].getType()
        argtype.append(at)
        if not at in validtypes and (not word or at.value != 'WORD'):
            stypes = [str(t) for t in validtypes]
            if word: stypes.append('WORD')
            raise QBLRuntimeError(pos, "function '%s' argument%s has type %s, but it should be %s" % (
                funcname, 
                '' if singlearg else ' ' + str(argidx[i]+1),
                argtype[i],
                ', '.join(stypes)))
    if retsingle:
        return argtype[0]
    else:
        return argtype
        
class Storage:
    def __init__(self, fridx, value = None, isFixed = False):
        self.fridx = fridx
        self.value = value
        self.isFixed = isFixed
        
def bool2bit(b):
    return QBLBitObject(1 if b else 0) 

class QBLFuncError(QBLInternalFunc):
    def __init__(self):
        super().__init__('error', 1)
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, QBLObjectType.Str, singlearg = True)
        raise QBLRuntimeError(None, arg.value)
        
class QBLFuncInput(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('input', 1)
        self.qm = qm
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, QBLObjectType.ObjType, singlearg = True)
        if arg.value == 'QBIT':
            ret = QBLQBitObject(self.qm.allocInputQBit())
            self.qm.arrinp.append(ret)
            return ret
        elif arg.value == 'STRWORD':
            if arg.bitstruct == None:
                nbits = None
            else:
                allquantum = True
                for bt in arg.bitstruct:
                    if bt == QBLObjectType.Bit:
                        allquantum = False
                        break
                if not allquantum:
                    nbits = None
                else:
                    nbits = len(arg.bitstruct)
            if nbits != None:
                ret = QBLWordObject(arg.signed, [QBLQBitObject(self.qm.allocInputQBit()) for i in range(nbits)])
                self.qm.arrinp.append(ret)
                return ret
                
        raise QBLRuntimeError(None, "function '%s' expects qbit type or a full quantum word type, but the argument was %s" % (
            self.name, str(arg)
        ))
        
class QBLFuncOutput(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('output', 1)
        self.qm = qm
        
    def call(self, args):
        ret = self.qm.setOutput(args[0])
        self.qm.arrout.append(ret)
        return ret
   
def convqstate(qm, starg, sttype, nbits = None):
    invcomp = False
    if sttype in [QBLObjectType.Dict, QBLObjectType.List]:
        if sttype == QBLObjectType.Dict:
            stbits = starg.nbits
            nst = 1<<stbits
            idxarr = starg.value
        else:
            nst = len(starg.value)
            stbits = 0
            while (nst >> stbits) > 1:
                stbits += 1
            if 1<<stbits != nst:
                raise QBLRuntimeError(None, 'a quantum state defined by a list with length of %d, but it should have a length of a power of 2' % nst)
            idxarr = range(nst)
        if nbits != None:
            if stbits != nbits:
                if sttype == QBLObjectType.List or stbits > nbits:
                    raise QBLRuntimeError(None, "state bit number of % is not compatible with operator's bit number of %d" % (stbits, nbits))
            stlen = 1<<nbits
        else:
            stlen = nst

        state = [ComplexValue.Zero for i in range(stlen)]
        
        for i in idxarr:
            cpxcomp = qm.cast(QBLObjectType.Cplx, starg[i])
            if cpxcomp == None:
                invcomp = True
                break
            state[i] = cpxcomp.value        
    else:
        stbits = 1
        if starg.value in [0, 1]:
            state = starg.value
        else:
            invcomp = True
    if invcomp:
        raise QBLRuntimeError(None, 'a quantum state should be either given as a 0-1 value or a complex valued list/dictionary')
    return (stbits, state)
             
class QBLFuncQBInit(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('qbinit', 2)
        self.qm = qm
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0 = assertArgType(self.name, args, 0, [QBLObjectType.QBit, QBLObjectType.List])
        type1 = assertArgType(self.name, args, 1, [QBLObjectType.Bit, QBLObjectType.Int, QBLObjectType.Dict])
        if type0 == QBLObjectType.List:
            nbits = len(arg0.value)
            lstqb = arg0.value
        else:
            nbits = 1
            lstqb = [arg0]
        
        qbarr = []
        for qbitobj in lstqb:
            if qbitobj.getType() != QBLObjectType.QBit:
                raise QBLRuntimeError(None, 'argument 1 should be either a qubit or an array of qubits, but instead got %s' % str(qbitobj))
            qbidx = qbitobj.value
            self.qm.allocQBit(qbidx)
            qbdata = self.qm.arrqb[qbidx]
            if len(qbdata.arrstep) > 0 or qbdata.isinput:
                raise QBLRuntimeError(None, 'qubit index %d has been initialized already' % qbidx)
            qbarr.append(qbidx)

        stbits, state = convqstate(self.qm, arg1, type1)
        if nbits != stbits:
            raise QBLRuntimeError(None, 'number of qubit indices are not consistent with states bits, %d != %d' % (nbits, stbits))
        self.qm.addStep(StepQBInit(qbarr, state))
        return None       
        
class QBLFuncQState(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('qstate', 1)
        self.qm = qm
        
    def call(self, args):
        argtype = assertArgType(self.name, args, 0, [QBLObjectType.Bit, QBLObjectType.Int, QBLObjectType.Dict], singlearg = True)
        
        stbits, state = convqstate(self.qm, args[0], argtype)
        qbarr = []
        ret = []
        for i in range(stbits):
            qbidx = self.qm.allocQBit()
            qbarr.append(qbidx)
            ret.append(QBLQBitObject(qbidx))
        self.qm.addStep(StepQBInit(qbarr, state))
        return QBLListObject(ret)

class QBLFuncApplyOp(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('applyop', 2)
        self.qm = qm
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0 = assertArgType(self.name, args, 0, [QBLObjectType.List], word=True)
        type1 = assertArgType(self.name, args, 1, [QBLObjectType.Dict, QBLObjectType.List])
        
        nbits = len(arg0.value)
        nbase = 1<<nbits
        rbase = range(nbase)
        
        qbarr = []
        for i in range(nbits):
            qbit = arg0.value[i]
            if qbit == None or qbit.getType() != QBLObjectType.QBit:
                raise QBLRuntimeError(None, 'argument 1 should be a list or word of all qubits')
            qbarr.append(qbit.value)
            
        if type1 == QBLObjectType.Dict:
            nrowbits = arg1.nbits
            nrows = 1 << nrowbits
            idxarr = arg1.value
        else:
            nrows = len(arg1.value)
            nrowbits = 0
            while (nrows >> nrowbits) > 1:
                nrowbits += 1
            if 1<<nrowbits != nrows:
                raise QBLRuntimeError(None, 'an operator defined by a list with length of %d, but it should have a length of a power of 2' % nrows)
            idxarr = range(nrows)

        if nbits != nrowbits:
            raise QBLRuntimeError(None, 'argument 1 and 2 have inconsistent lengths (%d bits != %d bits)' % (nbits, nrowbits))
            
        opmatr = [None for i in  rbase]
        for i in idxarr:
            rowval = arg1.value[i]
            stbits, state = convqstate(self.qm, rowval, rowval.getType(), nbits)
            opmatr[i] = state      
            
        isutr = True
        for row in opmatr:
            if row == None:
                isutr = False
                break
                
        if isutr:
            evalop = [[z.evaluate() for z in row] for row in opmatr]
            for i in rbase:
                for k in rbase:
                    testval = sum([evalop[i][s] * (evalop[k][s].conjugate()) for s in rbase  ])
                    if i == k:
                        testval -= 1.0 + 0j
                    if (testval * (testval.conjugate())).real > 0.0001:
                        isutr = False
                        break
                if not isutr: break
                    
        if not isutr:
            raise QBLRuntimeError(None, 'operator failed unitarity test')
                        
        self.qm.addStep(StepApplyOp(qbarr, opmatr))
        return None     

class QBLFuncStartHedge(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('starthedge', 0)
        self.qm = qm
        
    def call(self, args):
        self.qm.startHedge()
        
class QBLFuncEndHedge(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('endhedge', 0)
        self.qm = qm
        
    def call(self, args):
        self.qm.endHedge()
    
class QBLFuncGetType(QBLInternalFunc):
    def __init__(self):
        super().__init__('type', 1)
        
    def call(self, args):
        return args[0].getType()
    
class QBLFuncIsWord(QBLInternalFunc):
    def __init__(self):
        super().__init__('isword', 1)
        
    def call(self, args):
        return bool2bit(args[0].getType().value == 'WORD')
    
class QBLFuncIsSigned(QBLInternalFunc):
    def __init__(self):
        super().__init__('issigned', 1)
        
    def call(self, args):
        arg = args[0]
        argtype = arg.objtype
        if argtype.value == 'INT':
            ret = True
        elif argtype.value == 'WORD':
            ret = argtype.signed
        else:
            ret = False
        return bool2bit(ret)

class QBLFuncLen(QBLInternalFunc):
    def __init__(self):
        super().__init__('len', 1)
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, QBLObjectType.List, word = True, singlearg = True)
        return QBLIntObject(len(arg.value))
    
class QBLFuncAlloc(QBLInternalFunc):
    def __init__(self):
        super().__init__('alloc', 1)
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, [QBLObjectType.Int, QBLObjectType.Bit], singlearg = True)
        n = arg.value
        if n<0:
            raise QBLRuntimeError(None, 'function %s accepts only non-negative argument, but %d was found' % (self.name, n))
        return QBLListObject([None for i in range(n)])  

class QBLFuncLogNot(QBLInternalFunc):
    def __init__(self):
        super().__init__('__lognot__', 1)
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, [QBLObjectType.Int, QBLObjectType.Bit], singlearg = True)
        return bool2bit(arg.value == 0)
    
class QBLFuncLogAnd(QBLInternalFunc):
    def __init__(self):
        super().__init__('__logand__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        assertArgType(self.name, args, [0, 1], [QBLObjectType.Int, QBLObjectType.Bit])
        return bool2bit(arg0.value!=0 and arg1.value != 0)

class QBLFuncLogOr(QBLInternalFunc):
    def __init__(self):
        super().__init__('__logor__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        assertArgType(self.name, args, [0, 1], [QBLObjectType.Int, QBLObjectType.Bit])
        return bool2bit(arg0.value != 0 or arg1.value != 0)
    
class QBLFuncLogXor(QBLInternalFunc):
    def __init__(self):
        super().__init__('__logxor__', 2)
        
    def call(self, args):
        assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Bit])
        return bool2bit((args[0].value!=0) != (args[1].value != 0))
    
class QBLFuncIdentical(QBLInternalFunc):
    def __init__(self):
        super().__init__('===', 2)
        
    def call(self, args):
        return bool2bit(args[0] == args[1])
    
class QBLFuncNIdentical(QBLInternalFunc):
    def __init__(self):
        super().__init__('!==', 2)
        
    def call(self, args):
        return bool2bit(args[0].value != args[1].value)

class QBLFuncLessThan(QBLInternalFunc):
    def __init__(self):
        super().__init__('__lt__', 2)
        
    def call(self, args):
        type0, type1 = assertArgType(self.name, args, [0, 1], [QBLObjectType.Int, QBLObjectType.Bit])
        return bool2bit(args[0].value<args[1].value)

class QBLFuncShift(QBLInternalFunc):
    def __init__(self, name):
        super().__init__(name, 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0 = assertArgType(self.name, args, 0, [QBLObjectType.Int, QBLObjectType.Bit, QBLObjectType.QBit], word=True)
        type1 = assertArgType(self.name, args, 1, [QBLObjectType.Int, QBLObjectType.Bit], word=True)
        
        if type1.value == 'WORD':
            sbits = arg1.toint()
        else:
            sbits = arg1.value
            
        if sbits<0:
            raise QBLRuntimeError(None, 'value of %d as bit count is not allowed (less than zero)' % sbits)
        return self.doshift(arg0, type0, sbits)  
    
class QBLFuncRightShift(QBLFuncShift):
    def __init__(self):
        super().__init__('>>')
        
    def doshift(self, arg, argtype, sbits):        
        if sbits == 0:
            return arg
        argval = arg.value
        if argtype.value == 'INT':
            return QBLIntObject(argval>>sbits)
        elif argtype.value == 'BIT':
            return QBLBitObject(argval>>sbits)
        elif argtype.value == 'QBIT':
            return QBLBitObject(0)
        else:             
            n = len(argval)
            if sbits < n:
                r = range(sbits)
            else:
                r = range(n)     
            if argtype.signed:
                lastbit = argval[n-1]
            else:
                lastbit = QBLBitObject(0)
            retlst = [lastbit for i in r]
            if sbits < n:
                retlst2 = argval[sbits:n]
                retlst2.extend(retlst)
                retlst = retlst2
            return QBLWordObject(argtype.signed, retlst)
        
class QBLFuncLeftShift(QBLFuncShift):
    def __init__(self):
        super().__init__('<<')
        
    def doshift(self, arg, argtype, sbits):
        if sbits == 0:
            return arg
        argval = arg.value
        if argtype.value == 'INT':
            return QBLIntObject(arg.value<<sbits)
        elif argtype.value == 'BIT':
            return QBLBitObject(arg.value>>sbits) #We want to be the value 0 for sbits > 0
        elif argtype.value == 'QBIT':
            return QBLBitObject(0) if sbits == 0 else arg
        else:
            n = len(argval)
            if sbits < n:
                r = range(sbits)
            else:
                r = range(n)     
            newbit = QBLBitObject(0)
            retlst = [newbit for i in r]
            if sbits < n:
                retlst.extend(arg.value[0:(n - sbits)])
            return QBLWordObject(argtype.signed, retlst)
        
def cplxargs(arg0, type0, arg1, type1, allowint):
    if type0 == QBLObjectType.Cplx:
        z0 = arg0
        if type1 == QBLObjectType.Cplx:
            z1 = arg1
        else:
            z1 = QBLCplxObject(ComplexValue(real = RationalValue('INT',  arg1.value)))
    elif type1 == QBLObjectType.Cplx:
        z0 = QBLCplxObject(ComplexValue(real = RationalValue('INT',  arg0.value)))
        z1 = arg1
    elif allowint:
        z0 = None
        z1 = None
    else:
        z0 = QBLCplxObject(ComplexValue(real = RationalValue('INT',  arg0.value)))
        z1 = QBLCplxObject(ComplexValue(real = RationalValue('INT',  arg1.value)))
    return (z0, z1)
        
class QBLFuncAdd(QBLInternalFunc):
    def __init__(self):
        super().__init__('__add__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0, type1 = assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Cplx, QBLObjectType.Str, QBLObjectType.Bit])
        
        if type0 == QBLObjectType.Str:
            isstr = True
            mismatch = (type1 != QBLObjectType.Str)
        else:
            isstr = False
            mismatch = (type1 == QBLObjectType.Str)
                           
        if mismatch:
            raise QBLRuntimeError(None, 'function %s has mismatching types: %s and %s' % (self.name, str(arg0.objtype), str(arg1.objtype)))
        
        if isstr:
            return QBLStrObject(arg0.value + arg1.value)
        z0, z1 = cplxargs(arg0, type0, arg1, type1, True)
        if z0 != None:
            return QBLCplxObject(z0.value + z1.value)
        else:
            return QBLIntObject(arg0.value + arg1.value)
        
class QBLFuncSub(QBLInternalFunc):
    def __init__(self):
        super().__init__('__sub__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0, type1 = assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Cplx, QBLObjectType.Bit])
        z0, z1 = cplxargs(arg0, type0, arg1, type1, True)
        if z0 != None:
            return QBLCplxObject(z0.value - z1.value)     
        return QBLIntObject(arg0.value-arg1.value)

class QBLFuncMul(QBLInternalFunc):
    def __init__(self):
        super().__init__('__mul__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0, type1 = assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Cplx, QBLObjectType.Bit])
        z0, z1 = cplxargs(arg0, type0, arg1, type1, True)
        if z0 != None:
            return QBLCplxObject(z0.value * z1.value) 
        return QBLIntObject(arg0.value * arg1.value)    
    
class QBLFuncTrueDiv(QBLInternalFunc):
    def __init__(self):
        super().__init__('__truediv__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0, type1 = assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Cplx, QBLObjectType.Bit])
        z0, z1 = cplxargs(arg0, type0, arg1, type1, False)
        return QBLCplxObject(z0.value / z1.value)

class QBLFuncIntDiv(QBLInternalFunc):
    def __init__(self):
        super().__init__('__intdiv__', 2)
        
    def call(self, args):
        arg0 = args[0]
        arg1 = args[1]
        type0, type1 = assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Bit])
        try:
            return QBLListObject([QBLIntObject(arg0.value // arg1.value), QBLIntObject(arg0.value % arg1.value)]) 
        except ZeroDivisionError:
            raise QBLRuntimeError(None, 'Division by zero')
    
class QBLFuncNeg(QBLInternalFunc):
    def __init__(self):
        super().__init__('__neg__', 1)
        
    def call(self, args):
        arg = args[0]
        argtype = assertArgType(self.name, args, 0, [QBLObjectType.Int, QBLObjectType.Cplx, QBLObjectType.Bit], singlearg = True)
        if argtype == QBLObjectType.Cplx:
            return QBLCplxObject(-arg.value)
        else:
            return QBLIntObject(-arg.value)

class QBLComplexFunc(QBLInternalFunc):
    def __init__(self, name, nargs):
        super().__init__(name, nargs)
        
    def call(self, args):
        newargs = []
        for i in range(self.nargs):
            arg = args[i]
            argtype = assertArgType(
                self.name,
                args,
                i,
                [QBLObjectType.Int, QBLObjectType.Cplx, QBLObjectType.Bit],
                singlearg = (self.nargs == 0))
            if argtype == QBLObjectType.Cplx:
                z = arg.value
            else:
                z = ComplexValue(real = RationalValue('INT',  arg.value))
            newargs.append(z)
        return QBLCplxObject(ComplexValue(funcname = self.name, arrarg = newargs))
    
class QBLFuncPrint(QBLInternalFunc):
    def __init__(self):
        super().__init__('print', 1)
        
    def call(self, args):
        print(str(args[0]))
        return None
    
class QBData:
    def __init__(self, qbidx):
        self.qbidx = qbidx
        self.compridx = None
        self.arrstep = []
        self.isinput = False
        self.isoutput = False
        
    def __str__(self):
        return 'QBData(qbidx = %d, arrstep = %s,  isinput = %s, isoutput = %s)' % (self.qbidx, str(self.arrstep), str(self.isinput), str(self.isoutput))
    
class QLStep:
    def __init__(self, typeid, arrqb):
        self.typeid = typeid
        self.arrqb = arrqb
        self.nqb = len(arrqb)
        self.nbase = 1<<self.nqb
        self.id = None
        
    def reindex(self, oldidx, newidx):
        if oldidx in self.arrqb:
            self.arrqb[self.arrqb.index(oldidx)] = newidx
            
    def delQB(self, qbidx):
        self.arrqb.pop(self.arrqb.index(qbidx))
        self.nqb = len(self.arrqb)
        self.nbase = 1<<self.nqb
        
class StepQBInit(QLStep):
    def __init__(self, arrqb, state):
        super().__init__('INIT', arrqb)
        if type(state) == int:
            if state == 0:
                self.state = [ComplexValue(real = RationalValue('INT', 1)), ComplexValue()]
            elif state == 1:
                self.state = [ComplexValue(), ComplexValue(real = RationalValue('INT', 1))]
        else:
            self.state = state
        
    def __str__(self):
        return 'qbinit(%s, {%s})' % (str(self.arrqb), ', '.join([str(int2word(k, self.nqb)) + ' : ' + str(self.state[k]) for k in range(self.nbase)]))
    
class StepApplyTbl(QLStep):
    def __init__(self, arrqbin, arrqbout, arrcopy, tbl):
        super().__init__('APPTBL', list(set(arrqbin + arrqbout)))
        self.nin = len(arrqbin)
        self.nout = len(arrqbout)
        self.arrqbin = arrqbin
        self.arrqbout = arrqbout
        self.arrcopy = arrcopy
        self.tbl = tbl
    
    def reindex(self, oldidx, newidx):
        super().reindex(oldidx, newidx)
        if oldidx in self.arrqbin:
            self.arrqbin[self.arrqbin.index(oldidx)] = newidx
        if oldidx in self.arrqbout:
            self.arrqbout[self.arrqbout.index(oldidx)] = newidx
        
    def delOutQB(self, qbidx):
        idx = self.arrqbout.index(qbidx)
        masklo = (1<<idx) - 1
        maskhi = (~masklo)<<1
        for i in range(len(self.tbl)):
            val = self.tbl[i]
            self.tbl[i] = (val & masklo) | ((val & maskhi)>>1)
        self.arrqbout.pop(idx)
        self.nout -= 1
        if qbidx not in self.arrqbin:
            self.delQB(qbidx)
            return True
        else:
            return False
            
    def __str__(self):
        return '''applytbl(qbin=%s, qbout=%s, copyin=%s\n  [%s])''' % (str(self.arrqbin), str(self.arrqbout),  str(self.arrcopy),
                      ',\n   '.join([str(int2word(i, self.nin)) + ' : ' + str(int2word(self.tbl[i], self.nout)) for i in range(len(self.tbl))]))
    
class StepApplyOp(QLStep):
    def __init__(self, arrqb, opmatr):
        super().__init__('APPOP', arrqb)
        self.opmatr = opmatr
    
    def __str__(self):
        return '''applyop(%s,\n  [%s])''' % (str(self.arrqb), 
                      ',\n   '.join([ ', '.join([str(self.opmatr[i][k]) for k in range(self.nbase)]) for i in range(self.nbase)]))
class Hedge:
    def __init__(self, parent):
        self.parent = parent
        self.arrchld = []
        self.startidx = None
        self.endidx = None
        
    def __str__(self):
        if self.parent == None:
            return 'Root hedge'
        else:
            return 'Hedge(startidx=' + str(self.startidx) + ', endidx=' + str(self.endidx) + ')'
        
class StepHedgeStart(QLStep):
    def __init__(self, hedge):
        super().__init__('HDGSTART', [].copy())
        self.hedge = hedge
        
    def __str__(self):
        return 'starthedge()'

class StepHedgeEnd(QLStep):
    def __init__(self, hedge):
        super().__init__('HDGEND', [].copy())
        
    def __str__(self):
        return 'endhedge()'

class QuantumLogic:
    def __init__(self, imppath = [], preload = ['base']):
        self.impsrcpath = []
        self.imppath = imppath
        self.impsyspath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qbl')
        self.globalfr={}
        self.arrfr = [self.globalfr]
        self.callstack = []

        self.setGlobal('objtype', QBLObjectType.ObjType)
        self.setGlobal('function', QBLObjectType.Function)
        self.setGlobal('funclist', QBLObjectType.FuncList)
        self.setGlobal('list', QBLObjectType.List)
        self.setGlobal('int', QBLObjectType.Int)
        self.setGlobal('cplx', QBLObjectType.Cplx)
        self.setGlobal('str', QBLObjectType.Str)
        self.setGlobal('bit', QBLObjectType.Bit)
        self.setGlobal('qbit', QBLObjectType.QBit)
        self.setGlobal('word', QBLWordType.Word)
        self.setGlobal('uword', QBLWordType.UWord)
        self.setGlobal('qword', QBLWordType.QWord)
        self.setGlobal('quword', QBLWordType.QUWord)
        self.setGlobal('sqrt', QBLComplexFunc('sqrt', 1))
        self.setGlobal('exp', QBLComplexFunc('exp', 1))
        self.setGlobal('pi', QBLCplxObject(ComplexValue(funcname = 'π', arrarg = [])))
        
        self.addFunc(QBLFuncInput(self))
        self.addFunc(QBLFuncOutput(self))
        self.addFunc(QBLFuncQBInit(self))
        self.addFunc(QBLFuncQState(self))
        self.addFunc(QBLFuncApplyOp(self))
        self.addFunc(QBLFuncError())
        self.addFunc(QBLFuncStartHedge(self))
        self.addFunc(QBLFuncEndHedge(self))
        self.addFunc(QBLFuncGetType())
        self.addFunc(QBLFuncIsWord())
        self.addFunc(QBLFuncIsSigned())
        self.addFunc(QBLFuncLen())
        self.addFunc(QBLFuncAlloc())
        self.addFunc(QBLFuncLogNot())
        self.addFunc(QBLFuncLogAnd())
        self.addFunc(QBLFuncLogOr())
        self.addFunc(QBLFuncLogXor())
        self.addFunc(QBLFuncPrint())
        self.addFunc(QBLFuncIdentical())
        self.addFunc(QBLFuncNIdentical())
        self.addFunc(QBLFuncLessThan())
        self.addFunc(QBLFuncRightShift())
        self.addFunc(QBLFuncLeftShift())
        self.addFunc(QBLFuncAdd())
        self.addFunc(QBLFuncSub())
        self.addFunc(QBLFuncMul())
        self.addFunc(QBLFuncTrueDiv())
        self.addFunc(QBLFuncIntDiv())
        self.addFunc(QBLFuncNeg())
        
        self.arrqb = []
        self.arrqbcompr = None
        self.nqb = 0
        self.freeidx = 0
        self.maxidx = 0
        self.arrstep = []
        self.arrinp = []
        self.arrout = []
        self.roothdg = Hedge(None)
        self.currhdg = self.roothdg
        
        for pl in preload:
            self.importSrc(pl, None, sysonly = True)
            
    def raiseRuntimeError(self, pos, msg):
        raise QBLRuntimeError(pos, msg, callstack = self.callstack)
        
    def raiseImplError(self, pos):
        self.raiseRuntimeError(pos, 'this language feature has not been implemented yet')
        
    def raiseTargetError(self, pos):
        self.raiseRuntimeError(pos, 'assignment target should be either a name or element(s) of an array')
        
    def importSrc(self, impname, startpos, sysonly = False):
        if sysonly:
            arrpath = [self.impsyspath]
        else:
            if len(self.impsrcpath) > 0:
                arrpath = [self.impsrcpath[-1]]
            else:
                arrpath = ['.']
            arrpath.extend(self.imppath)
            arrpath.append(self.impsyspath)
        srcfile = None
        for p in arrpath:
            testpath = os.path.join(p, impname + '.qbl')
            if os.path.isfile(testpath): #TODO: make this case insensitive on extenstion (.qbl, .QBL, ... should be equally good)
                srcfile = testpath
                break
        if srcfile != None:
            self.compileSource(srcfile = srcfile)
        else:
            self.raiseRuntimeError(startpos, impname + " couldn't be found in search path")
    
    def setGlobal(self, name, value):
        self.globalfr[name] = Storage(
            0,
            value = value,
            isFixed = True)   
        
    def setValue(self, target, value, startpos, tgtidx = None):
        if tgtidx == None:
            if target.isFixed:
                elf.raiseRuntimeError(startpos, "fixed objects shouldn't be reassigned")
            target.value = value
        else:
            tgtarr = target.value
            if tgtidx < 0 or tgtidx >= len(tgtarr):
                self.raiseRuntimeError(startpos, 'index %d out of range' % tgtidx)
            tgtarr[tgtidx] = value
    
    def addFrame(self):
        ret = {}
        self.arrfr.append(ret)
        return ret
    
    def rmFrame(self):
        self.arrfr.pop()
    
    def setupTarget(self, name, local):
        storage = self.lookupName(name, None)
        curridx = len(self.arrfr)-1
        if storage != None and local and storage.fridx != curridx:
            storage = None
        if storage == None:
            storage = Storage(curridx, isFixed = False)
            self.arrfr[curridx][name] = storage
        return storage
    
    def lookupName(self, name, errorpos = None):
        for i in range(len(self.arrfr)-1, -1, -1):
            frame=self.arrfr[i]
            if name in frame: return frame[name]
        if errorpos != None:    
            self.raiseRuntimeError(errorpos, "name '%s' is not found" % name)
        else:
            return None 

    def addFunc(self, func):
        store = self.lookupName(func.name)
        if store != None:
            funclist = store.value
            if funclist == None or funclist.objtype != QBLObjectType.FuncList:
                self.raiseRuntimeError(func.cmd.startpos, 'name %s was already defined as a non-function list object, function cannot be added' %  func.name)
        else:
            funclist = QBLFuncListObject(func.name)
            self.arrfr[0][func.name] = Storage(0, value = funclist, isFixed = True)
                 
        funcs = funclist.value
        if func.nargs in funcs and funcs[func.nargs].functype == 'INTERNAL':
            self.raiseRuntimeError(func.cmd.startpos, 'function %s with %d arguments is internal, cannot be overriden' %  (func.name,  func.nargs))
        funclist.value[func.nargs] = func
            
    def allocQBit(self, idx = None):
        if idx == None: idx = self.freeidx
        if idx<0: return None
        lqb = len(self.arrqb)
        if idx >= lqb:
            if idx > lqb:
                self.arrqb.extend([None for i in range(idx - lqb)])
            self.arrqb.append(QBData(idx))
            if self.freeidx == idx:
                self.freeidx += 1
        else:
            if self.arrqb[idx] != None: return None
            self.arrqb[idx] = QBData(idx)
            if self.freeidx == idx:
                while self.freeidx < lqb and self.arrqb[self.freeidx] != None:
                    self.freeidx += 1       
        self.nqb += 1
        return idx
    
    def allocInputQBit(self):
        qbidx = self.allocQBit()
        qbdata = self.arrqb[qbidx]
        qbdata.isinput = True
        return qbidx
    
    def setOutput(self, obj, oldidx = None, newidx = None):
        reindex = oldidx != None
        objcls = obj.getType().value
        if objcls == 'QBIT':
            if reindex:
                if oldidx == obj.value:
                    return QBLQBitObject(newidx)
            else:
                self.arrqb[obj.value].isoutput = True
        elif objcls in ['WORD', 'LIST']:
            if objcls == 'LIST' and not reindex:
                obj = QBLListObject(obj.value.copy())
            for i in range(len(obj.value)):
                qb = obj.value[i]
                if reindex:
                    obj.value[i] =  self.setOutput(qb, oldidx, newidx)
                else:
                    self.setOutput(qb)
        return obj

    def cleanQBits(self):
        for i in range(len(self.arrqb)):
            qbdata = self.arrqb[i]
            if qbdata != None and len(qbdata.arrstep) == 0 and not qbdata.isoutput: #delete qubit
                self.arrqb[i] = None
                self.nqb -= 1
                if self.freeidx > i:
                    self.freeidx = i
    
    def comprQBits(self):
        self.arrqbcompr = []
        for qbdata in self.arrqb:
            if qbdata != None:
                qbdata.compridx = len(self.arrqbcompr)
                self.arrqbcompr.append(qbdata)
    
    def addStep(self, qmstep):
        stepidx = len(self.arrstep)
        qmstep.id = stepidx
        for qbidx in qmstep.arrqb:
            if qbidx < len(self.arrqb):
                qbdata = self.arrqb[qbidx]
            else:
                qbdata = None
            if qbdata == None:
                qbdata = self.arrqb[self.allocQBit(qbidx)]
            self.arrqb[qbidx].arrstep.append(stepidx)
        self.arrstep.append(qmstep)

    def popStepQB(self, stepidx, qbidx):
        qbdata = self.arrqb[qbidx]
        qbdata.arrstep.pop(qbdata.arrstep.index(stepidx))
    
    def delStep(self, stepidx):
        step = self.arrstep[stepidx]
        for qbidx in step.arrqb:
            self.popStepQB(stepidx, qbidx)
        self.arrstep[stepidx] = None
        
    def startHedge(self):
        newhdg = Hedge(self.currhdg)
        self.currhdg.arrchld.append(newhdg)
        self.currhdg = newhdg
        newhdg.startidx = len(self.arrstep)
        strthdg = StepHedgeStart(newhdg)
        self.addStep(strthdg)
        
    def endHedge(self):
        if self.currhdg.parent == None:
            self.raiseRuntimeError(None, "endhedge doesn't have preceeding starthedge call")
        endidx = len(self.arrstep)
        if endidx > self.currhdg.startidx + 1:
            endhdg = StepHedgeEnd(self.currhdg)
            self.currhdg.endidx = endidx
            self.addStep(endhdg)
        else:
            self.delLastHedge(self.currhdg)
        self.currhdg = self.currhdg.parent 
        
    def delLastHedge(self, hedge):
        self.arrstep[hedge.startidx] = None
        if hedge.endidx != None:
            self.arrstep[hedge.endidx] = None
        while len(self.arrstep) > 0 and self.arrstep[-1] == None:
            self.arrstep.pop(-1)
        parhdg = hedge.parent
        parhdg.arrchld.pop(len(parhdg.arrchld) - 1)

    def bit2qbit(self, value):
        qbidx = self.allocQBit()
        self.addStep(StepQBInit([qbidx], value))
        return QBLQBitObject(qbidx)
        
    def cast(self, tgttype, srcobj):
        if srcobj == None: return None
        srctype = srcobj.getType()
        if tgttype == srctype:
            return srcobj
        tgtclass = tgttype.value
        srcclass = srctype.value
    
        if tgtclass == 'STR':
            return QBLStrObject(str(srcobj))
        
        if tgtclass == 'CPLX':
            ival = self.cast(QBLObjectType.Int, srcobj)
            if ival == None: return None
            return QBLCplxObject(ComplexValue(real = RationalValue('INT', ival.value)))
        
        if srcclass == 'OBJTYPE' and srcobj.value == 'WORD':
            if tgtclass == 'LIST' :
                return QBLListObject(srcobj.bitstruct.copy())
            
        elif srcclass == 'BIT':
            if tgtclass == 'QBIT':
                return self.bit2qbit(srcobj.value)
            elif tgtclass == 'INT':
                return QBLIntObject(srcobj.value)
            elif tgtclass == 'STRWORD':
                rb = range(tgttype.nbits)
                bitlst = [srcobj.value if i == 0 else 0 for i in rb]
                for i in rb:
                    bitlst[i] = QBLBitObject(bitlst[i]) if tgttype.bitstruct == None or tgttype.bitstruct[i] == QBLObjectType.Bit else self.bit2qbit(bitlst[i])
                return QBLWordObject(tgttype.signed, bitlst)
        
        elif srcclass == 'QBIT':
            if tgtclass == 'STRWORD':
                rb = range(tgttype.nbits)
                bitlst = [srcobj if i == 0 else 0 for i in rb]
                
                for i in rb:
                    if i == 0:
                        if tgttype.bitstruct != None and tgttype.bitstruct[i] == QBLObjectType.Bit:
                            return None
                    else:
                        bitlst[i] = QBLBitObject(bitlst[i]) if tgttype.bitstruct == None or tgttype.bitstruct[i] == QBLObjectType.Bit else self.bit2qbit(bitlst[i])
            
                return QBLWordObject(tgttype.signed, bitlst)
            
        elif srcclass == 'INT':
            if tgtclass in ['BIT', 'QBIT']:
                if srcobj.value in [0, 1]:
                    if tgtclass == 'BIT':
                        return QBLBitObject(srcobj.value)
                    else:
                        return self.bit2qbit(srcobj.value)
            elif tgtclass == 'STRWORD':
                rb = range(tgttype.nbits)
                if (srcobj.value>>tgttype.nbits) not in [0, -1]:
                    return None
                bitlst = int2word(srcobj.value, tgttype.nbits)
                for i in rb:
                    bitlst[i] = QBLBitObject(bitlst[i]) if tgttype.bitstruct == None or tgttype.bitstruct[i] == QBLObjectType.Bit else self.bit2qbit(bitlst[i])
                return QBLWordObject(tgttype.signed, bitlst)
        
        elif srcclass == 'LIST':
            if tgtclass in ['WORD', 'STRWORD']:
                if tgtclass == 'STRWORD' and tgttype.nbits != len(srcobj.value): return None
                bitlst = srcobj.value.copy()
                if tgtclass == 'STRWORD':
                    strtgt = tgttype.bitstruct != None
                    qutgt = False
                else:
                    strtgt = False
                    qutgt = tgttype.allquantum
                for i in range(len(bitlst)):
                    val = bitlst[i]
                    if strtgt:
                        tbtype = tgttype.bitstruct[i]
                    elif qutgt or (val.objtype != None and val.objtype.value == 'QBIT'):
                        tbtype = QBLObjectType.QBit
                    else:
                        tbtype = QBLObjectType.Bit
                    newbit = self.cast(tbtype, bitlst[i])
                    if newbit == None: return None
                    bitlst[i] = newbit
                return QBLWordObject(tgttype.signed, bitlst)
                
        elif srcclass == 'WORD':
            if tgtclass == 'INT':
                retval = srcobj.toint()
                if retval == None: return None
                else: return QBLIntObject(retval)
            elif tgtclass in ['WORD', 'STRWORD']:
                srclen = len(srcobj.value)
                if tgtclass == 'STRWORD':
                    strtgt = tgttype.bitstruct != None
                    qutgt = False
                    tgtlen = tgttype.nbits
                    enlarge = tgtlen > srclen
                else:
                    strtgt = False
                    qutgt = tgttype.allquantum
                    enlarge = False
                    tgtlen = srclen
                
                if enlarge:
                    bitlst = srcobj.value.copy()
                    extbit = srcobj.value[srclen - 1] if srctype.signed else QBLBitObject(0)
                    for i in range(srclen, tgtlen):
                        bitlst.append(extbit)
                else:
                    if srctype.signed:
                        extbit = srcobj.value[tgtlen - 1]
                    else:
                        extbit = QBLBitObject(0)
                    for i in range(tgtlen, srclen):
                        if srcobj.value[i] != extbit:
                            return None
                    bitlst = srcobj.value[0:tgtlen] 
                for i in range(0, tgtlen):
                    sb = bitlst[i]
                    sbtype = sb.objtype.value
                    if strtgt:
                        tbtype = tgttype.bitstruct[i].value
                    elif qutgt:
                        tbtype = 'QBIT'
                    else:
                        tbtype = sbtype
                        
                    if tbtype != sbtype:
                        if tbtype == 'BIT': return None
                        else:
                            bitlst[i] = self.bit2qbit(sb)
                        
                return QBLWordObject(tgttype.signed, bitlst)
            elif tgtclass == 'LIST':
                return QBLListObject(srcobj.value.copy())
            
        return None
        
    def compileExpr(self, expr, nullable = False, isTarget = False):
        if isTarget and (expr.typeid != 'EXPFUNC' or expr.name != '#ELEMENT'):
            self.raiseTargetError(expr.startpos)
            
        if expr.typeid == 'EXPCONS':
            ret = expr.obj
            
        elif expr.typeid == 'EXPNAME':
            storage = self.lookupName(expr.name, errorpos = expr.startpos)
            if storage.value == None:
                self.raiseRuntimeError(expr.startpos, "variable %s is uninitialized and shouldn't be referenced" %  expr.name)
            ret = storage.value
            
        elif expr.typeid == 'EXPFUNC':
            qual = ( expr.name == '#QUALIFY' )
            elmt = ( expr.name == '#ELEMENT' )
            isarr = ( expr.name == '#ARRAY' )
            nargs = len(expr.arrarg)
            docast = False
            ret = None
            if qual or elmt or isarr: 
                idobj = None
            else:
                if expr.idexp != None:
                    idobj = self.compileExpr(expr.idexp)
                else:
                    idobj = self.lookupName(expr.name, errorpos = expr.startpos).value
                if idobj.objtype not in [None, QBLObjectType.FuncList,  QBLObjectType.Function]: 
                    self.raiseRuntimeError(idexp.startpos, "Object %s shouldn't be called as a function" % str(ret))
                if idobj.objtype == QBLObjectType.FuncList:
                    try:
                        idobj = idobj.value[nargs]
                    except KeyError:
                        self.raiseRuntimeError(expr.idexp.startpos, 'function %s is not defined for %d arguments, only for %s' % (
                            idobj.name,
                            nargs,
                            ', '.join([str(n) for n in idobj.value])
                        ))
                elif idobj.objtype == None:
                    if nargs != 1:
                        self.raiseRuntimeError(expr.startpos, "casting to object type %s needs exactly one argument" % str(idobj))
                    docast = True
                               
            args = [self.compileExpr(expr.arrarg[i]) for i in range(nargs)]
                
            if qual:
                baseobj = args[0]
                if baseobj.getType() != QBLObjectType.ObjType or baseobj.value != 'WORD':
                    self.raiseRuntimeError(expr.startpos, "%s shouldn't be qualified with {}" % str(args[0]))
                
                idxarg = args[1]
                argtype = idxarg.getType()
                if argtype == QBLObjectType.Int:
                    if idxarg.value>0:
                        ret = QBLStructuredWordType(baseobj, idxarg.value)
                elif argtype == QBLObjectType.List:
                    bitsok = (len(idxarg.value)>0)
                    bits = []
                    for e in idxarg.value:
                        if e == None:
                            self.raiseRuntimeError(expr.arrarg[1].startpos, 'qualifer should be a fully initialized array')
                        elif e not in [QBLObjectType.Bit, QBLObjectType.QBit]:
                            bitsok = False
                            break
                        bits.append(e)     
                    if bitsok:
                        ret = QBLStructuredWordType(baseobj, bits)
                if ret == None:    
                    self.raiseRuntimeError(expr.arrarg[1].startpos, 'a positive integer or an array of bit types is expected as qualifier')
                    
            elif elmt:
                arridx = None
                isidxarr = False
                baseobj = args[0]
                if baseobj != QBLObjectType.QBit and not baseobj.getType().hasElements:
                    self.raiseRuntimeError(expr.arrarg[1].startpos, "object of type %s doesn't provide elements" % str(baseobj.getType()))
                if nargs == 2:
                    idxarg = args[1]
                    argtype = idxarg.getType()
                    if argtype == QBLObjectType.Int or argtype == QBLObjectType.Str:
                        arridx = idxarg.value
                    elif argtype == QBLObjectType.List:
                        isidxarr = True
                        idxsok = (len(idxarg.value)>0)
                        idxs = []
                        for e in idxarg.value:
                            if e == None:
                                self.raiseRuntimeError(expr.arrarg[1].startpos, "index array shouldn't contain uninitialized element")
                            elif e.objtype != QBLObjectType.Int:
                                self.raiseRuntimeError(expr.arrarg[1].startpos, 'indices should be integers or array of integers')
                            idxs.append(e.value)     
                        
                        arridx = idxs                        
                else:
                    self.raiseRuntimeError(expr.startpos, 'multiindices are not allowed') #shouldn't arrive here though
                    
                if arridx == None:
                    self.raiseRuntimeError(expr.startpos, 'index value cannot be empty') 
                else:
                    if isidxarr:
                        retval = []
                        idxs = arridx
                    else:
                        idxs = [arridx]
                    if isTarget:
                        if baseobj.getType() != QBLObjectType.List:
                            self.raiseTargetError(expr.startpos)
                        return (baseobj, arridx)
                    for i in idxs:
                        try:
                            value = baseobj[i]
                            idxok = True
                        except IndexError:
                            idxok = False
                        except KeyError:
                            idxok = False
                        if not idxok:
                            self.raiseRuntimeError(expr.arrarg[1].startpos, "there isn't any element for index %s" % str(s))
                        if value == None:
                            self.raiseRuntimeError(expr.startpos, "shouldn't refer to uninitialized element")
                        if isidxarr:
                            retval.append(value)
                        else:
                            ret = value
                            
                    if isidxarr:
                        ret = QBLListObject(value = retval)
                            
            elif isarr:
                ret = QBLListObject(args)
            
            elif docast:
                ret =  self.cast(idobj, args[0])
                if ret == None:
                    self.raiseRuntimeError(expr.startpos, "object %s with type %s cannot be converted to type %s" % (str(args[0]), str(args[0].getType()), str(idobj)))
            else:
                if nargs != idobj.nargs:
                    self.raiseRuntimeError(expr.startpos, "function '%s' requires %d arguments but found %d" % (idobj.name, idobj.nargs, nargs))
                if idobj.functype == 'INTERNAL':
                    try:
                        ret = idobj.call(args)
                    except QBLRuntimeError as e:
                        self.raiseRuntimeError(expr.startpos, e.desc)
                        
                elif idobj.functype == 'SCRIPT':
                    self.callstack.append(expr)
                    funcfr = self.addFrame()
                    currfr = len(self.arrfr)-1
                    for i in range(idobj.nargs):
                        funcfr[idobj.cmd.args[i].name] = Storage(currfr, value = args[i], isFixed = False)
                    for bcmd in idobj.cmd.body:
                        ret = self.compileCommand(bcmd)
                        if ret != None:
                            ret = ret[0]
                            break
                    self.rmFrame()
                    self.callstack.pop()
                    
                elif idobj.functype == 'TABLE':
                    qbitdict = {}
                    cbits = []
                    cbitidxs = []
                    cval = 0 #cval will contain the classical input value
                    for i in range(nargs):
                        arg = args[i]
                        if arg.getType() == QBLObjectType.QBit: #If the arg is a qubit, we store it's reference
                            key = arg.value
                            if key in qbitdict:
                                qbitdict[key].append(i)
                            else:
                                qbitdict[key] = [i]
                        else:
                            bitval = self.cast(QBLObjectType.Bit, arg)
                            if bitval == None or bitval.value not in [0,1]:
                                self.raiseRuntimeError(expr.startpos, "table function '%s' requires a qbit or 0 or 1, but got %s for argument %d" % (idobj.name, str(args[i]), i))
                            cbits.append(bitval.value)
                            cval += bitval.value<<i
                            cbitidxs.append(i)
                    
                    nin = len(qbitdict)
                    rin = range(nin)
                    nout = idobj.cmd.body[1]
                    rout = range(nout)
                    truthtbl = idobj.cmd.body[2]
                    if nin == 0: 
                        outval = truthtbl[cval]
                        ret = [QBLBitObject((outval>>i)&1) for i in rout]
                    else:
                        invecs = [0 for i in rin]
                        outvecs = [0 for i in rout]
                        nitem = 1<<nin
                        ritem = range(nitem)
                        outvals = [0 for i in ritem]
                        arrqbin = [qb for qb in qbitdict]
                        copyins = [True for i in rin]
                        for i in ritem:
                            key = cval
                            for k in rin:
                                bitval = (i >> k) & 1
                                invecs[k] |= bitval << i
                                for l in qbitdict[arrqbin[k]]:
                                    key = key | (bitval << l)
                            outval = truthtbl[key]
                            outvals[i] = outval
                            for k in rout:
                                outvecs[k] |= ((outval>>k)&1)<<i
                        
                        #Check const outputs or whether the output matches any other input or output
                        cons1 = (1<<nitem)-1
                        mask = 0
                        idx = 0
                        ret = [None for i in rout]
                        retmap = [i for i in rout]
                        arrqbout = [] 
                        for i in rout:
                            newmask = mask<<1 | 1
                            outvec = outvecs[idx]
                            iscons = outvec in [0, cons1]
                            isinp = outvec in invecs
                            issame = outvec in outvecs[0:idx]
                            if iscons or issame or isinp:
                                for k in ritem:
                                    outval = outvals[k]
                                    outvals[k] = mask & outval | ((~newmask & outval)>>1)
                                outvecs.pop(idx)
                                retmap.pop(idx)
                                if iscons:
                                    ret[i] = bool2bit(outvec != 0)
                                elif isinp:
                                    inpidx = invecs.index(outvec)
                                    ret[i] = QBLQBitObject(arrqbin[inpidx]) 
                                else:
                                    ret[i] = ret[outvecs.index(outvec)]
                            else:
                                idx += 1
                                mask = newmask
                                qbidx = self.allocQBit()
                                ret[i] = QBLQBitObject(qbidx)
                                arrqbout.append(qbidx)
                        nout = len(outvecs)
                        rout = range(nout)
                        
                        if nout>0:
                            self.addStep(StepApplyTbl(arrqbin, arrqbout, copyins, outvals))
                    ret = QBLListObject(ret)
                else: 
                    self.raiseImplError(expr.startpos)
                
            if not nullable and ret == None:
                self.raiseRuntimeError(expr.startpos, "function %s expected to return a value, but it didn't" % idobj.name)
                
        elif expr.typeid == 'EXPDICT':
            dictobj = []
            ret = QBLDictObject(expr.nbits, {i : self.compileExpr(expr.dictexp[i]) for i in expr.dictexp })
                
        else:
            self.raiseImplError(expr.startpos)

        return ret
            
    def compileCommand(self, cmd):
        if cmd.typeid == 'IMPORT':
            self.importSrc(cmd.impname, cmd.startpos)
            
        elif cmd.typeid == 'CMDCALC':
            for i in range(len(cmd.tgtarr)):
                tgtexp = cmd.tgtarr[i]
                evalexp = cmd.evalarr[i]
                if(evalexp != None):
                    value = self.compileExpr(evalexp, nullable = (tgtexp == None))
                else:
                    value = None

                if tgtexp != None:
                    expr = tgtexp
                    if expr.typeid == 'EXPNAME':
                        storage = self.setupTarget(expr.name, cmd.local)
                        if value != None:                            
                            self.setValue(storage, value, tgtexp.startpos)
                    else:
                        tgtobj, tgtidx = self.compileExpr(tgtexp, isTarget = True)
                        tgtarr = tgtobj.value
                        if type(tgtidx) == list:
                            valtyp = value.getType()
                            if valtyp.value != 'LIST':
                                self.raiseRuntimeError(evalexp.startpos, 'when assigning to multiple array elements, the value should be also an array')
                            valarr = value.value
                            lenidx = len(tgtidx)
                            if lenidx != len(valarr):
                                self.raiseRuntimeError(cmd.startpos, 'target array indexes are not matching with source array length')
                        else:
                            valarr = [value]
                            tgtidx = [tgtidx]
                            lenidx = 1

                        tgttype = tgtobj.getType()
                        for i in range(lenidx):
                            self.setValue(tgtobj, valarr[i], tgtexp.startpos, tgtidx = tgtidx[i])
                        
        elif cmd.typeid == 'CMDFDEF':
            self.addFunc(QBLFuncObject(cmd.name, cmd = cmd))
        
        elif cmd.typeid == 'CMDRET':
            retval = self.compileExpr(cmd.retexp) if cmd.retexp != None else None
            return [retval]
            
        elif cmd.typeid in ['CMDIF', 'CMDWHILE']:
            while(True):
                condvalue = self.compileExpr(cmd.condition)
                condtype = condvalue.getType()
                if condtype.value not in ['INT', 'BIT']:
                    self.raiseRuntimeError(cmd.condition.startpos, 'condition should either int or bit type')
                if condvalue.value != 0:
                    if cmd.typeid == 'CMDIF':
                        cmdtoexec = cmd.iftrue
                    else:
                        cmdtoexec = cmd.command
                else:
                    if cmd.typeid == 'CMDIF':
                        cmdtoexec = cmd.iffalse
                    else: break
                if cmdtoexec != None:
                    retval = self.compileCommand(cmdtoexec)
                    if retval != None: return retval
                if cmd.typeid == 'CMDIF': break
                    
        elif cmd.typeid == 'CMDFOR':
            listobj = self.compileExpr(cmd.listexp)
            if listobj.getType() != QBLObjectType.List:
                self.raiseRuntimeError(cmd.listexp, 'can iterate a list only, instead found object with type '+str(listobj.getType()))
            storage = self.setupTarget(cmd.varname, True)
            for iterobj in listobj.value:
                storage.value = iterobj
                retval = self.compileCommand(cmd.command)
                if retval != None: return retval
                
        elif cmd.typeid == 'CMDBLCK':
            self.addFrame()
            retval = None
            for bcmd in cmd.arrcmd:
                retval = self.compileCommand(bcmd)
                if retval != None:
                    break
            self.rmFrame()
            return retval
        
        else:
            self.raiseImplError(cmd.startpos)
            
        return None
        
    def compileSource(self, source=None, srcfile=None):
        if srcfile != None:
            self.impsrcpath.append(os.path.dirname(srcfile))
        lexer=Lexer(source=source, srcfile=srcfile)
        while True:
            nextstm = parseCommand(lexer)
            if nextstm != None:
                self.compileCommand(nextstm)
            else:
                break
        if srcfile != None:
            self.impsrcpath.pop(-1)
        
    def compileParsed(self, parsed):
        for cmd in parsed:
            self.compileCommand(cmd)
    
    def reuseTblInps(self, step, stepidx):
        cntreusedold = 0
        for inidx in range(len(step.arrqbin)):
            qbidx1 = step.arrqbin[inidx]
            if qbidx1 not in step.arrqbout and not step.arrcopy[inidx]:
                for i2 in range(len(step.arrqbout)):
                    qbidx2 = step.arrqbout[i2]
                    if qbidx2 not in step.arrqbin:
                        qbd1 = self.arrqb[qbidx1]
                        qbd2 = self.arrqb[qbidx2]
                        qbd1.isoutput = qbd2.isoutput
                        qbd2.isoutput = False
                        arrnextst = qbd2.arrstep[1:]
                        for nextstidx in arrnextst:
                            self.arrstep[nextstidx].reindex(qbidx2, qbidx1)
                        for outidx in range(len(self.arrout)):
                            self.arrout[outidx] = self.setOutput(self.arrout[outidx], oldidx = qbidx2, newidx = qbidx1)
                        qbd1.arrstep.extend(arrnextst)
                        qbd2.arrstep = []
                        step.arrqbout[i2] = qbidx1
                        step.delQB(qbidx2)
                        cntreusedold += 1
                        break
        return cntreusedold
    
    def reduce(self, verbose = False):
        stepidx = len(self.arrstep) - 1
        cntunusednew = 0
        cntreusedold = 0
        while stepidx >= 0:
            currstep = self.arrstep[stepidx]
            if currstep != None:
                todel = False
                if currstep.typeid == 'APPTBL':
                    for qbidx in currstep.arrqb.copy():
                        qbdata = self.arrqb[qbidx]
                        if stepidx == qbdata.arrstep[len(qbdata.arrstep) - 1] and not qbdata.isoutput:
                            if qbidx in currstep.arrqbout:
                                if currstep.delOutQB(qbidx):
                                    cntunusednew += 1
                                    self.popStepQB(stepidx, qbidx)
                                    if verbose:
                                        print('Popping in step ', stepidx, 'qbit idx', qbidx)
                            else:
                                currstep.arrcopy[currstep.arrqbin.index(qbidx)] = False
                    cntreusedold += self.reuseTblInps(currstep, stepidx)

                    if currstep.nout == 0: 
                        todel = True

                    # TODO: to check whether the transformation is trivial
                    # if not todel:
                    #     todel = True
                    #     for i in range(1<<currstep.nin):
                    #         if currstep.tbl[i] != i:
                    #             todel = False
                    #             break

                if not todel:
                    for qbidx in currstep.arrqb:
                        qbdata = self.arrqb[qbidx]
                        if qbdata.isoutput or stepidx != qbdata.arrstep[len(qbdata.arrstep) - 1]:
                            todel = False
                            break
                if todel:
                    if verbose:
                        print('Deleting step', stepidx)
                    self.delStep(stepidx)
            stepidx -= 1
        self.cleanQBits()
        return {'cntunusednew' : cntunusednew, 'cntreusedold' : cntreusedold}
 
    def findClosestSteps(self, stepidx, limst, searchnext):
        stepdata = self.arrstep[stepidx]
        arrclosest = []
        if stepdata == None:
            return arrclosest
        for qbidx in stepdata.arrqb:
            qbdata = self.arrqb[qbidx]
            currstord = qbdata.arrstep.index(stepidx)
            if searchnext:
                if currstord + 1 < len(qbdata.arrstep):
                    closest = qbdata.arrstep[currstord + 1]
                    if closest <= limst:
                        arrclosest.append(closest)
            else:
                if currstord > 0:
                    closest = qbdata.arrstep[currstord - 1]
                    if closest >= limst:
                        arrclosest.append(closest)

        return list(set(arrclosest))

    def traverseSteps(self, stepidx1, stepidx2, upcnt, arrord = None):
        n = stepidx2-stepidx1
        if upcnt:
            limstidx = stepidx2
            dorder = 1
            ret = arrord[(len(arrord) - n - 1):]
            ret[0] = -1
        else:
            limstidx = stepidx1
            dorder = -1
            ret = [None for i in range(n+1)]
            ret[n] = 1

        for i in range(n):
            idx = i if upcnt else n - i
            order = ret[idx] if i > 0 else dorder
            if order != None and (not upcnt or order > 0):
                currstidx = stepidx1 + idx
                cst = self.findClosestSteps(currstidx, limstidx, searchnext = upcnt)
                for clsstidx in cst:
                    if not upcnt or clsstidx != limstidx:
                        ret[clsstidx - stepidx1] = order + dorder
        return ret

    def alignSteps(self, stepidx1, stepidx2, arrord):
        n = len(arrord)
        #x = [-1, -3, None, -2, 2, None, 2, 1]
        arrnnidx = [i for i in range(n) if arrord[i] != None]
        oldstepidx = [stepidx1 + i for i in arrnnidx]
        arrnn = [arrord[i] for i in arrnnidx]
        arrnn = [2 if x > 1 else (-2 if x < -1 else  x) for x in arrnn]
        nnn = len(arrnn)
        rnn = range(nnn)
        ordpairs=list(zip(arrnn, rnn))
        ordpairs.sort(key = lambda el: nnn * el[0] + el[1])
        newstepidx = [None] * nnn
        newstepidx = [oldstepidx[ordpairs[i][1]] for i in rnn]
        for i in rnn:
            newstepidx[ordpairs[i][1]] = oldstepidx[i]
        arrstep = [self.arrstep[stidx] for stidx in oldstepidx]
        allqbidx = []
        for i in rnn:
            st = arrstep[i]
            if st != None:
                allqbidx.extend(st.arrqb)
            self.arrstep[newstepidx[i]] = st
        allqbidx = list(set(allqbidx))
        for qbidx in allqbidx:
            qbsteps = self.arrqb[qbidx].arrstep

            for i in range(len(qbsteps)):
                qbst = qbsteps[i]
                k = oldstepidx.index(qbst) if qbst in oldstepidx else -1
                if k >=0:
                    qbsteps[i] = newstepidx[k]
            savesteps = qbsteps.copy()
            qbsteps.sort()
            if qbsteps != savesteps:
                print('Order error during align', stepidx1, stepidx2, qbidx, arrord)
                print(savesteps)
                print(qbsteps)
                print(oldstepidx, newstepidx)
                raise Exception()
                
                    
        return (newstepidx[0], newstepidx[-1])

    def joinSteps(
        self,
        mode = "HEDGED",
        maxinqb = 8,
        maxoutqb = None,
        jointoplev = True, 
        stepidx1 = None,
        stepidx2 = None,
        iterdata = None,
        verbose = False):

        maxstidx = len(self.arrstep) - 1
        if maxstidx < 0:
            return

        if mode == "HEDGED":
            currhdg = self.roothdg
            doscan = True
            ishedged = True
        elif mode == "UNHEDGED":
            ishedged = False
            doscan = True
            stepmin = 0
            stepidx2 = maxstidx
        elif mode == "SINGLE":
            if stepidx1 == None or stepidx2 == None:
                raise Exception('Single pair contraction requires valid stepidx1 and stepidx2 arguments')
            ishedged = False
            doscan = False
            stepmin = stepidx1
        else:
            raise Exception('Unkown mode: '+ str(mode))

        hdgcomp = False
        while True:  
            if ishedged:
                while True:
                    nchld = len(currhdg.arrchld)
                    if nchld > 0:
                        if verbose:
                            print('Going down from', currhdg, 'with children', nchld)
                            for h in currhdg.arrchld:
                                print('Child:', h)
                        currhdg = currhdg.arrchld[nchld - 1]
                        if verbose:
                            print('Going down to', currhdg, 'nchld:', len(currhdg.arrchld))
                        stepidx2 = currhdg.endidx
                        stepmin = currhdg.startidx
                    elif currhdg.parent != None:
                        if hdgcomp:
                            if verbose:
                                print('Hedge complete', currhdg)
                            self.delLastHedge(currhdg)
                            currhdg = currhdg.parent
                            if verbose:
                                print('Going up to', currhdg, 'with children', len(currhdg.arrchld))
                            stepidx2 = currhdg.endidx
                            stepmin = currhdg.startidx
                            if verbose:
                                for h in currhdg.arrchld:
                                    print('Child:', h)
                            hdgcomp = False
                        else:
                            #print('Terminal hedge', currhdg)
                            if stepidx2 == None:
                                raise Exception('Hedge %s has no ending step' % str(currhdg))
                            break                    
                    else:
                        ishedged = False
                        if jointoplev:
                            stepidx2 = len(self.arrstep) - 1
                            if stepidx2 < 0:
                                return
                        else:
                            stepidx2 = 0
                        stepmin = 0    
                        break
            #print('stepidx, stepmin', stepidx2, stepmin)
            step2 = self.arrstep[stepidx2]
            stepback = True
            if step2 != None and step2.typeid == 'APPTBL':
                arrclst = self.findClosestSteps(stepidx2, stepmin, False)
                if len(arrclst) > 0:
                    stmin = min(arrclst)
                    arrdncnt = self.traverseSteps(stmin, stepidx2, False)
                    if doscan:
                        if verbose:
                            print('Testing step', stepidx2)
                        candst = [i + stmin for i in range(len(arrdncnt)) if arrdncnt[i] == -2 and self.arrstep[i + stmin].typeid == 'APPTBL']
                        candst.sort()
                        candst.reverse()
                    else:
                        candst = [stepmin]
                else:
                    candst = []
                arrtest = []
                for stepidx1 in candst:                
                    step1 = self.arrstep[stepidx1]
                    newstep, newnin = joinTblPair(step1, step2, maxinqb, maxoutqb)
                    if verbose:
                        print('Test joining step %d with %d%s nin:(%d,%d) -> %d' % (
                            stepidx1, stepidx2,
                            (' on ' + str(currhdg)) if ishedged else '',
                            step1.nin, step2.nin, newnin))
                    if newstep != None:
                        oldqbarr = step1.arrqb.copy()
                        oldqbarr.extend(step2.arrqb)
                        oldqbarr = set(oldqbarr)
                        arrtest.append((stepidx1, newstep, oldqbarr))
                        invecs, outvecs = transposeTbl(newstep.tbl, newstep.nin, newstep.nout)
                        irr = testVecs(invecs, outvecs)
                        if verbose:                        
                            if len(irr) > 0:
                                print('Irrelevant inbits', irr)
                for stepidx1, newstep, oldqbarr in arrtest:
                    step1 = self.arrstep[stepidx1]
                    if newstep.nin <= maxinqb:
                        if verbose:
                            print('Joining step %d with %d' % (stepidx1, stepidx2))
                        arrupcnt = self.traverseSteps(stepidx1, stepidx2, True, arrdncnt)
                        newstidx1, newstidx2 = self.alignSteps(stepidx1, stepidx2, arrupcnt)
                        if verbose:
                            print('New indices:', newstidx1, newstidx2)

                        for qbidx in oldqbarr:
                            qbdata = self.arrqb[qbidx]
                            #print(qbdata)
                            if qbidx in newstep.arrqb:
                                if qbidx in step2.arrqb:
                                    if qbidx in step1.arrqb:
                                        self.popStepQB(newstidx1, qbidx)
                                else:
                                    if qbidx in step1.arrqb:
                                        qbdata.arrstep[qbdata.arrstep.index(newstidx1)] = newstidx2
                            else:
                                if qbidx in step1.arrqb:
                                        self.popStepQB(newstidx1, qbidx)
                                if qbidx in step2.arrqb:
                                        self.popStepQB(newstidx2, qbidx)
                            savesteps = qbdata.arrstep.copy()
                            savesteps.sort()
                            if qbdata.arrstep != savesteps:
                                print('Order error during join', stepidx1, stepidx2, newstidx1, newstidx2, qbidx)
                                print(arrupcnt)
                                print(qbdata.arrstep)                                
                                print(savesteps)
                                raise Exception()
                        self.arrstep[newstidx1] = None
                        self.arrstep[newstidx2] = newstep
                        reused = self.reuseTblInps(newstep, newstidx2)
                        if verbose:
                            print('Reused inputs: ' + str(reused))
                        stepback = False
                        if iterdata != None:
                            iterdata.append((
                                len([s for s in self.arrstep if s != None]),
                                len([q for q in self.arrqb if q != None and len(q.arrstep) > 0]),
                                max([s.nin for s in self.arrstep if s != None and s.typeid == 'APPTBL'])))
                        break
            if stepback:
                stepidx2 -= 1
            if not doscan:
                break
            elif stepidx2 < stepmin:
                if ishedged:
                    hdgcomp = True
                else:
                    break
        self.cleanQBits()

    def unitarize(self, verbose = False):
        cntinpused = 0
        cntnewqb = 0
        for stepidx in range(len(self.arrstep)):
            step = self.arrstep[stepidx]
            if step != None and step.typeid == 'APPTBL':
                outvals = step.tbl.copy()
                arrqbout = step.arrqbout.copy()
                nout = len(arrqbout)
                for inpidx in range(step.nin):
                    qbinidx = step.arrqbin[inpidx]
                    if step.arrcopy[inpidx]:
                        for i in range(len(outvals)):
                            outvals[i] |= ((i>>inpidx)&1)<<nout
                        arrqbout.append(qbinidx)
                        nout += 1
                
                nel = len(outvals)
                arrgrpcnt = {}
                arrgrpidx = []
                maxgrpidx = 0
                for i in range(nel):
                    val = outvals[i]
                    if val in arrgrpcnt:
                        grpidx = arrgrpcnt[val]
                    else:
                        grpidx = 0
                    arrgrpcnt[val] = grpidx + 1
                    arrgrpidx.append(grpidx)
                    if grpidx > maxgrpidx:
                        maxgrpidx = grpidx
                if maxgrpidx > 0:
                    cntstinpused = 0
                    cntstnewqb = 0
                    
                    grpbits = 0
                    i = maxgrpidx
                    while i > 0:
                        i = i>>1
                        grpbits += 1
                        
                    for i in range(len(outvals)):
                        outvals[i] |= arrgrpidx[i]<<nout
                        
                    inpidx = 0
                    while grpbits > 0 and inpidx < step.nin:
                        qbidx = step.arrqbin[inpidx]
                        if qbidx not in arrqbout:
                            arrqbout.append(qbidx)
                            grpbits -= 1
                            cntstinpused += 1
                        inpidx += 1
                        
                    while grpbits > 0:
                        newqb = self.allocQBit()
                        self.arrqb[newqb].arrstep.append(stepidx)
                        arrqbout.append(newqb)
                        grpbits -= 1
                        cntstnewqb += 1

                    self.arrstep[stepidx] = StepApplyTbl(
                        step.arrqbin,
                        arrqbout, [False for i in range(len(step.arrqbin))], outvals)
                    
                    cntinpused += cntstinpused
                    cntnewqb += cntstnewqb
                    
                    if verbose:
                        print('Step %d has %d inputs. Count of output values:%d < %d' % (stepidx, step.nin, len(arrgrpcnt), 1<<step.nin)) 
                        print('Maximum number of elements in a group with the same output value is %d' % (maxgrpidx + 1))
                        print('To unitarize, %d inputs are reused as output, %d new qubits introduced' % (cntstinpused, cntstnewqb))
                        print()
                            
        return {'cntnewqb' : cntnewqb, 'cntinpused' : cntinpused}
    
    def getObjBits(self, qblobj, arrbit, iscompr = False):
        objclass = qblobj.getType().value
        if objclass in ['WORD', 'LIST']:
            objarr = qblobj.value
        else:
            objarr = [qblobj]
        for el in objarr:
            eltype = el.getType()
            if eltype.value == 'QBIT':
                arrbit.append(self.arrqb[el.value].compridx if iscompr else el.value)
            elif eltype.value == 'LIST':
                self.getObjBits(el, arrbit, iscompr)
    
    def getOutBits(self, outidx, iscompr = False):
        qblobj = self.arrout[outidx]
        ret = []
        self.getObjBits(qblobj, ret, iscompr)
        return ret
              
    def getStat(self):
        ninit = 0
        ntbl = 0
        nop = 0
        nhdg = 0
        nst = 0
        maxnstqbin = 0
        maxnstqbout = 0
        nstqb = 0
        cplxworst = 0
        cplxbest = 0
        for step in self.arrstep:
            if step != None:
                if step.typeid == 'INIT':
                    ninit += 1
                elif step.typeid == 'APPTBL':
                    ntbl += 1
                    nstqbout = step.nout + sum(step.arrcopy)
                    maxnstqbin = step.nin if step.nin > maxnstqbin else maxnstqbin
                    maxnstqbout = nstqbout if nstqbout > maxnstqbout else maxnstqbout
                    cplxworst += ((1<<step.nin) - 1) * step.nout
                    cplxcnot = math.log((step.nqb) * (step.nqb - 1)) if step.nqb > 1 else 0
                    cplxdf = (1<<step.nin) * nstqbout
                    cplxln2df = math.log((1<<cplxdf) + 1) if cplxdf <= 20 else cplxdf*math.log(2)
                    cplxbest += math.ceil(cplxln2df / cplxcnot) - 1 if step.nqb > 1 else 0
                elif step.typeid == 'APPOP':
                    nop += 1
                elif step.typeid in ['HDGSTART', 'HDGEND']:
                    nhdg += 1
                else:
                    print(step)
                nstqb = step.nqb if step.nqb > nstqb else nstqb
                nst += 1
                
        return {
            'cntQubits' : self.nqb,
            'cntSteps': nst,
            'cntInitSteps': ninit,
            'cntTableSteps': ntbl,
            'cntGenOpSteps': nop,
            'cntHedgeSteps': nhdg,
            'maxCntStepQubits': nstqb,
            'maxCntStepInQubits': maxnstqbin,
            'maxCntStepOutQubits': maxnstqbout,
            'cplxWorst': cplxworst,
            'cplxBest' : cplxbest,
        }
            
    def __str__(self):
        ret = 'QuantumLogic:\nSteps:\n'
        for i in range(len(self.arrstep)):
            step = self.arrstep[i]
            if step != None:
                ret += 'step['+str(i) + '] = ' + str(step) + '\n'

        ret += 'Number of qubits:%d\n' % self.nqb
        ret += 'Qubits:\n'
        for qb in self.arrqb:
            ret += str(qb) + '\n'

        ret += 'Inputs:\n'
        for obj in self.arrinp:
            ret += str(obj) + '\n'

        ret += 'Outputs:\n'
        for obj in self.arrout:
            ret += str(obj) + '\n'
        
        return ret

def joinTblPair(step1, step2, maxinqb, maxoutqb):
    mask1 = (1<<step1.nin) - 1
    arrqbin = step1.arrqbin.copy()
    arrcopy = step1.arrcopy.copy()
    arrinmap = []
    for i in range(step2.nin):
        qb = step2.arrqbin[i]
        if qb in step1.arrqbout:
            src = 1
            srcbit = step1.arrqbout.index(qb)
        elif qb in step1.arrqbin:
            src = 0
            srcbit = step1.arrqbin.index(qb)
            arrcopy[srcbit] = step2.arrcopy[i]
        else:
            src = 0
            srcbit = len(arrqbin)
            arrqbin.append(qb)
            arrcopy.append(step2.arrcopy[i])
        arrinmap.append((src, srcbit, 1<<srcbit))
    nin = len(arrqbin)
    if nin > maxinqb:
        return (None, nin)
    arrqbout = []
    arroutmap = []
    for i in range(step1.nout):
        qb = step1.arrqbout[i]
        if not (qb in step2.arrqbout or (qb in step2.arrqbin and not step2.arrcopy[step2.arrqbin.index(qb)])):
            arrqbout.append(qb)
            arroutmap.append((i, 1<<i))
    arrqbout.extend(step2.arrqbout)
    nout = len(arrqbout)
    noutadd = len(arroutmap)
    if maxoutqb != None and nout > maxoutqb:
        return (None, nin)
    tbl = []
    for i in range(1<<nin):
        out1 = step1.tbl[mask1 & i]
        arrsrc = [i, out1]
        in2 = 0
        for k in range(step2.nin):
            inmap = arrinmap[k]
            in2 |= ((arrsrc[inmap[0]] & inmap[2])>>inmap[1])<<k
        outval = step2.tbl[in2]<<noutadd
        for k in range(noutadd):
            outmap = arroutmap[k]
            outval |= ((out1 & outmap[1])>>outmap[0])<<k
        tbl.append(outval)

    return (StepApplyTbl(arrqbin, arrqbout, arrcopy, tbl), nin)
    
def transposeTbl(tbl, nin, nout):
    invecs = [0]*nin
    outvecs = [0]*nout
    for i in range(1<<nin):
        for k in range(nin):
            invecs[k] |= ((i >> k) & 1) << i
        for k in range(nout):
            outvecs[k] |= ((tbl[i] >> k) & 1) << i
    return (invecs, outvecs)
    
def testVecs(invecs, outvecs):
    #Check input qubits' irrelevance
    arrirr = []
    nin = len(invecs)
    nout = len(outvecs)
    for i in range(nin):
        shift = (1<<i)
        invechi = invecs[i]
        inveclo = invechi>>shift
        irrel = True
        #print('Invec: ', invecs[i], inveclo, invechi, shift)
        for k in range(nout):
            #print('Outvec: ', k, outvecs[k], outvecs[k] & inveclo, outvecs[k] & invechi)
            if (outvecs[k] & inveclo)<<shift != outvecs[k] & invechi:
                irrel = False
                break
        if irrel:
            arrirr.append(i)
    return arrirr
        
