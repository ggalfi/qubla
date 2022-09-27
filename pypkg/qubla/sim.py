# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022 Gergely Gálfi
#

from .parser import int2word

def statevec(qm):
    inited = [False for i in range(qm.nqb)]
    arrinitstep = []
    for i in range(qm.nqb):
        if not inited[i]:
            initst = qm.arrstep[qm.arrqbcompr[i].arrstep[0]]
            if initst.typeid == 'INIT':
                arrinitqb = initst.arrqb.copy()
                arrstate = [initst.state[k].evaluate() for k in range(initst.nbase)]
            elif initst.typeid == 'COPY':
                arrinitqb = [initst.dstidx]
                arrstate = [1.0+0j, 0j]
            elif initst.typeid == 'APPTBL':
                arrinitqb = initst.arrqb[initst.nin:]
                arrstate = [1.0+0j if k == 0 else 0j for k in range(1<<len(arrinitqb))]
            else:
                arrinitqb = []
            ninit = len(arrinitqb)
            if ninit > 0:
                for k in range(len(arrinitqb)):
                    qb = qm.arrqb[arrinitqb[k]].compridx
                    arrinitqb[k] = qb
                    inited[qb] = True
                arrinitstep.append((arrinitqb, arrstate))
            
    nbas = 1<<qm.nqb
    state = []
    for i in range(nbas):
        comp = 1.0+0j
        bits = int2word(i, qm.nqb)
        for arrinitqb, arrstate in arrinitstep:
            key = 0
            for k in range(len(arrinitqb)):
                key += (bits[arrinitqb[k]])<<k
            comp = comp*arrstate[key]
        state.append(comp)

    arrprepst = []
    for step in qm.arrstep:
        if step != None and step.typeid != 'INIT':
            stqb = [qm.arrqb[qbidx].compridx for qbidx in step.arrqb]
            mask = 0
            for qb in stqb:
                mask |= 1<<qb
            mask = ~mask
            nstqb = len(stqb)
            rstqb = range(1<<nstqb)
            invtbl = [None for i in rstqb]
            if step.typeid == 'APPTBL':
                for i in range(1<<step.nin):
                    invtbl[step.tbl[i]] = i
            elif step.typeid == 'APPOP':
                invtbl = [[step.opmatr[i][k].evaluate() for k in rstqb] for i in rstqb]
            else:
                invtbl[0] = 0
                invtbl[3] = 1
            arrprepst.append((step.typeid, stqb, mask, invtbl))
        
            
    for sttype, stqb, mask, invtbl in arrprepst:
        newstate = []
        nstqb = len(stqb)
        rstqb = range(nstqb)
        for i in range(nbas):
            outb = 0
            for k in rstqb:
                outb |= ((i>>stqb[k])&1)<<k
            if sttype == 'APPOP':
                newcomp = 0.0j
                for inb in rstqb:
                    stidx = mask & i
                    for k in rstqb:                        
                        stidx |= ((inb>>k)&1)<<stqb[k]
                    newcomp += invtbl[outb][inb]*state[stidx]
                newstate.append(newcomp)
            else:
                inb = invtbl[outb]
                if inb == None:
                    newstate.append(0j)
                else:
                    stidx = mask & i 
                    for k in rstqb: 
                        stidx |= ((inb>>k)&1)<<stqb[k]
                    newstate.append(state[stidx])
        state = newstate
    return state

def getDens(state, arrqb):
    nst = len(state)
    nbits = len(arrqb)
    rbits = range(nbits)
    nitems = 1<<nbits
    ret = [0.0 for i in range(nitems)]
    for i in range(nst):
        itemidx = 0
        for k in rbits:
            itemidx |= ((i>>arrqb[k])&1)<<k
        comp = state[i]
        ret[itemidx] += comp.real*comp.real + comp.imag*comp.imag
    return ret