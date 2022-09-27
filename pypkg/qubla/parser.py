# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022 Gergely Gálfi
#

from .lazyalg import *
from .lexer import *
from .types import *

class TokenError(QBLSyntaxError):
    def __init__(self, tok, msg):
        super().__init__(tok.startpos, msg)

class UnexpEndError(TokenError):
    def __init__(self, lexer):
        i = -1
        while lexer.lookAheadToken(i) != None:
            i += 1
        print(lexer.lookAheadToken(i-1))
        super().__init__(lexer.lookAheadToken(i-1), 'unexpected end of file')    
    
def raiseUnexpTokenError(lexer):
    tok=lexer.lookAheadToken(0)
    if tok != None:
        raise TokenError(tok, 'unexpected token')
    else:
        raise UnexpEndError(lexer)
        
class TreeNode:
    def __init__(self, typeid, startpos, endpos):
        self.typeid = typeid
        self.startpos = startpos
        self.endpos = endpos
        
    def __str__(self):
        return 'Node type:%s from %s to %s' % (self.typeid, str(self.startpos), str(self.endpos))
    
    def __repr__(self):
        return str(self)
    
    def print(self, indent=''):
        print(indent+str(self))
        

class ExprConst(TreeNode):
    def __init__(self, startpos, endpos, obj):
        super().__init__('EXPCONS', startpos, endpos)
        self.obj=obj
                        
    def __str__(self):
        return super().__str__()+ ' value: ' + repr(self.obj)
                                  
class ExprName(TreeNode):
    def __init__(self, nametok):
        super().__init__('EXPNAME', nametok.startpos, nametok.endpos)
        self.name=nametok.value
    
    def __str__(self):
        return super().__str__()+(' name:%s' % (self.name,))
        
class ExprFunc(TreeNode):
    def __init__(self, startpos,  endpos, funcid, arrarg):
        super().__init__('EXPFUNC', startpos, endpos)
        if type(funcid) == str:
            self.idexp = None
            self.name = funcid
        else:
            self.idexp = funcid
            self.name = None
        self.arrarg=arrarg
        
    def __str__(self):
        return super().__str__() + (' name:' + self.name if self.name != None else '')
    
    def print(self, indent=''):
        super().print(indent)
        if self.idexp != None:
            print(indent+'|ID expr:')
            self.idexp.print(indent+'|')
        for i in range(len(self.arrarg)):
            print(indent+'|Arg '+str(i))
            self.arrarg[i].print(indent+'|')

class ExprDict(TreeNode):
    def __init__(self, startpos,  endpos, dictexp, nbits):
        super().__init__('EXPDICT', startpos, endpos)
        self.dictexp = dictexp
        self.nbits = nbits
        
    def __str__(self):
        return super().__str__()
    
    def print(self, indent=''):
        super().print(indent)
        for i in self.dictexpr:
            print(indent+'|Key:%s'+str(i))
            self.dictexpr[i].print(indent+'|')
    
            
def int2word(x, nbits):            
    return [(x>>i) &1 for i in range(nbits)]

class CmdFuncDef(TreeNode):
    def __init__(self, startpos, endpos, deftype, nametok, args, body):        
        super().__init__('CMDFDEF', startpos, endpos)
        self.deftype = deftype
        self.nametok = nametok
        self.name = nametok.value
        self.body = body
        if self.deftype == 'TABLE':
            self.args = None
            self.nargs = body[0]
        elif self.deftype == 'SCRIPT':
            self.args = args
            self.nargs = len(args)
    
    def __str__(self):
        return super().__str__()+(' name:%s  deftype:%s' % (self.name, self.deftype))
    
    def print(self, indent=''):
        super().print(indent)
        if self.deftype == 'TABLE':
            print(indent+'|Table items:')
            tbl = self.body[2]
            nin = self.body[0]
            for i in range(len(tbl)):
                print(indent+'| %s : %s' % (str(int2word(i, nin)), str(int2word(tbl[i], nin))))
        elif self.deftype == 'SCRIPT':
            print(indent+'|Script:')
            for cmd in self.body:
                cmd.print(indent+'|')
        
class CmdCalc(TreeNode):
    def __init__(self, startpos, endpos, tgtarr, evalarr, local):
        super().__init__('CMDCALC', startpos, endpos)
        self.tgtarr = tgtarr
        self.evalarr = evalarr
        self.local = local
        
    def __str__(self):
        return super().__str__()+' local:' + str(self.local)
        
    def print(self, indent=''):
        super().print(indent)
        for i in range(len(self.tgtarr)):
            tgtexp = self.tgtarr[i]
            evalexp = self.evalarr[i]
            if tgtexp != None:
                print(indent+'|%d. target expression:' % i)
                tgtexp.print(indent+'|')
            if evalexp != None:
                print(indent+'|%d. expression to evalute:' % i)
                evalexp.print(indent+'|') 

