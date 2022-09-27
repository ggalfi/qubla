# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022 Gergely Gálfi
#

import math
import cmath

def gcd(x, y):
    while(y != 0):
        y, x = x % y, y
    return x

class RationalValue:
    def __init__(self, numtype, value):
        if numtype != 'INT':
            if value[0] != 0:
                if value[1]<0:
                    value[0] = -value[0]
                    value[1] = -value[1]
                if numtype == 'DEC':
                    while(value[0] % 10 == 0 and value[1] > 1):
                        value[0] = value[0] // 10
                        value[1] = value[1] // 10
                else:
                    div = gcd(value[0] if value[0] >= 0 else -value[0], value[1])
                    value[0] = value[0] // div
                    value[1] = value[1] // div
                    
                if value[1] == 1:
                    numtype = 'INT'
                    value = value[0]
            else:
                numtype = 'INT'
                value = 0
        
        if numtype == 'INT':
            self.isneg = (value < 0)
        else:
            self.isneg = (value[0] < 0)
            
        self.numtype = numtype
        self.value = value

    def fromdec(x):
        n = 0
        denom = 1
        while n <= 400:
            mul = x*denom
            imul = math.floor(mul)
            if mul == imul: break
            n += 1
            denom *= 10
        return RationalValue('DEC',[imul, denom])
        
    def addsub(self, r, add):
        if self.numtype == 'INT':
            if r.numtype == 'INT':
                return RationalValue('INT', self.value + r.value if add else self.value - r.value)
            else:
                rettype = r.numtype
                x1 = self.value * r.value[1]
                x2 = r.value[0]
                denom = r.value[1]
        elif r.numtype == 'INT':
            rettype = self.numtype
            x1 = self.value[0]
            x2 = r.value * self.value[1]
            denom = self.value[1]
        else:
            x1 = self.value[0] * r.value[1]
            x2 = r.value[0] * self.value[1]
            denom = self.value[1] * r.value[1]
            rettype = 'FRAC' if self.numtype == 'FRAC' or r.numtype == 'FRAC' else 'DEC'
        return RationalValue(rettype, [x1 + x2 if add else x1 - x2, denom])
    
    def __add__(self, r):
        return self.addsub(r, True)

    def __sub__(self, r):
        return self.addsub(r, False)

    def __neg__(self):
        if self.numtype == 'INT':
            return RationalValue('INT', -self.value)
        else:
            return RationalValue(self.numtype , [-self.value[0], self.value[1]])
    
    def __mul__(self, r):
        if self.numtype == 'INT':
            if r.numtype == 'INT':
                return RationalValue('INT', self.value * r.value)
            else:
                return RationalValue(r.numtype, [self.value * r.value[0], r.value[1]])
        elif r.numtype == 'INT':
            return RationalValue(self.numtype, [self.value[0] * r.value, self.value[1]])
        else:
            return RationalValue(
                'FRAC' if self.numtype == 'FRAC' or r.numtype == 'FRAC' else 'DEC',
                [self.value[0] * r.value[0], self.value[1] * r.value[1]])
        
    def __truediv__(self, r):
        if r.value == 0:
            raise ZeroDivisionError
        if self.numtype == 'INT':
            if r.numtype == 'INT':           
                return RationalValue('FRAC', [self.value, r.value])
            else:
                return RationalValue('FRAC', [self.value * r.value[1], r.value[0]])
        elif r.numtype == 'INT':
            return RationalValue(self.numtype, [self.value[0] * r.value, self.value[1]])
        else:
            return RationalValue(
                'FRAC',
                [self.value[0] * r.value[1], self.value[1] * r.value[0]])
        
    def evaluate(self):
        if self.numtype == 'INT':
            return self.value
        else:
            return self.value[0]/self.value[1]
        
    def __eq__(self, obj):
        if type(self) != type(obj): return False
        if self.numtype != obj.numtype:
            if self.numtype == 'INT' or obj.numtype == 'INT': return False
            numer1 = self.value[0]
            denom1 = self.value[1]
            numer2 = obj.value[0]
            denom2 = obj.value[1]
            if self.numtype == 'DEC':
                return numer1 % numer2 == 0 and denom1 % denom2 == 0 and numer1//numer2 == denom1//denom2
            else:
                return numer2 % numer1 == 0 and denom2 % denom1 == 0 and numer2//numer1 == denom2//denom1
        else:
            return self.value == obj.value
                
    def __str__(self):
        if self.numtype == 'INT':
            return str(self.value)
        elif self.numtype == 'DEC':
            return str(self.value[0] / self.value[1])
        else:      
            ret = str(-self.value[0] if self.isneg else self.value[0]) + '/' + str(self.value[1])
            if self.isneg:
                ret = '-(' + ret + ')'
            return ret
    
RationalValue.Zero = RationalValue('INT', 0)
RationalValue.One = RationalValue('INT', 1)

