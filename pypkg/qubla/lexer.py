# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022 Gergely Gálfi
#

class SourcePosition:
    def __init__(self, idx, linenum, linepos, srcfile = None):
        self.srcfile = srcfile
        self.idx=idx
        self.linenum=linenum
        self.linepos=linepos
        
    def copy(self):
        return SourcePosition(self.idx, self.linenum, self.linepos, srcfile = self.srcfile)
    
    def __str__(self):
        return  '%sline:%d offset:%d' % (
            'filename: %s ' % self.srcfile if self.srcfile != None else '',
            self.linenum,
            self.linepos)

class QBLSyntaxError(Exception):
    def __init__(self, pos, msg):
        super().__init__('Syntax error at ' + str(pos) + ': ' + msg)
        self.pos = pos
    
class Token:
    def __init__(self, type, value, startpos, endpos = None, alnumname = False):
        self.type = type
        self.value = value
        self.startpos = startpos
        if endpos == None: self.endpos = startpos
        else: self.endpos = endpos
        self.alnumname = alnumname
        
    def __str__(self):
        return "Token type:%s value:'%s'%s from %s to %s" % (
            self.type,
            self.value,
            ' alnum: ' + str(self.alnumname) if self.type == 'NAME' else '',
            str(self.startpos), str(self.endpos))
    
    def __repr__(self):
        return self.__str__()
         
def charType(c):
    if c=='': return 'EOF'
    if (c>='a' and c<='z') or (c>='A' and c<='Z'): return 'ALPHA'
    elif c>='0' and c<='9': return 'NUM'
    elif c in [' ', '\t', '\n', '\r']: return 'WS'
    else: return 'OTHER'
    
class Lexer:
    def __init__(self, source = None, srcfile = None):
        if srcfile != None:
            with open(srcfile, 'r', encoding = 'utf-8') as f:
                self.src = f.read()
        else:
            self.src=source

        self.len=len(self.src)
        self.nextpos=SourcePosition(-1, 0, 0, srcfile = srcfile)
        
        self.state=0
        self.str=''
        self.holdchar=False
        self.newline=True
        self.laarr=[None]

    def prepNextToken(self):                
        while True:
            if not self.holdchar:
                self.nextpos.idx+=1
                if self.nextpos.idx<self.len:
                    self.nextc=self.src[self.nextpos.idx]
                    if self.newline:
                        self.nextpos.linenum+=1
                        self.nextpos.linepos=1
                    else:
                        self.nextpos.linepos+=1
                    self.newline=(self.nextc=='\n')
                else:
                    self.nextc=''
            else:
                self.holdchar=False
            ctype=charType(self.nextc)

            if self.state == 0:
                if ctype == 'EOF':
                    self.holdchar=True
                    return None
                elif ctype == 'ALPHA' or self.nextc == '_':
                    self.state = 1
                    self.startpos=self.nextpos.copy()
                    self.endpos=self.nextpos.copy()
                    self.str=self.nextc
                elif ctype == 'NUM' or self.nextc == '.':
                    self.state = 2
                    self.startpos = self.nextpos.copy()
                    self.endpos = self.nextpos.copy()
                    self.str = self.nextc
                elif ctype == 'WS':
                    pass
                elif self.nextc in ['=', '!', '<', '>', '&', '|']:
                    self.state = 3
                    self.str = self.nextc
                    self.startpos = self.nextpos.copy()
                elif self.nextc == '"':
                    self.state = 5
                    self.startpos = self.nextpos.copy()
                    self.str = ''
                elif self.nextc == '`':
                    self.state = 7
                    self.startpos = self.nextpos.copy()
                    self.str = ''
                    self.alnumname = True
                elif self.nextc == '/':
                    self.state = 9
                    self.startpos=self.nextpos.copy()
                else:
                    return Token('OTHER', self.nextc, self.nextpos.copy())
                    
            elif self.state == 1:
                if(ctype=='ALPHA' or ctype == 'NUM'  or self.nextc == '_'):
                    self.str+=self.nextc
                    self.endpos=self.nextpos.copy()
                else:
                    self.holdchar=True
                    self.state = 0
                    return Token('NAME', self.str, self.startpos, self.endpos, True)
                
            elif self.state == 2:
                if ctype == 'NUM' or ctype == 'ALPHA' or self.nextc in ['_', '.']:
                    self.str+=self.nextc
                    self.endpos=self.nextpos.copy()
                else:
                    self.holdchar=True
                    self.state = 0
                    return Token('NUM', self.str, self.startpos, self.nextpos.copy())
            
            elif self.state == 3:
                opstr = self.str+self.nextc
                if opstr in ['===', '!==', '<=', '>=', '&&', '||', '>>', '<<']:
                    self.state = 0
                    return Token('OTHER', opstr, self.startpos, self.nextpos.copy())
                elif opstr in ['==', '!=']:
                    self.str = opstr
                else:
                    self.state = 0
                    self.holdchar=True
                    return Token('OTHER', self.str, self.startpos)
                        
            elif self.state == 5:
                if self.nextc == '"':
                    self.state = 0
                    return Token('STR', self.str, self.startpos, self.nextpos.copy())
                elif self.nextc =='':
                    raise QBLSyntaxError(self.startpos, "Untermintated string")
                else:
                    self.str += self.nextc
                    
            elif self.state == 7:
                if self.nextc == '`':
                    self.state = 0
                    if self.str != '' and (self.alnumname or self.str in ['==', '!=', '===', '!==', '<', '>', '<=', '>=', '!', '&&', '||', '+', '-', '*', '/', '//', '~', '%']):
                        return Token('NAME', self.str, self.startpos, endpos = self.nextpos.copy(), alnumname = self.alnumname)
                    else:
                        raise QBLSyntaxError(self.startpos, "Illegal quoted name: "+self.str)
                else:
                    if ctype!='ALPHA' and self.nextc != '_' and (self.str == '' or ctype != 'NUM'):
                        self.alnumname = False
                    self.str += self.nextc
                    
            elif self.state == 9:
                if self.nextc == '*':                    
                    self.state = 10
                elif self.nextc == '%':
                    self.state = 11
                elif self.nextc == '/':
                    self.state = 0
                    return Token('OTHER', '//', self.startpos)
                else:
                    self.holdchar=True
                    self.state = 0
                    return Token('OTHER', '/', self.startpos)
                
            elif self.state == 10:
                if self.nextc == '*':                    
                    self.state = 12
                elif self.nextc == '':
                    raise QBLSyntaxError(self.startpos, "Untermintated comment")
                    
            elif self.state == 11:
                if self.nextc in ['\n', '']:
                    self.state = 0
                
            elif self.state == 12:
                if self.nextc == '/':
                    self.state = 0
                elif self.nextc == '':
                    raise QBLSyntaxError(self.startpos, "Untermintated comment")
                else:
                    self.state = 10


    def lookAheadToken(self, n):
        while len(self.laarr)<=n+1:
            tok=self.prepNextToken()
            if tok!=None:
                self.laarr.append(tok)
            else: return None
        return self.laarr[n+1]
    
    def nextToken(self):
        ret=self.lookAheadToken(0)
        if ret!=None: del self.laarr[0]
        return ret