class CmdIf(TreeNode):
    def __init__(self, startpos, endpos, condition, iftrue, iffalse):
        super().__init__('CMDIF', startpos, endpos)
        self.condition = condition
        self.iftrue = iftrue
        self.iffalse = iffalse
    
    def print(self, indent=''):
        super().print(indent)
        print(indent+'|Condition:')
        self.condition.print(indent+'|')
        if (self.iftrue != None):
            print(indent+'|If true:')
            self.iftrue.print(indent+'|')
        if (self.iffalse != None):
            print(indent+'|If false:')
            self.iffalse.print(indent+'|')

class CmdWhile(TreeNode):
    def __init__(self, startpos, endpos, condition, command):
        super().__init__('CMDWHILE', startpos, endpos)
        self.condition = condition
        self.command = command
    
    def print(self, indent=''):
        super().print(indent)
        print(indent+'|Condition:')
        self.condition.print(indent+'|')
        if (self.command != None):
            print(indent+'|If true:')
            self.command.print(indent+'|')

class CmdFor(TreeNode):
    def __init__(self, startpos, endpos, nametok, listexp, command):
        super().__init__('CMDFOR', startpos, endpos)
        self.nametok = nametok
        self.varname = nametok.value
        self.listexp = listexp
        self.command = command
    
    def __str__(self):
        return super().__str__()+' varname:' + str(self.varname)
    
    def print(self, indent=''):
        super().print(indent)
        print(indent+'|List expr:')
        self.listexp.print(indent+'|')
        if (self.command != None):
            print(indent+'|Command:')
            self.command.print(indent+'|')
            
class CmdReturn(TreeNode):
    def __init__(self, startpos, endpos, retexp):
        super().__init__('CMDRET', startpos, endpos)
        self.retexp = retexp
    
    def print(self, indent=''):
        super().print(indent)
        if (self.retexp != None):
            print(indent+'|Returned expression:')
            self.retexp.print(indent+'|')

class CmdBlock(TreeNode):
    def __init__(self, startpos, endpos, arrcmd):
        super().__init__('CMDBLCK', startpos, endpos)
        self.arrcmd=arrcmd
    
    def print(self, indent=''):
        super().print(indent)
        for i in range(len(self.arrcmd)):
            print(indent+'|Cmd '+str(i))
            self.arrcmd[i].print(indent+'|')

def nextTokenAssert(lexer, value = None, toktype = 'OTHER'):
    tok=lexer.lookAheadToken(0)
    if tok != None:
        if tok.type == toktype and (value == None or tok.value == value):
            return lexer.nextToken()
        else:
            raise TokenError(tok, "expected %s but instead got %s" % (
                "'" + value + "'" if value != None else 'token type '+ toktype,
                "'" + tok.value + "'" if tok.value != None else 'token type '+ tok.type)
            )
    else:
        raise UnexpEndError(lexer)

class ExprError(Exception):
    def __init__(self, exp, msg):
        super().__init__('Expression error at ' + str(exp.startpos) + ': ' + msg)
        
def testToken(tok, value, toktype='OTHER'):
    return tok!=None and tok.type == toktype and tok.value == value

def testUnaryOp(tok):
    prec=None
    fname=None
    if (tok!=None):
        if tok.type == 'OTHER' and tok.value in ['!', '~', '+', '-']:
            prec = 7
            fname = tok.value
    return (prec, fname)
        
def parseExpr(lexer, prec=0):
    tok = lexer.lookAheadToken(0)
    opprec, fname=testUnaryOp(tok)
    if opprec != None:
        prefix = lexer.nextToken()
        inexp = parseExpr(lexer, opprec)
        if fname in ['-', '+'] and inexp.typeid == 'EXPCONS' and inexp.obj.objtype.value == 'INT':
            retexp = ExprConst(
                prefix.startpos,
                inexp.endpos,
                QBLIntObject(inexp.obj.value if fname == '+' else -inexp.obj.value))
        else:
            retexp = ExprFunc(prefix.startpos, inexp.endpos, fname, [inexp])
    else:
        retexp = parseSimpleExpr(lexer)
                 
    while True:
        tok = lexer.lookAheadToken(0)
        opprec=None
        if tok!=None and tok.type == 'OTHER' :
            if tok.value in [ '*', '/', '%', '//']:
                opprec = 7
            elif tok.value in [ '+', '-' ]:
                opprec = 6
            elif tok.value in [ '>>', '<<' ]:
                opprec = 5
            elif tok.value in [ '&', '|' ]:
                opprec = 4
            elif tok.value in [ '<', '>', '<=', '>=' ]:
                opprec = 3
            elif tok.value in [ '==', '!=', '===', '!==']:
                opprec = 2
            elif tok.value in [ '||', '&&' ]:
                opprec = 1      
        if opprec == None or opprec<=prec:
            return retexp

        optok=lexer.nextToken()   
        rhsexp = parseExpr(lexer, opprec)       
        retexp = ExprFunc(retexp.startpos, rhsexp.endpos, tok.value, [retexp, rhsexp])
    