class ComplexValue:
    def __init__(self, real = RationalValue.Zero, imag = RationalValue.Zero, funcname = None, arrarg = None):
        self.real = real
        self.imag = imag
        self.funcname = funcname
        self.arrarg = arrarg
        self.isfunc = funcname != None
    
    def __add__(self, z):
        if not (self.isfunc or z.isfunc):
            return ComplexValue(real = self.real + z.real, imag = self.imag + z.imag)
        else:
            return ComplexValue(funcname = '+', arrarg = [self, z])

    def __sub__(self, z):
        if not (self.isfunc or z.isfunc):
            return ComplexValue(real = self.real - z.real, imag = self.imag - z.imag)
        else:
            return ComplexValue(funcname = '-', arrarg = [self, z])
    
    def __neg__(self):
        if not self.isfunc:
            return ComplexValue(funcname = '-', arrarg = [self])
        else:
            return ComplexValue(real = -self.real, imag = -self.imag)
        
    def __mul__(self, z):
        if not (self.isfunc or z.isfunc):
            return ComplexValue(real = self.real * z.real - self.imag * z.imag, imag = self.imag * z.real + self.real * z.imag)
        else:
            return ComplexValue(funcname = '*', arrarg = [self, z])
        
    def __truediv__(self, z):
        if not (self.isfunc or z.isfunc):
            zabs2 = z.real * z.real + z.imag * z.imag
            return ComplexValue(
                real = (self.real * z.real + self.imag * z.imag) / zabs2,
                imag = (self.imag * z.real - self.real * z.imag) / zabs2)
        else:
            return ComplexValue(funcname = '/', arrarg = [self, z])
          
    def evaluate(self):
        if self.isfunc:
            evargs = [arg.evaluate() for arg in self.arrarg]
            nargs = len(evargs)
            if self.funcname == 'sqrt' and nargs == 1:
                if type(evargs[0]) == complex:
                    return cmath.sqrt(evargs[0])
                else:
                    return math.sqrt(evargs[0])
            elif self.funcname == 'exp' and nargs == 1:
                if type(evargs[0]) == complex:
                    return cmath.exp(evargs[0])
                else:
                    return math.exp(evargs[0])
            elif self.funcname == 'π' and nargs == 0:
                return math.pi
            elif self.funcname == '+' and nargs == 2:
                return evargs[0] + evargs[1]
            elif self.funcname == '-' and nargs in [1, 2]:
                return evargs[0] - evargs[1] if nargs == 2 else -evargs[0]
            elif self.funcname == '*' and nargs == 2:
                return evargs[0] * evargs[1]
            elif self.funcname == '/' and nargs == 2:
                return evargs[0] / evargs[1]
            else:
                raise Exception("unknown function '%s' for %d args: " % (self.funcname, nargs))


        else:
            if self.imag == RationalValue.Zero:
                return self.real.evaluate()
            else:
                return complex(self.real.evaluate(), self.imag.evaluate())

    
    def precedstr(self, prec):
        para = False
        if self.isfunc:
            args = self.arrarg
            nargs = len(args)
            if nargs == 0: return self.funcname
            if self.funcname in ['+', '-'] and nargs == 1:
                newprec1 = 9
                newprec2 = 9
            elif self.funcname == '+' and nargs > 1:
                newprec1 = 2
                newprec2 = 2
            elif self.funcname == '-'  and nargs > 1:
                newprec1 = 2
                newprec2 = 3
            elif self.funcname == '*':
                newprec1 = 4
                newprec2 = 4
            elif self.funcname == '/':
                newprec1 = 4
                newprec2 = 5
            else:
                newprec1 = 0
                newprec2 = 0
                
            if newprec1 == 0:
                ret = '%s(%s)' % (self.funcname, ', '.join([a.precedstr(0) for a in args]))           
            elif newprec1 == 9:
                ret = self.funcname + str(args[0])
            else:
                ret = self.funcname.join([args[i].precedstr(newprec1 if i == 0 else newprec2) for i in range(len(args))])
                if newprec1 < prec:
                    para = True
                
        else:
            if self.imag == RationalValue.Zero:
                ret = str(self.real)
            else:
                simag = str(self.imag)
                if self.imag.numtype == 'FRAC':
                    simag = simag + '*1i'
                else:
                    simag = simag +'i'
                if self.real == RationalValue.Zero:
                    ret = simag
                else:
                    ret = str(self.real) + ('' if self.imag.isneg else '+') + simag
                if prec > 0:
                    para = True
        if para:
            ret = '(' + ret + ')'
        return ret
        
    def __str__(self):
        return self.precedstr(0)
    
    def __eq__(self, obj):
        if type(self) != type(obj): return False
        if self.isfunc:
            if self.funcname != obj.funcname: return False
            n = len(self.arrarg)
            if n != len(obj.arrarg): return False
            for i in range(n):
                if self.arrarg[i] != obj.arrarg[i]: return False
            return True
        else:
            return (self.real == obj.real) and (self.imag == obj.imag) 
 
ComplexValue.Zero = ComplexValue(real = RationalValue.Zero, imag = RationalValue.Zero)
ComplexValue.One = ComplexValue(real = RationalValue.One, imag = RationalValue.Zero)