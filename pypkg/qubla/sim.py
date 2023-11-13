# Qubla
#
# www.absimp.org/qubla
#
# Copyright (c) 2022-2023 Gergely Gálfi
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
            elif initst.typeid == 'APPTBL':
                arrinitqb = [qb for qb in initst.arrqbout if not qb in initst.arrqbin]
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
                key |= (bits[arrinitqb[k]])<<k
            comp = comp*arrstate[key]
        state.append(comp)

    arrprepst = []
    for step in qm.arrstep:
        if step != None and step.typeid in ['APPTBL', 'APPOP']:
            stqb = [qm.arrqb[qbidx].compridx for qbidx in step.arrqb]
            mask = 0
            for qb in stqb:
                mask |= 1<<qb
            mask = ~mask
            nstqb = len(stqb)
            rstqb = range(1<<nstqb)
            invtbl = [None for i in rstqb]
            if step.typeid == 'APPTBL':
                arrinidx = [step.arrqb.index(qb) for qb in step.arrqbin]
                arroutidx = [step.arrqb.index(qb) for qb in step.arrqbout]
                for i in range(1<<step.nin):
                    inidx = 0
                    outidx = 0
                    for k in range(step.nin):
                        inbit = ((i >> arrinidx[k]) & 1)
                        inidx |= inbit << k
                        if step.arrcopy[k]:
                            outidx |= inbit << arrinidx[k]
                    outval = step.tbl[i]
                    for k in range(step.nout):
                        outidx |= ((outval >> k) & 1) << arroutidx[k]
                    invtbl[outidx] = inidx
            elif step.typeid == 'APPOP':
                invtbl = [[step.opmatr[i][k].evaluate() for k in rstqb] for i in rstqb]
            
            arrprepst.append((step.typeid, stqb, mask, invtbl))
            
    for sttype, stqb, mask, invtbl in arrprepst:
        #print('invtbl',invtbl)
        newstate = []
        nstqb = len(stqb)
        rstqb = range(nstqb)
        for i in range(nbas):
            outb = 0
            for k in rstqb:
                outb |= ((i>>stqb[k])&1)<<k
            if sttype == 'APPOP':
                newcomp = 0.0j
                for inb in range(1<<nstqb):
                    stidx = mask & i
                    for k in rstqb:                        
                        stidx |= ((inb>>k)&1)<<stqb[k]
                    #print('i:', i, ' inb:', inb, ' outb:', outb, ' stidx:', stidx, ' invtbl:',invtbl)
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
        #print('State:', state)
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