def processDictItems(lexer, itemset, ninbits, forcebits):
    nbits = None
    maxnbits = 0
    invval = False
    inctype = False
    incbit = False
    isint = False
    isstr = False
    retdict = {}
    prockeys = (ninbits == None)
    if prockeys:
        rng = itemset
    else:
        rng = range(1<<ninbits)
        
    errmsg = ('in bits' if prockeys else 'out bits') if forcebits else 'key'
    for item in rng:
        if prockeys:
            exp = item[0]
        else:
            if item in itemset:
                exp = itemset[item]
            else:
                value = 0
                exp = None
        
        if exp != None:
            if exp.typeid == 'EXPCONS':
                objclass = exp.obj.getType().value
                if objclass in ['INT',  'STR']:
                    value = exp.obj.value
                    if objclass == 'STR':
                        if isint or forcebits:
                            inctype = True
                            break
                        isstr = True
                    else:
                        if isstr:
                            inctype = True
                            break
                        isint = True
                        while value >> maxnbits not in [0, -1]:
                            maxnbits += 1

                        if nbits != None and maxnbits > nbits:
                            incbit = True
                            break                
                else:
                    invval = True
                    break
            elif exp.typeid == 'EXPFUNC' and exp.name == '#ARRAY':
                newnbits = len(exp.arrarg)
                if (nbits != None and newnbits != nbits) or newnbits < maxnbits:
                    incbit = True
                    break
                nbits = newnbits
                value = 0
                for i in range(nbits):
                    bitexp = exp.arrarg[i]
                    if bitexp.typeid != 'EXPCONS' or bitexp.obj.getType().value != 'INT' or bitexp.obj.value not in [0,1]:
                        invval = True
                        break
                    value += bitexp.obj.value<<i
                if invval:
                    break
            else:
                invval = True
                break
        if prockeys:
            if value in retdict:
                raise ExprError(exp, '%s set is not uniqe' % errmsg)
            retdict[value] = item[1]
        else:
            retdict[item] = value
            
    if invval:
        raise ExprError(exp, '%s should be%s an integer or an array of zeros and ones, but instead found %s' %
            errmsg, '' if forcebits else 'a string, ', str(exp))
    if inctype:
        raise ExprError(exp, 'incompatible %s type' % errmsg)
    if incbit:
        raise ExprError(exp, 'incompatible %s bit size' % errmsg)
                        
    return (isint, maxnbits if nbits == None else nbits, retdict)

            
def parseCommaList(lexer, closepar, isdict = False):
    clarr = []
    firstitem = True
    while True:
        tok = lexer.lookAheadToken(0)
        if testToken(tok, closepar):
            return clarr
        elif not firstitem:
            nextTokenAssert(lexer, ',')
        item = parseExpr(lexer)
        if isdict:
            nextTokenAssert(lexer, ':')
            item = [item, parseExpr(lexer)]
        clarr.append(item)
        firstitem = False                        

def parseDictionary(lexer, forcebits):
    nextTokenAssert(lexer, '{')
    lst = parseCommaList(lexer, '}', True)
    return processDictItems(lexer, lst, None, forcebits)
                        
