# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022 Gergely Gálfi
#

import os

from .lazyalg import *
from .lexer import *
from .parser import *
from .types import *

class CompileError(Exception):
    def __init__(self, pos, msg):
        super().__init__('Compile error at %s: %s' % (str(pos), msg))
        self.msg = msg
        self.pos = pos
        
class UserError(Exception):
    def __init__(self, qm, pos, msg):
        super().__init__('User error at %s: %s\nCall stack:\n%s' % (
            str(pos),
            msg,
        ''.join([str(expr)+'\n' for expr in qm.callstack])))
        self.msg = msg
        self.pos = pos

def ImplError(pos):
    return CompileError(pos, 'this language feature has not been implemented yet')
        
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
            raise CompileError(pos, "function '%s' argument%s has type %s, but it should be %s" % (
                funcname, 
                '' if singlearg else ' ' + str(argidx[i]+1),
                argtype[i],
                ', '.join(stypes)))
    if retsingle:
        return argtype[0]
    else:
        return argtype
    

def TargetError(pos):
    return CompileError(pos, 'assignment target should be either a name or element(s) of an array')
        
class Storage:
    def __init__(self, fridx, value = None, isFixed = False):
        self.fridx = fridx
        self.value = value
        self.isFixed = isFixed
        
def bool2bit(b):
    return QBLBitObject(1 if b else 0) 

class QBLFuncError(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('error', 1)
        self.qm = qm
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, QBLObjectType.Str, singlearg = True)
        raise UserError(self.qm, None, arg.value)
        
