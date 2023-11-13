# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022-2023 Gergely Gálfi
#

class QBLError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg

class QBLInterpreterError(QBLError):
    def __init__(self, errname, pos, desc, callstack = None):
        super().__init__('%s: %s\nat %s\n%s%s' % (
            errname,
            desc,
            str(pos),
            pos.showSrc() if pos != None and pos.lexer != None else '',
            'Callstack:\n' + (''.join([str(expr)+'\n' for expr in callstack])) if callstack != None else ''
        ))
        self.errname = errname
        self.pos = pos
        self.desc = desc
        
class QBLSyntaxError(QBLInterpreterError):
    def __init__(self, pos, desc):
        super().__init__('Syntax error', pos, desc)
        
class QBLRuntimeError(QBLInterpreterError):
    def __init__(self, pos, desc, callstack = None):
        super().__init__('Runtime error', pos, desc, callstack = callstack)