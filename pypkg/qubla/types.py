# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022 Gergely Gálfi
#

from .lazyalg import *

class QBLObject:
    def __init__(self, objtype, value):
        self.objtype = objtype
        self.value = value
    
    def __eq__(self, obj):
        return type(self) == type(obj) and self.value == obj.value
    
    def getType(self):
        if self.objtype == None:
            return QBLObjectType.ObjType
        else:
            return self.objtype
    
    def __repr__(self):
        return '%s(%s)' % (str(self.getType()), self.__str__())
    
    def __str__(self):
        return str(self.value)
    
class QBLObjectType(QBLObject):

    def __init__(self, typeclass, hasElements = False):
        super().__init__(None, typeclass)
        self.hasElements = hasElements
        
    def __str__(self):
        return str(self.value.lower())

class QBLQBitType(QBLObjectType):
    def __init__(self):
        super().__init__('QBIT')
        
    def __getitem__(self, key):
        if key<0:
            raise IndexError
        return QBLQBitObject(key)
    
QBLObjectType.ObjType = QBLObjectType('OBJTYPE')
QBLObjectType.List = QBLObjectType('LIST', True)
QBLObjectType.Dict = QBLObjectType('DICT', True)
QBLObjectType.Function = QBLObjectType('FUNCTION')
QBLObjectType.FuncList = QBLObjectType('FUNCLIST', True)
QBLObjectType.Int = QBLObjectType('INT', True)
QBLObjectType.Cplx = QBLObjectType('CPLX')
QBLObjectType.Str = QBLObjectType('STR', True) 
QBLObjectType.Bit = QBLObjectType('BIT')
QBLObjectType.QBit = QBLQBitType()

class QBLBitObject(QBLObject):
    def __init__(self, value):
        super().__init__(QBLObjectType.Bit, value)
        
class QBLQBitObject(QBLObject):
    def __init__(self, value):
        super().__init__(QBLObjectType.QBit, value)
    
    def __str__(self):
        return str('qbit[%d]' % self.value)

class QBLIntObject(QBLObject):
    def __init__(self, value):
        super().__init__(QBLObjectType.Int, value)
    
    def __getitem__(self, key):
        if key<0:
            raise IndexError
        return QBLBitObject((self.value>>key) & 1)
    
    def getElementType(self):
        return QBLObjectType.Bit   
    
class QBLCplxObject(QBLObject):
    def __init__(self, value):
        super().__init__(QBLObjectType.Cplx, value)

class QBLStrObject(QBLObject):
    def __init__(self, value):
        super().__init__(QBLObjectType.Str, value)
   
    def __getitem__(self, key):
        if key<0 or key>=len(self.value):
            raise IndexError
        return QBLStrObject(self.value[k])
    
    def getElementType(self):
        return QBLObjectType.Str

    def __repr__(self):
        return 'str("%s")' % self.value  
    
class QBLWordType(QBLObjectType):
    def __init__(self, signed, allquantum):
        super().__init__('WORD', True)
        self.signed = signed
        self.allquantum = allquantum
                        
    def __str__(self):
        return '%s%sword' % (('q' if self.allquantum else ''), ('' if self.signed else 'u'))
    
    def __eq__(self, obj):
        return super().__eq__(obj) and self.allquantum == obj.allquantum and self.signed == obj.signed 

QBLWordType.Word = QBLWordType(True, False)
QBLWordType.QWord = QBLWordType(True, True)
QBLWordType.UWord = QBLWordType(False, False)
QBLWordType.QUWord = QBLWordType(False, True)
    
class QBLStructuredWordType(QBLObjectType):
    def __init__(self, basetype, qualifier):
        super().__init__('STRWORD')
        
        if basetype.signed:
            self.basetype = QBLWordType.Word
        else:
            self.basetype = QBLWordType.UWord
        
        self.signed = basetype.signed
        if (type(qualifier) == int):
            self.nbits = qualifier
            self.bitstruct = [QBLObjectType.QBit for i in range(qualifier)] if basetype.allquantum else None
        else:
            allclassic = True
            for bt in qualifier:
                if bt == QBLObjectType.QBit:
                    allclassic = False
                    break
            self.nbits = len(qualifier)
            self.bitstruct = None if allclassic else qualifier
            
    def __eq__(self, obj):
        ret= (super().__eq__(obj))
        ret = ret and self.signed == obj.signed and self.bitstruct == obj.bitstruct
        return ret
        
    def __str__(self):
        return '%sword{%s}' %  (
            '' if self.signed else 'u',
            ('[%s]' % (', '.join([str(b) for b in self.bitstruct]))) if self.bitstruct != None else str(self.nbits)
        )
    
class QBLWordObject(QBLObject):
    def __init__(self, signed, value):
        super().__init__(QBLWordType.Word if signed else QBLWordType.UWord, value)
        
    def __getitem__(self, key):
        return self.value[key]
    
    def toint(self):
        n = len(self.value)
        ismin = self.objtype.signed and self.value[n - 1].value == 1 
        if ismin:
            n -= 1
            ret = -(1<<n)
        else:
            ret = 0
        for i in range(n):
            val = self.value[i];
            if val.objtype.value != 'BIT': return None
            ret += self.value[i].value<<i
        return ret
    
    def __str__(self):
        reti = self.toint()
        if reti == None:
            return '[' + ', '.join([str(e) for e in self.value ]) + ']'
        else:
            return str(reti)

#TODO: handle cycles
class QBLListObject(QBLObject):
    def __init__(self, value):
        super().__init__(QBLObjectType.List, value)
                           
    def __getitem__(self, key):
        return self.value[key]
    
    def __str__(self):
        return '[' + ', '.join([(str(e) if type(e) != list else '[...]') if e != None else 'Uninitialized' for e in self.value ]) + ']'

class QBLDictObject(QBLObject):
    def __init__(self, nbits, value):
        super().__init__(QBLObjectType.Dict, value)
        self.nbits = nbits
                           
    def __getitem__(self, key):
        return self.value[key]
    
    def __str__(self):
        skey = [str(key) for key in self.value]
        sval = [self.value[key] for key in self.value]
        sval = [(str(e) if type(e) != list else '[...]') if e != None else 'Uninitialized' for e in sval]
        return '{' + ', '.join(['%s : %s' % (skey[i], sval[i]) for i in range(len(skey))]) + '}'    
    
class QBLFuncListObject(QBLObject):
    def __init__(self, name):
        super().__init__(QBLObjectType.FuncList, {})
        self.name = name
        
    def __getitem__(self, key):
        return self.value[key]

#TODO: handle identity relation
class QBLFuncObject(QBLObject):
    def __init__(self, name, functype = None, cmd = None, nargs = None):
        super().__init__(QBLObjectType.Function, None)
        self.functype = functype if functype != None else cmd.deftype
        self.nargs = nargs if nargs != None else cmd.nargs
        self.cmd = cmd
        self.name = name            
            
class QBLInternalFunc(QBLFuncObject):
    def __init__(self, name, nargs):
        super().__init__(name, functype = 'INTERNAL', nargs = nargs)   
    def call(self, args):
        pass    
    