def parseSimpleExpr(lexer):
    tok = lexer.lookAheadToken(0)
    
    if tok != None:
        startpos = tok.startpos
    else:
        UnexpEndError(lexer)
    
    stemexp = None
    if tok.type == 'NAME':
        stemexp = ExprName(lexer.nextToken())
            
    elif tok.type == 'NUM':
        inttok = lexer.nextToken()
        numbase = 10
        invfmt = False
        if len(inttok.value)>2:
            sbase = inttok.value[0:2]
            if sbase in ['0x', '0X']:
                numbase = 16
            elif sbase in ['0o', '0O']:
                numbase = 8
            elif sbase in ['0b', '0B']:
                numbase = 2
        if numbase == 10:
            pieces = inttok.value.split('.')
            npieces = len(pieces)
            if npieces <= 2:
                lastpiece = pieces[npieces - 1]
                lenlast = len(lastpiece)
                if lenlast > 1 and lastpiece[lenlast - 1] in ['i', 'I']:
                    isimg = True
                    pieces[npieces - 1] = lastpiece[0:(lenlast - 1)]
                else:
                    isimg = False
                try:
                    ipieces = [int(p) for p in pieces ]
                except ValueError:
                    invfmt = True
                
                if not invfmt:
                    numer = ipieces[0]
                    if npieces == 2:
                        ip2 = ipieces[1]
                        denom = 1
                        while ip2//denom > 0:
                            denom *= 10
                        numer = numer * denom + ip2
                        frac = RationalValue('DEC', [numer, denom])
                        if isimg:
                            real = RationalValue.Zero
                            imag = frac
                        else:
                            real = frac
                            imag = RationalValue.Zero
                        numobj = QBLCplxObject(ComplexValue(real = real, imag = imag))
                    elif isimg:
                        numobj = QBLCplxObject(ComplexValue(imag = RationalValue('INT', numer)))
                    else:
                        numobj = QBLIntObject(ipieces[0])
            else:
                invfmt = True
            
        else:
            try:
                numobj =  QBLIntObject(int(inttok.value, numbase))
            except ValueError:
                invfmt = True
            
        if invfmt:
            raise QBLSyntaxError(inttok.startpos, "invalid number format")
        stemexp = ExprConst(inttok.startpos, inttok.endpos, numobj)

    elif tok.type == 'STR':
        inttok = lexer.nextToken()
        stemexp = ExprConst(inttok.startpos, inttok.endpos, QBLStrObject(inttok.value))
        
    elif testToken(tok, '('):
        lexer.nextToken()
        stemexp = parseExpr(lexer)
        closepar = nextTokenAssert(lexer, ')')
        stemexp.startpos = startpos
        stemexp.endpos = closepar.endpos
        
    elif testToken(tok, '['):    
        lexer.nextToken()
        comps = parseCommaList(lexer, ']')
        stemexp = ExprFunc(startpos, lexer.nextToken().endpos, '#ARRAY', comps)
        
    elif testToken(tok, '{'):    
        tmp, nbits, comps = parseDictionary(lexer, False)
        stemexp = ExprDict(startpos, lexer.nextToken().endpos, comps, nbits)
                        
    else:
        raiseUnexpTokenError(lexer)

    tok = lexer.lookAheadToken(0)
    while tok != None and tok.value in ['(', '[', '{']:
        openpar = tok.value
        lexer.nextToken()
        tok = lexer.lookAheadToken(0)
        if openpar == '(':
            argarr = parseCommaList(lexer, ')')
            stemexp = ExprFunc(startpos, lexer.nextToken().endpos, stemexp, argarr)
        elif openpar == '[':
            idxexp = parseExpr(lexer)
            ket = nextTokenAssert(lexer, ']')
            stemexp = ExprFunc(startpos, ket.endpos, '#ELEMENT',  [stemexp] if idxexp == None else [stemexp, idxexp])
        elif openpar == '{':
            argexp = parseExpr(lexer)
            ket = nextTokenAssert(lexer, '}')
            stemexp = ExprFunc(startpos, ket.endpos, '#QUALIFY', [stemexp, argexp])
            
        tok = lexer.lookAheadToken(0)
    return stemexp
  