class QBLFuncInput(QBLInternalFunc):
    def __init__(self, qm):
        super().__init__('input', 1)
        self.qm = qm
        
    def call(self, args):
        arg = args[0]
        assertArgType(self.name, args, 0, QBLObjectType.ObjType, singlearg = True)
        if arg.value == 'QBIT':
            return QBLQBitObject(qm.allocInputQBit())
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
                
        raise CompileError(None, "function '%s' expects qbit type or a full quantum word type, but the argument was %s" % (
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
                raise CompileError(None, 'a quantum state defined by a list with length of %d, but it should have a length of a power of 2' % nst)
            idxarr = range(nst)
        if nbits != None:
            if stbits != nbits:
                if sttype == QBLObjectType.List or stbits > nbits:
                    raise CompileError(None, "state bit number of % is not compatible with operator's bit number of %d" % (stbits, nbits))
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
        raise CompileError(None, 'a quantum state should be either given as a 0-1 value or a complex valued list/dictionary')
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
                raise CompileError(None, 'argument 1 should be either a qubit or an array of qubits, but instead got %s' % str(qbitobj))
            qbidx = qbitobj.value
            self.qm.allocQBit(qbidx)
            qbdata = self.qm.arrqb[qbidx]
            if len(qbdata.arrstep) > 0 or qbdata.isinput:
                raise CompileError(None, 'qubit index %d has been initialized already' % qbidx)
            qbarr.append(qbidx)

        stbits, state = p8(self.qm, arg1, type1)
        if nbits != stbits:
            raise CompileError(None, 'number of qubit indices are not consistent with states bits, %d != %d' % (nbits, stbits))
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
        type0 = assertArgType(self.name, args, 0, [QBLObjectType.List])
        type1 = assertArgType(self.name, args, 1, [QBLObjectType.Dict, QBLObjectType.List])
        
        nbits = len(arg0.value)
        nbase = 1<<nbits
        rbase = range(nbase)
        
        qbarr = []
        for i in range(nbits):
            qbit = arg0.value[i]
            if qbit == None or qbit.getType() != QBLObjectType.QBit:
                raise CompileError(None, 'argument 1 should be a list of qubits')
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
                raise CompileError(None, 'an operator defined by a list with length of %d, but it should have a length of a power of 2' % nrows)
            idxarr = range(nrows)

        if nbits != nrowbits:
            raise CompileError(None, 'argument 1 and 2 have inconsistent lengths (%d bits != %d bits)' % (nbits, nrowbits))
            
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
            raise CompileError(None, 'operator failed unitarity test')
                        
        self.qm.addStep(StepApplyOp(qbarr, opmatr))
        return None     
    
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
            raise CompileError(None, 'function %s accepts only non-negative argument, but %d was found' % (self.name, n))
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
        return bool2bit(arg0.value!=0 or arg1.value != 0)
    
class QBLFuncLogXor(QBLInternalFunc):
    def __init__(self):
        super().__init__('__logxor__', 2)
        
    def call(self, args):
        assertArgType(self.name, args, [0,1], [QBLObjectType.Int, QBLObjectType.Bit])
        return bool2bit((arg[0].value!=0) != (arg[1].value != 0))
    
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
            raise CompileError(None, 'value of %d as bit count is not allowed (less than zero)' % sbits)
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
            raise CompileError(None, 'function %s has mismatching types: %s and %s' % (self.name, str(arg0.objtype), str(arg1.objtype)))
        
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
            raise CompileError(None, 'Division by zero')
    
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
        
    def reindex(self, oldidx, newidx):
        if oldidx in self.arrqb:
            self.arrqb[self.arrqb.index(oldidx)] = newidx
        
class StepQBInit(QLStep):
    def __init__(self, arrqb, state):
        super().__init__('INIT', arrqb)
        self.nbits = len(arrqb)
        self.nbase = 1<<self.nbits
        if type(state) == int:
            if state == 0:
                self.state = [ComplexValue(real = RationalValue('INT', 1)), ComplexValue()]
            elif state == 1:
                self.state = [ComplexValue(), ComplexValue(real = RationalValue('INT', 1))]
        else:
            self.state = state
        
    def __str__(self):
        return 'qbinit(%s, {%s})' % (str(self.arrqb), ', '.join([str(int2word(k, self.nbits)) + ' : ' + str(self.state[k]) for k in range(self.nbase)]))

class StepQBCopy(QLStep):
    def __init__(self, srcidx, dstidx):
        super().__init__('COPY', [srcidx, dstidx])
        self.srcidx = srcidx
        self.dstidx = dstidx
        
    def reindex(self, oldidx, newidx):
        super().reindex(oldidx, newidx)
        if oldidx == self.srcidx: self.srcidx = newidx
        if oldidx == self.dstidx: self.dstidx = newidx
      
    def __str__(self):
        return 'qbcopy(%d, %d)' % (self.srcidx, self.dstidx)
    
class StepApplyTbl(QLStep):
    def __init__(self, arrqb, nin, nout, tbl):
        super().__init__('APPTBL', arrqb)
        self.nin = nin
        self.nout = nout
        self.tbl = tbl
        
    def __str__(self):
        return '''applytbl(%s, %d, %d,\n  [%s])''' % (str(self.arrqb), self.nin, self.nout, 
                      ',\n   '.join([str(int2word(i, self.nin)) + ' : ' + str(int2word(self.tbl[i], self.nout)) for i in range(len(self.tbl))]))
class StepApplyOp(QLStep):
    def __init__(self, arrqb, opmatr):
        super().__init__('APPOP', arrqb)
        self.nbits = len(arrqb)
        self.nbase = 1<<self.nbits
        self.opmatr = opmatr
        
    def __str__(self):
        return '''applyop(%s,\n  [%s])''' % (str(self.arrqb), 
                      ',\n   '.join([ ', '.join([str(self.opmatr[i][k]) for k in range(self.nbase)]) for i in range(self.nbase)])) 
class QuantumLogic:
    def __init__(self, preload = [os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qbl', 'base.qbl')]):
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
        self.addFunc(QBLFuncError(self))
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
        
        for src in preload:
            self.compileSource(srcfile = src)
    
    def setGlobal(self, name, value):
        self.globalfr[name] = Storage(
            0,
            value = value,
            isFixed = True)   
        
    def setValue(self, target, value, startpos, tgtidx = None):
        if tgtidx == None:
            if target.isFixed:
                raise CompileError(startpos, "fixed objects shouldn't be reassigned")
            target.value = value
        else:
            tgtarr = target.value
            if tgtidx < 0 or tgtidx >= len(tgtarr):
                raise CompileError(startpos, 'index %d out of range' % tgtidx)
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
            raise CompileError(errorpos, "name '%s' is not found" % name)
        else:
            return None 

    def addFunc(self, func):
        store = self.lookupName(func.name)
        if store != None:
            funclist = store.value
            if funclist == None or funclist.objtype != QBLObjectType.FuncList:
                raise CompileError(func.cmd.startpos, 'name %s was already defined as a non-function list object, function cannot be added' %  func.name)
        else:
            funclist = QBLFuncListObject(func.name)
            self.arrfr[0][func.name] = Storage(0, value = funclist, isFixed = True)
                 
        funcs = funclist.value
        if func.nargs in funcs and funcs[func.nargs].functype == 'INTERNAL':
            raise CompileError(func.cmd.startpos, 'function %s with %d arguments is internal, cannot be overriden' %  (func.name,  func.nargs))
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
    
    def comprQBits(self):
        self.arrqbcompr = []
        for qbdata in self.arrqb:
            if qbdata != None:
                qbdata.compridx = len(self.arrqbcompr)
                self.arrqbcompr.append(qbdata)
    
    def addStep(self, qmstep):
        stepidx = len(self.arrstep)
        for qbidx in qmstep.arrqb:
            if qbidx < len(self.arrqb):
                qbdata = self.arrqb[qbidx]
            else:
                qbdata = None
            if qbdata == None:
                qbdata = self.arrqb[self.allocQBit(qbidx)]
            self.arrqb[qbidx].arrstep.append(stepidx)
        self.arrstep.append(qmstep)

    def delStep(self, idx):
        step = self.arrstep[idx]
        for qbidx in step.arrqb:
            qbdata = self.arrqb[qbidx]
            qbdata.arrstep.pop(qbdata.arrstep.index(idx))
        self.arrstep[idx] = None

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
                return QBLWordObject(tgttype.signed, bitlist)
            
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
            raise TargetError(expr.startpos)
            
        if expr.typeid == 'EXPCONS':
            ret = expr.obj
            
        elif expr.typeid == 'EXPNAME':
            storage = self.lookupName(expr.name, errorpos = expr.startpos)
            if storage.value == None:
                raise CompileError(expr.startpos, "variable %s is uninitialized and shouldn't be referenced" %  expr.name)
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
                    raise CompileError(idexp.startpos, "Object %s shouldn't be called as a function" % str(ret))
                if idobj.objtype == QBLObjectType.FuncList:
                    try:
                        idobj = idobj.value[nargs]
                    except KeyError:
                        raise CompileError(expr.idexp.startpos, 'function %s is not defined for %d arguments, only for %s' % (
                            idobj.name,
                            nargs,
                            ', '.join([str(n) for n in idobj.value])
                        ))
                elif idobj.objtype == None:
                    if nargs != 1:
                        raise CompileError(expr.startpos, "casting to object type %s needs exactly one argument" % str(idobj))
                    docast = True
                               
            args = [self.compileExpr(expr.arrarg[i]) for i in range(nargs)]
                
            if qual:
                baseobj = args[0]
                if baseobj.getType() != QBLObjectType.ObjType or baseobj.value != 'WORD':
                    raise CompileError(expr.startpos, "%s shouldn't be qualified with {}" % str(args[0]))
                
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
                            raise CompileError(expr.arrarg[1].startpos, 'qualifer should be a fully initialized array')
                        elif e not in [QBLObjectType.Bit, QBLObjectType.QBit]:
                            bitsok = False
                            break
                        bits.append(e)     
                    if bitsok:
                        ret = QBLStructuredWordType(baseobj, bits)
                if ret == None:    
                    raise CompileError(expr.arrarg[1].startpos, 'a positive integer or an array of bit types is expected as qualifier')
                    
            elif elmt:
                arridx = None
                isidxarr = False
                baseobj = args[0]
                if baseobj != QBLObjectType.QBit and not baseobj.getType().hasElements:
                    raise CompileError(expr.arrarg[1].startpos, "object of type %s doesn't provide elements" % str(baseobj.getType()))
                if nargs == 2:
                    idxarg = args[1]
                    argtype = idxarg.getType()
                    if argtype == QBLObjectType.Int:
                        arridx = idxarg.value
                    elif argtype == QBLObjectType.List:
                        isidxarr = True
                        idxsok = (len(idxarg.value)>0)
                        idxs = []
                        for e in idxarg.value:
                            if e == None:
                                raise CompileError(expr.arrarg[1].startpos, "index array shouldn't contain uninitialized element")
                            elif e.objtype != QBLObjectType.Int:
                                raise CompileError(expr.arrarg[1].startpos, 'indices should be integers or array of integers')
                            idxs.append(e.value)     
                        
                        arridx = idxs                        
                else:
                    raise CompileError(expr.startpos, 'multiindices are not allowed') #shouldn't arrive here though
                    
                if arridx == None:
                    raise CompileError(expr.startpos, 'index value cannot be empty') 
                else:
                    if isidxarr:
                        retval = []
                        idxs = arridx
                    else:
                        idxs = [arridx]
                    if isTarget:
                        if baseobj.getType() != QBLObjectType.List:
                            raise TargetError(expr.startpos)
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
                            raise CompileError(expr.arrarg[1].startpos, "there isn't any element for index %d" % i)
                        if value == None:
                            raise CompileError(expr.startpos, "shouldn't refer to uninitialized element")
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
                    raise CompileError(expr.startpos, "object %s with type %s cannot be converted to type %s" % (str(args[0]), str(args[0].getType()), str(idobj)))
            else:
                if nargs != idobj.nargs:
                    raise CompileError(expr.startpos, "function '%s' requires %d arguments but found %d" % (idobj.name, idobj.nargs, nargs))
                if idobj.functype == 'INTERNAL':
                    try:
                        ret = idobj.call(args)
                    except CompileError as ce:
                        raise CompileError(expr.startpos, ce.msg)
                    except UserError as ce:
                        raise UserError(self, expr.startpos, ce.msg)
                        
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
                    cval = 0
                    for i in range(nargs):
                        arg = args[i]
                        if arg.getType() == QBLObjectType.QBit:
                            key = arg.value
                            if key in qbitdict:
                                qbitdict[key].append(i)
                            else:
                                qbitdict[key] = [i]
                        else:
                            bitval = self.cast(QBLObjectType.Bit, arg)
                            if bitval == None or bitval.value not in [0,1]:
                                raise CompileError(expr.startpos, "table function '%s' requires a qbit or 0 or 1, but got %s for argument %d" % (idobj.name, str(args[i]), i))
                            cbits.append(bitval.value)
                            cval += bitval.value<<i
                            cbitidxs.append(i)
                    
                    nin = len(qbitdict)
                    rin = range(nin)
                    nret = idobj.cmd.body[1]
                    nout = nret
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
                        for i in ritem:
                            key = cval
                            k = 0
                            for qb in qbitdict:
                                bitval = (i >> k) & 1
                                invecs[k] |= bitval << i
                                for l in qbitdict[qb]:
                                    key = key | (bitval << l)
                                k = k+1
                            outval = truthtbl[key]
                            outvals[i] = outval
                            for k in rout:
                                outvecs[k] |= ((outval>>k)&1)<<i
                        
                        #Check const outputs
                        cons1 = (1<<nitem)-1
                        mask = 0
                        idx = 0
                        ret = [None for i in rout]
                        retmap = [i for i in rout]
                        for i in rout:
                            outvec = outvecs[idx]
                            newmask = mask<<1 | 1
                            if outvec in [0, cons1]:
                                for k in ritem:
                                    outval = outvals[k]
                                    outvals[k] = mask & outval | ((~newmask & outval)>>1)
                                outvecs.pop(idx)
                                retmap.pop(idx)
                                ret[i] = bool2bit(outvec != 0)
                            else:
                                idx += 1
                                mask = newmask
                        nout = len(outvecs)
                        rout = range(nout)
                        
                        if nout>0:
                            #check already mapped input qubits
                            dirargs = [[k for k in rout if invecs[i] == outvecs[k]] for i in rin]

                            #adding input qubits to achieve unitarity
                            nadded = 0
                            newidx = 0
                            while len(set(outvals)) < len(outvals):
                                while len(dirargs[newidx]) > 0:
                                    newidx += 1
                                for i in ritem:
                                    outvals[i] |= ((i>>newidx)&1)<<nout
                                dirargs[newidx] = [nout]
                                nadded += 1
                                nout += 1
                            rout = range(nout)

                            #reordering for match inputs with outputs
                            inmapped = [False for i in rout]
                            out2in = [None for i in rout]
                            for i in rin:
                                if len(dirargs[i])>0:
                                    diridx = dirargs[i][0]
                                    inmapped[i] = True
                                    out2in[diridx] = i    

                            qbitidxs = [qb for qb in qbitdict]
                            trqbs = [None for i in rout]
                            nextin = 0
                            for i in rout:
                                if out2in[i] == None:
                                    while inmapped[nextin]:
                                        nextin += 1
                                    out2in[i] = nextin
                                    inp = nextin
                                    newqb = self.allocQBit()
                                    nextin += 1
                                    if inp<nin:
                                        self.addStep(StepQBCopy(qbitidxs[inp], newqb))
                                else:
                                    inp = out2in[i]
                                    newqb = qbitidxs[inp]
                                trqbs[inp] = newqb
                                if i < len(retmap):
                                    ret[retmap[i]] = QBLQBitObject(newqb)

                            for i in ritem:
                                newval = 0
                                oldval = outvals[i]
                                for k in rout:
                                    newval |= ((oldval>>k)&1)<<out2in[k]
                                outvals[i] = newval

                            self.addStep(StepApplyTbl(trqbs, nin, nout, outvals))
                    ret = QBLListObject(ret)
                else: 
                    raise ImplError(expr.startpos)
                
            if not nullable and ret == None:
                expr.print()
                raise CompileError(expr.startpos, "function %s expected to return a value, but it didn't" % idobj.name)
                
        elif expr.typeid == 'EXPDICT':
            dictobj = []
            ret = QBLDictObject(expr.nbits, {i : self.compileExpr(expr.dictexp[i]) for i in expr.dictexp })
                
        else:
            raise ImplError(expr.startpos)
            
        
        return ret
            
    def compileCommand(self, cmd):
        if cmd.typeid == 'CMDCALC':
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
                                raise CompileError(evalexp.startpos, 'when assigning to multiple array elements, the value should be also an array')
                            valarr = value.value
                            lenidx = len(tgtidx)
                            if lenidx != len(valarr):
                                raise CompileError(cmd.startpos, 'target array indexes are not matching with source array length')
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
                    raise CompileError(cmd.condition.startpos, 'condition should either int or bit type')
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
                raise CompileError(cmd.listexp, 'can iterate a list only, instead found object with type '+str(listobj.getType()))
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
            raise ImplError(cmd.startpos)
            
        return None
        
    def compileSource(self, source=None, srcfile=None):
        lexer=Lexer(source=source, srcfile=srcfile)
        while True:
            nextstm = parseCommand(lexer)
            if nextstm != None:
                self.compileCommand(nextstm)
            else:
                break

    def compileParsed(self, parsed):
        for cmd in parsed:
            self.compileCommand(cmd)
            
    def __str__(self):
        ret = 'QC:\n'
        for s in self.arrstep:
            ret += str(s) + '\n'

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

def reduce(qm):
    stepidx = len(qm.arrstep) - 1
    while stepidx >= 0:
        currstep = qm.arrstep[stepidx]
        if currstep != None:
            if currstep.typeid == 'COPY':
                srcdata = qm.arrqb[currstep.srcidx]
                dstdata = qm.arrqb[currstep.dstidx]
                if not srcdata.isoutput and stepidx == srcdata.arrstep[len(srcdata.arrstep) - 1]:
                    srcdata.isoutput = dstdata.isoutput
                    dstdata.isoutput = False
                    qm.delStep(stepidx)
                    for nextstidx in dstdata.arrstep:
                        qm.arrstep[nextstidx].reindex(currstep.dstidx, currstep.srcidx)
                    for outidx in range(len(qm.arrout)):
                        qm.arrout[outidx] = qm.setOutput(qm.arrout[outidx], oldidx = currstep.dstidx, newidx = currstep.srcidx)
                    srcdata.arrstep.extend(dstdata.arrstep)
                    dstdata.arrstep = []
                
            else:
                todel = False
                if currstep.typeid == 'APPTBL':
                    todel = True
                    for i in range(1<<currstep.nin):
                        if currstep.tbl[i] != i:
                            todel = False
                            break
                if not todel:
                    todel = True
                    for qbidx in currstep.arrqb:
                        qbdata = qm.arrqb[qbidx]
                        if qbdata.isoutput or stepidx != qbdata.arrstep[len(qbdata.arrstep) - 1]:
                            todel = False
                            break
                if todel:
                    qm.delStep(stepidx)
        stepidx -= 1
    for i in range(len(qm.arrqb)):
        qbdata = qm.arrqb[i]
        if qbdata != None and len(qbdata.arrstep) == 0 and not qbdata.isoutput:
            qm.arrqb[i] = None
            qm.nqb -= 1
    qm.comprQBits()
  

def getOutBits(qm, outidx, iscompr = False):
    qblobj = qm.arrout[outidx]
    objclass = qblobj.getType().value
    if objclass in ['WORD', 'LIST']:
        objarr = qblobj.value
    else:
        objarr = [qblobj]
    ret = []
    for el in objarr:
        if el.getType().value == 'QBIT':
            ret.append(qm.arrqb[el.value].compridx if iscompr else el.value)
    return ret