def parseCommand(lexer, returnOnSemicolon = False, depth = 0, inFunc = False):
    while True:
        tok=lexer.lookAheadToken(0)
        if tok == None: return None
        localVDef = False
        startpos = tok.startpos
        if tok.type=='NAME':
            if tok.value == 'function':
                tok2 = lexer.lookAheadToken(1)
                if tok2 != None and tok2.type == 'NAME':
                    if depth > 0:
                        raise TokenError(tok, 'function should be defined outside of any program block')
                    lexer.nextToken()
                    nametok = nextTokenAssert(lexer, toktype='NAME')
                    tok=lexer.lookAheadToken(0)
                    if tok == None:
                        UnexpEndError(lexer)
                    elif tok.type == 'NAME' and tok.value == 'table':
                        lexer.nextToken()
                        isint, ninbits, parsedict = parseDictionary(lexer, True)
                        isint, noutbits, tbldict = processDictItems(lexer, parsedict, ninbits, True)
                        return CmdFuncDef(startpos, lexer.nextToken().endpos, "TABLE", nametok, None, (ninbits, noutbits, tbldict))
                        
                    else:
                        nextTokenAssert(lexer, '(')
                        arrargs = parseCommaList(lexer, ')')
                        nextTokenAssert(lexer, ')')
                        nextTokenAssert(lexer, '{')
                        arrstm = []
                        while True:
                            tok=lexer.lookAheadToken(0)
                            if tok == None or testToken(tok, '}'): break
                            stm=parseCommand(lexer, depth = depth+1, inFunc = True)
                            if stm == None: break
                            arrstm.append(stm)
                        closepar = nextTokenAssert(lexer, '}')
                        return CmdFuncDef(startpos, closepar.endpos,'SCRIPT', nametok, arrargs, arrstm)
            elif tok.value in ['if', 'while']:
                lexer.nextToken()
                nextTokenAssert(lexer, '(')
                condition = parseExpr(lexer)
                nextTokenAssert(lexer, ')')
                command = parseCommand(lexer, depth = depth+1, inFunc = inFunc)
                if tok.value == 'if':
                    if testToken(lexer.lookAheadToken(0), 'else', 'NAME'):
                        lexer.nextToken()
                        iffalse = parseCommand(lexer, depth = depth+1, inFunc = inFunc)
                        endpos = iffalse.endpos if iffalse != None else tok
                    else:
                        iffalse = None
                        endpos = command.endpos if command != None else condition.endpos
                    return CmdIf(startpos, endpos, condition, command, iffalse)
                else:
                    endpos = command.endpos if command != None else condition.endpos
                    return CmdWhile(startpos, endpos, condition, command)
            elif tok.value == 'for':
                lexer.nextToken()
                nextTokenAssert(lexer, '(')
                nametok = nextTokenAssert(lexer, toktype = 'NAME')
                nextTokenAssert(lexer, ':')
                listexpr = parseExpr(lexer)
                nextTokenAssert(lexer, ')')
                command = parseCommand(lexer, depth = depth+1, inFunc = inFunc)
                endpos = command.endpos if command != None else condition.endpos
                return CmdFor(startpos, endpos, nametok, listexpr, command)
            elif tok.value == 'return':
                if not inFunc:
                    raise TokenError(tok, 'return statment allowed only in function definition')
                lexer.nextToken()
                if not testToken(lexer.lookAheadToken(0), ';'):
                    retexpr = parseExpr(lexer)
                else:
                    retexpr = None
                closesc = nextTokenAssert(lexer, ';')
                return CmdReturn(startpos, closesc.endpos, retexpr)
            elif tok.value == 'local':
                tok2=lexer.lookAheadToken(1)
                if tok2 == None:
                    raise UnexpEndError(lexer)
                if tok2.type == 'NAME':
                    lexer.nextToken()
                    localVDef = True
                    
        elif tok.type == 'OTHER':
            if tok.value == ';':
                lexer.nextToken()
                if(returnOnSemicolon): return None
                else: continue
            elif tok.value == '{':
                lexer.nextToken()
                arrstm = []
                while True:
                    tok = lexer.lookAheadToken(0)
                    if tok != None and tok.type == 'OTHER' and tok.value == '}': break
                    stm = parseCommand(lexer, depth = depth+1, inFunc = inFunc)
                    if stm == None: break
                    arrstm.append(stm)
                closepar = nextTokenAssert(lexer, '}')
                return CmdBlock(startpos, closepar.endpos, arrstm)
        tgtarr = []
        evalarr = []
        while True:
            expr1 = parseExpr(lexer)
            tok = lexer.lookAheadToken(0)
            if testToken(tok, '='):
                tgtexp = expr1
                lexer.nextToken()
                evalexp  = parseExpr(lexer)
            else:
                if localVDef:
                    tgtexp = expr1
                    evalexp = None
                else:
                    tgtexp = None
                    evalexp = expr1
            if localVDef and tgtexp.typeid != 'EXPNAME':
                raise ExprError(tgtexp, 'local variables should be specified by a name') 
            tgtarr.append(tgtexp)
            evalarr.append(evalexp)
            tok = lexer.lookAheadToken(0)
            if not testToken(tok, ','):
                break
            lexer.nextToken()
        closesc = nextTokenAssert(lexer, ';')
        return CmdCalc(startpos, closesc.endpos, tgtarr, evalarr, localVDef)
        
def parse(source):
    arrstm=[]
    lexer=Lexer(source)
    while True:
        nextstm = parseCommand(lexer)
        if nextstm != None:
            arrstm.append(nextstm)
        else:
            return arrstm
            
